import os
import time
import unicodecsv as csv
import re
import string
try:
    from urllib import quote_plus
except ImportError:
    from urllib.parse import quote_plus

from bouncer.constants import MANAGE
from flask import Blueprint, current_app, request
from flask import url_for
from flask_login import login_required, current_user

from flask_restful import Resource, reqparse

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload

from compair.authorization import require
from compair.core import event, abort
from compair.models import User, CourseRole, Assignment, UserCourse, Course, Answer, \
    AnswerComment, AssignmentCriterion, Comparison, AnswerCommentType, Group, File, KalturaMedia
from compair.kaltura import KalturaAPI
from .util import new_restful_api

report_api = Blueprint('report_api', __name__)
api = new_restful_api(report_api)

report_parser = reqparse.RequestParser()
report_parser.add_argument('group_id')
# may change 'type' to int
report_parser.add_argument('type', required=True, nullable=False)
report_parser.add_argument('assignment')

# events
on_export_report = event.signal('EXPORT_REPORT')
# should we have a different event for each type of report?

def name_generator(course, report_name, group, file_type="csv"):
    date = time.strftime("%Y-%m-%d--%H-%M-%S")
    group_name_output = ""
    if group:
        group_name_output = group.name + '-'
    # from https://gist.github.com/seanh/93666
    # return a file system safe filename
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = course.name + "-" + group_name_output + report_name + "--" + date + "." + file_type
    return ''.join(char for char in filename if char in valid_chars)


class ReportRootAPI(Resource):
    @login_required
    def post(self, course_uuid):
        course = Course.get_active_by_uuid_or_404(course_uuid)
        assignment = Assignment(course_id=course.id)
        require(MANAGE, assignment,
            title="Report Not Run",
            message="Sorry, your system role does not allow you to run reports.")

        params = report_parser.parse_args()
        group_uuid = params.get('group_id', None)
        report_type = params.get('type')

        group = Group.get_active_by_uuid_or_404(group_uuid) if group_uuid else None

        assignments = []
        assignment_uuid = params.get('assignment', None)
        if assignment_uuid:
            assignment = Assignment.get_active_by_uuid_or_404(assignment_uuid)
            assignments = [assignment]
        else:
            assignments = Assignment.query \
                .filter_by(
                    course_id=course.id,
                    active=True
                ) \
                .all()

        if report_type == "participation_stat":
            data = participation_stat_report(course, assignments, group, assignment_uuid is None)

            title = [
                'Assignment', 'Last Name', 'First Name','Student Number', 'User UUID',
                'Answer', 'Answer ID', 'Answer Deleted', 'Answer Submission Date', 'Answer Last Modified',
                'Answer Score (Normalized)', 'Overall Rank',
                'Comparisons Submitted', 'Comparisons Required', 'Comparison Requirements Met',
                'Self-Evaluation Submitted', 'Feedback Submitted (During Comparisons)', 'Feedback Submitted (Outside Comparisons)']
            titles = [title]

        elif report_type == "participation":
            user_titles = ['Last Name', 'First Name', 'Student Number']
            data = participation_report(course, assignments, group)

            title_row1 = [""] * len(user_titles)
            title_row2 = user_titles

            for assignment in assignments:
                title_row1 += [assignment.name]
                title_row2.append('Participation Grade')
                title_row1 += [""]
                title_row2.append('Answer')
                title_row1 += [""]
                title_row2.append('Attachment')
                title_row1 += [""]
                title_row2.append('Answer Score (Normalized)')
                title_row1 += [""]
                title_row2.append("Comparisons Submitted (" + str(assignment.total_comparisons_required) + ' required)')
                if assignment.enable_self_evaluation:
                    title_row1 += [""]
                    title_row2.append("Self-Evaluation Submitted")
                title_row1 += [""]
                title_row2.append("Feedback Submitted (During Comparisons)")
                title_row1 += [""]
                title_row2.append("Feedback Submitted (Outside Comparisons)")
            titles = [title_row1, title_row2]

        elif report_type == "peer_feedback":
            titles1 = [
                "",
                "Feedback Author", "", "",
                "Answer Author", "", "",
                "", ""
            ]
            titles2 = [
                "Assignment",
                "Last Name", "First Name", "Student Number",
                "Last Name", "First Name", "Student Number",
                "Feedback Type", "Feedback", "Feedback Character Count"
            ]
            data = peer_feedback_report(course, assignments, group)
            titles = [titles1, titles2]

        else:
            abort(400, title="Report Not Run", message="Please try again with a report type from the list of report types provided.")

        name = name_generator(course, report_type, group)
        tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], name)

        with open(tmp_name, 'wb') as report:
            out = csv.writer(report)
            for t in titles:
                out.writerow(t)
            for s in data:
                out.writerow(s)

        on_export_report.send(
            self,
            event_name=on_export_report.name,
            user=current_user,
            course_id=course.id,
            data={'type': report_type, 'filename': name})

        return {'file': 'report/' + name}


api.add_resource(ReportRootAPI, '')


def participation_stat_report(course, assignments, group, overall):
    report = []

    query = UserCourse.query \
        .join(User, User.id == UserCourse.user_id) \
        .filter(and_(
            UserCourse.course_id == course.id,
            UserCourse.course_role != CourseRole.dropped
        ))
    if group:
        query = query.filter(group.id == UserCourse.group_id)
    classlist = query.order_by(User.lastname, User.firstname, User.id).all()

    assignment_ids = [assignment.id for assignment in assignments]
    class_ids = [u.user.id for u in classlist]

    group_ids = [g.id for g in course.groups.all() if g.active]
    group_users = {}
    for user_course in classlist:
        if user_course.group_id:
            group_users.setdefault(user_course.group_id, []).append(user_course.user_id)

    total_req = 0
    total = {}

    for assignment in assignments:
        # ANSWERS: instructors / TAs could submit multiple answers. normally 1 answer per student
        answers = Answer.query \
            .options(joinedload('score')) \
            .filter(and_(
                Answer.assignment_id == assignment.id,
                Answer.comparable == True,
                Answer.draft == False,
                Answer.practice == False,
                or_(
                    Answer.user_id.in_(class_ids),
                    Answer.group_id.in_(group_ids)
                )
            )) \
            .order_by(Answer.submission_date) \
            .all()

        user_answers = {}   # structure - user_id/[answer list]
        for answer in answers:
            user_ids = group_users.get(answer.group_id, []) if answer.group_answer else [answer.user_id]
            for user_id in user_ids:
                user_answers.setdefault(user_id, []).append(answer)

        # EVALUATIONS
        evaluations = Comparison.query \
            .with_entities(Comparison.user_id, func.count(Comparison.id)) \
            .filter_by(
                assignment_id=assignment.id,
                completed=True
            ) \
            .group_by(Comparison.user_id) \
            .all()
        evaluation_submitted = {user_id: int(count) for (user_id, count) in evaluations}

        # COMMENTS
        comments = AnswerComment.query \
            .join(Answer) \
            .filter(Answer.assignment_id == assignment.id) \
            .filter(AnswerComment.draft == False) \
            .filter(AnswerComment.active == True) \
            .with_entities(AnswerComment.user_id, AnswerComment.comment_type, func.count(AnswerComment.id)) \
            .group_by(AnswerComment.user_id, AnswerComment.comment_type) \
            .all()
        comments_self_eval = {user_id: count for (user_id, comment_type, count) in comments if comment_type == AnswerCommentType.self_evaluation}
        comments_during_comparison = {user_id: count for (user_id, comment_type, count) in comments if comment_type == AnswerCommentType.evaluation}
        comments_private = {user_id: count for (user_id, comment_type, count) in comments if comment_type == AnswerCommentType.private}
        comments_public = {user_id: count for (user_id, comment_type, count) in comments if comment_type == AnswerCommentType.public}

        total_req += assignment.total_comparisons_required  # for overall required

        for user_course in classlist:
            user = user_course.user
            temp = [assignment.name, user.lastname, user.firstname, user.student_number, user.uuid]

            # OVERALL
            total.setdefault(user.id, {
                'total_answers': 0,
                'total_evaluations': 0,
                'total_comments_self_eval': 0,
                'total_comments_during_comparison': 0,
                'total_comments_outside_comparison': 0
            })

            # each user has at least 1 line per assignment, regardless whether there is an answer
            active_answer_list = [ans for ans in user_answers.get(user.id, []) if ans.active]
            deleted_answer_list = [ans for ans in user_answers.get(user.id, []) if not ans.active]
            submitted = len(active_answer_list)
            deleted_count = len(deleted_answer_list)
            the_answer = active_answer_list[0] if submitted else None
            is_deleted = 'N' if submitted else 'N/A'
            answer_uuid = the_answer.uuid if submitted else 'N/A'
            answer_submission_date = datetime_to_string(the_answer.submission_date) if submitted else 'N/A'
            answer_last_modified = datetime_to_string(the_answer.modified) if submitted else 'N/A'
            answer_text = snippet(the_answer.content) if submitted else 'N/A'
            answer_rank = the_answer.score.rank if submitted and the_answer.score else 'Not Evaluated'
            answer_score = round_score(the_answer.score.normalized_score) if submitted and the_answer.score else 'Not Evaluated'
            total[user.id]['total_answers'] += submitted
            temp.extend([answer_text, answer_uuid, is_deleted, answer_submission_date, answer_last_modified, answer_score, answer_rank])

            evaluations = evaluation_submitted.get(user.id, 0)
            evaluation_req_met = 'Yes' if evaluations >= assignment.total_comparisons_required else 'No'
            total[user.id]['total_evaluations'] += evaluations
            temp.extend([evaluations, assignment.total_comparisons_required, evaluation_req_met])

            comment_self_eval_count = comments_self_eval.get(user.id, 0)
            comment_during_comparison_count = comments_during_comparison.get(user.id, 0)
            comment_outside_comparison_count = comments_private.get(user.id, 0) + comments_public.get(user.id, 0)
            total[user.id]['total_comments_self_eval'] += comment_self_eval_count
            total[user.id]['total_comments_during_comparison'] += comment_during_comparison_count
            total[user.id]['total_comments_outside_comparison'] += comment_outside_comparison_count
            temp.extend([comment_self_eval_count, comment_during_comparison_count, comment_outside_comparison_count])

            report.append(temp)

            # handle multiple answers from the user (normally only apply for instructors / TAs)
            if submitted > 1:
                for answer in active_answer_list[1:]:
                    answer_uuid = answer.uuid
                    answer_submission_date = datetime_to_string(answer.submission_date)
                    answer_last_modified = datetime_to_string(answer.modified)
                    answer_text = snippet(answer.content)
                    answer_rank = answer.score.rank if submitted and answer.score else 'Not Evaluated'
                    answer_score = round_score(answer.score.normalized_score) if submitted and answer.score else 'Not Evaluated'
                    temp = [assignment.name, user.lastname, user.firstname, user.student_number, user.uuid,
                        answer_text, answer_uuid, 'N', answer_submission_date, answer_last_modified,
                        answer_score, answer_rank,
                        evaluations, assignment.total_comparisons_required,
                        evaluation_req_met, comment_self_eval_count, comment_during_comparison_count, comment_outside_comparison_count]

                    report.append(temp)

            # add deleted answers, if any
            if deleted_count > 0:
                for answer in deleted_answer_list:
                    answer_uuid = answer.uuid
                    answer_submission_date = datetime_to_string(answer.submission_date)
                    answer_last_modified = datetime_to_string(answer.modified)
                    answer_text = snippet(answer.content)
                    answer_rank = answer.score.rank if answer.score else 'Not Evaluated'
                    answer_score = round_score(answer.score.normalized_score) if answer.score else 'Not Evaluated'
                    temp = [assignment.name, user.lastname, user.firstname, user.student_number, user.uuid,
                        answer_text, answer_uuid, 'Y', answer_submission_date, answer_last_modified,
                        answer_score, answer_rank,
                        evaluations, assignment.total_comparisons_required,
                        evaluation_req_met, comment_self_eval_count, comment_during_comparison_count, comment_outside_comparison_count]

                    report.append(temp)

    if overall:
        for user_course_student in classlist:
            user = user_course_student.user
            sum_submission = total.setdefault(user.id, {
                'total_answers': 0,
                'total_evaluations': 0,
                'total_comments_self_eval': 0,
                'total_comments_during_comparison': 0,
                'total_comments_outside_comparison': 0
            })
            # assume a user can only at most do the required number
            req_met = 'Yes' if sum_submission['total_evaluations'] >= total_req else 'No'
            temp = [
                '(Overall in Course)', user.lastname, user.firstname, user.student_number, user.uuid,
                sum_submission['total_answers'], '', '', '', '', '', '',
                sum_submission['total_evaluations'], total_req, req_met, sum_submission['total_comments_self_eval'],
                sum_submission['total_comments_during_comparison'], sum_submission['total_comments_outside_comparison']]
            report.append(temp)
    return report


def participation_report(course, assignments, group):
    report = []

    query = UserCourse.query \
        .join(User, User.id == UserCourse.user_id) \
        .filter(and_(
            UserCourse.course_id == course.id,
            UserCourse.course_role == CourseRole.student
        ))
    if group:
        query = query.filter(UserCourse.group_id == group.id)
    classlist = query.order_by(User.lastname, User.firstname, User.id).all()

    assignment_ids = [assignment.id for assignment in assignments]
    class_ids = [u.user_id for u in classlist]
    group_ids = [g.id for g in course.groups.all() if g.active]
    group_users = {}
    for user_course in classlist:
        if user_course.group_id:
            group_users.setdefault(user_course.group_id, []).append(user_course.user_id)

    # ANSWERS - scores
    answers = Answer.query \
        .options(joinedload('file')) \
        .options(joinedload('score')) \
        .options(joinedload('criteria_scores')) \
        .filter(and_(
            Answer.assignment_id.in_(assignment_ids),
            Answer.draft == False,
            Answer.practice == False,
            Answer.active == True,
            or_(
                Answer.user_id.in_(class_ids),
                Answer.group_id.in_(group_ids)
            )
        )) \
        .all()

    scores = {} # structure - user_id/assignment_id/normalized_score
    criteria_scores = {} # structure - user_id/assignment_id/criterion_id/normalized_score
    answer_count = {} # structure - user_id/assignment_id/[answers]
    answer_attachment = {} # structure - user_id/assignment_id/[File]
    for answer in answers:
        user_ids = group_users.get(answer.group_id, []) if answer.group_answer else [answer.user_id]
        for user_id in user_ids:
            # set scores
            user_object = scores.setdefault(user_id, {})
            user_object.setdefault(answer.assignment_id, answer.score.normalized_score if answer.score else None)

            # set criteria_scores
            user_object = criteria_scores.setdefault(user_id, {})
            assignment_object = user_object.setdefault(answer.assignment_id, {})
            for s in answer.criteria_scores:
                assignment_object[s.criterion_id] = s.normalized_score

            # set answer_count
            user_object = answer_count.setdefault(user_id, {})
            assignment_list = user_object.setdefault(answer.assignment_id, [])
            assignment_list.append(escape_leading_symbols_for_excel(strip_html(answer.content)))

            # set answer_attachment
            user_object = answer_attachment.setdefault(user_id, {})
            assignment_list = user_object.setdefault(answer.assignment_id, [])
            assignment_list.append(answer.file)

    # COMPARISONS
    comparisons_counts = Comparison.query \
        .filter(and_(
            Comparison.completed == True,
            Comparison.user_id.in_(class_ids),
            Comparison.assignment_id.in_(assignment_ids)
        )) \
        .with_entities(Comparison.assignment_id, Comparison.user_id, func.count(Comparison.id)) \
        .group_by(Comparison.assignment_id, Comparison.user_id) \
        .all()

    comparisons = {}  # structure - user_id/assignment_id/count
    for (assignment_id, user_id, count) in comparisons_counts:
        comparisons.setdefault(user_id, {}).setdefault(assignment_id, count)

    # CRITERIA
    assignment_criteria = AssignmentCriterion.query \
        .filter(AssignmentCriterion.assignment_id.in_(assignment_ids)) \
        .filter_by(active=True) \
        .order_by(AssignmentCriterion.position) \
        .all()

    criteria = {}  # structure - assignment_id/criterion_id
    for assignment_criterion in assignment_criteria:
        criteria.setdefault(assignment_criterion.assignment_id, [])
        criteria[assignment_criterion.assignment_id] \
            .append(assignment_criterion.criterion_id)

    user_grades = {} # structure - user_id/assignment_id/grade
    for assignment in assignments:
        for grade in assignment.grades:
            user_object = user_grades.setdefault(grade.user_id, {})
            user_object[grade.assignment_id] = round_grade(grade.grade * 100)

    for user_courses in classlist:
        user = user_courses.user
        temp = [user.lastname, user.firstname, user.student_number]

        for assignment in assignments:
            # COMMENTS
            comments = AnswerComment.query \
                .join(Answer) \
                .filter(Answer.assignment_id == assignment.id) \
                .filter(AnswerComment.user_id == user.id) \
                .filter(AnswerComment.draft == False) \
                .filter(AnswerComment.active == True) \
                .with_entities(AnswerComment.comment_type, func.count(AnswerComment.id)) \
                .group_by(AnswerComment.comment_type) \
                .all()
            comments_counts = {comment_type: count for (comment_type, count) in comments}
            comments_self_eval = comments_counts.get(AnswerCommentType.self_evaluation, 0)
            comments_during_comparison = comments_counts.get(AnswerCommentType.evaluation, 0)
            comments_outside_comparison = comments_counts.get(AnswerCommentType.public, 0) + comments_counts.get(AnswerCommentType.private, 0)

            temp.append(user_grades.get(user.id, {}).get(assignment.id, ""))
            temp.append('\n\n'.join(answer_count.get(user.id, {}).get(assignment.id, [])))
            temp.append('\n\n'.join( \
                [generate_hyperlink_for_excel(attachment_url(f)) for f in answer_attachment.get(user.id, {}).get(assignment.id, [])] \
                ))
            if user.id not in scores or assignment.id not in scores[user.id]:
                score = 'No Answer'
            elif scores[user.id][assignment.id] == None:
                score = 'Not Evaluated'
            else:
                score = round_score(scores[user.id][assignment.id])
            temp.append(score)

            if user.id not in comparisons or assignment.id not in comparisons[user.id]:
                compared = 0
            else:
                compared = comparisons[user.id][assignment.id]
            temp.append(str(compared))
            # self-evaluation
            if assignment.enable_self_evaluation:
                temp.append(comments_self_eval)
            # feedback counts
            temp.append(comments_during_comparison)
            temp.append(comments_outside_comparison)

        report.append(temp)

    return report

def peer_feedback_report(course, assignments, group):
    report = []

    senders = User.query \
        .join("user_courses") \
        .filter(and_(
            UserCourse.course_id == course.id,
            UserCourse.course_role == CourseRole.student
        )) \
        .order_by(User.lastname, User.firstname, User.id)
    if group:
        senders = senders.filter(UserCourse.group_id == group.id)
    senders = senders.all()
    sender_user_ids = [u.id for u in senders]

    assignment_ids = [assignment.id for assignment in assignments]

    answer_comments = AnswerComment.query \
        .join(Answer, AnswerComment.answer_id == Answer.id) \
        .outerjoin(User, User.id == Answer.user_id) \
        .outerjoin(Group, Group.id == Answer.group_id) \
        .with_entities(
            Answer.group_answer.label("receiver_is_group_answer"),
            AnswerComment.user_id.label("sender_user_id"),
            Answer.assignment_id.label("assignment_id"),
            AnswerComment.comment_type,
            AnswerComment.content,
            User.firstname.label("receiver_firstname"),
            User.lastname.label("receiver_lastname"),
            User.student_number.label("receiver_student_number"),
            Group.name.label("receiver_group_name")
        ) \
        .filter(Answer.assignment_id.in_(assignment_ids)) \
        .filter(AnswerComment.user_id.in_(sender_user_ids)) \
        .filter(AnswerComment.comment_type != AnswerCommentType.self_evaluation) \
        .filter(Answer.draft == False) \
        .filter(Answer.practice == False) \
        .filter(AnswerComment.draft == False) \
        .order_by(AnswerComment.created) \
        .all()

    for assignment in assignments:
        for user in senders:
            user_sent_feedback = [ac for ac in answer_comments  \
                if ac.sender_user_id == user.id and ac.assignment_id == assignment.id]

            if len(user_sent_feedback) > 0:
                for feedback in user_sent_feedback:

                    feedback_type = ""
                    if feedback.comment_type == AnswerCommentType.evaluation:
                        feedback_type = "Comparison"
                    elif feedback.comment_type == AnswerCommentType.private:
                        feedback_type = "Private Reply"
                    elif feedback.comment_type == AnswerCommentType.public:
                        feedback_type = "Public Reply"

                    temp = [
                        assignment.name,
                        user.lastname, user.firstname, user.student_number
                    ]

                    if feedback.receiver_is_group_answer:
                        temp += [feedback.receiver_group_name, "", ""]
                    else:
                        temp += [feedback.receiver_lastname, feedback.receiver_firstname, feedback.receiver_student_number]

                    plain_feedback_content = strip_html(feedback.content).strip(' \t\n\r')
                    temp += [feedback_type, \
                        escape_leading_symbols_for_excel(plain_feedback_content), \
                        len(plain_feedback_content)]

                    report.append(temp)

            else:
                # enter blank row
                temp = [
                    assignment.name,
                    user.lastname, user.firstname, user.student_number,
                    "---", "---", "---",
                    "", ""
                ]
                report.append(temp)

    return report


def strip_html(text):
    if not text:
        return ''
    text = re.sub('<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', '\'')
    return text


def escape_leading_symbols_for_excel(text):
    result = text
    # Insert a tab at the begining if the text starts with specific symbol.
    # This will escape it for Excel. If the CSV is to be processed by another
    # program, trimming will be required.
    if len(text) == 0:
        return result
    if text[0] in ['-', '+', '=']:
        result = '\t' + text
    return result


def generate_hyperlink_for_excel(url):
    if not url:
        return ''
    # Excel has length limit of 255 for string parameters.
    # Unfortunately, trying to break it down and concatenate back together wont work for HYPERLINK.
    # chunks = 'CONCATENATE("' + '","'.join([url[i:i+255] for i in range(0, len(url), 255)]) + '")'
    # return '=HYPERLINK(' + chunks + ', "View")'
    if len(url) > 255:
        return url
    return '=HYPERLINK("' + url + '", "Click to view")'

def snippet(content, length=100, suffix='...'):
    if content == None:
        return ""
    content = strip_html(content)
    content = content.replace('\n', ' ').replace('\r', '').strip()
    content = escape_leading_symbols_for_excel(content)
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length+1].split(' ')[:-1]) + suffix

def round_score(score, ndigits=0):
    """
    Round score to ndigits digits after decimal point
    """
    return round(score, ndigits)

def round_grade(grade, ndigits=0):
    """
    Round grade to ndigits digits after decimal point
    """
    return round(grade, ndigits)

def attachment_url(file):
    """
    Generate url from attachment File
    """
    if not file:
        return ''
    return url_for('file_retrieve', file_type='attachment', file_name=file.name, _external=True)

def datetime_to_string(datetime):
    if not datetime:
        return 'N/A'
    return datetime.strftime("%Y-%m-%d %H:%M:%S")
