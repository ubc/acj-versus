import os
import time
import unicodecsv as csv
import re
import string

from bouncer.constants import MANAGE
from flask import Blueprint, current_app
from flask_login import login_required, current_user

from flask_restful import Resource, reqparse

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload

from compair.authorization import require
from compair.core import event, abort
from compair.models import User, CourseRole, Assignment, UserCourse, Course, Answer, \
    AnswerComment, AssignmentCriterion, Comparison, AnswerCommentType, Group
from .util import new_restful_api

report_api = Blueprint('report_api', __name__)
api = new_restful_api(report_api)

report_parser = reqparse.RequestParser()
report_parser.add_argument('group_id')
# may change 'type' to int
report_parser.add_argument('type', required=True)
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
                'Assignment', 'User UUID', 'Last Name', 'First Name', 'Answer Submitted', 'Answer ID',
                'Answer', 'Overall Rank', 'Overall Score',
                'Evaluations Submitted', 'Evaluations Required', 'Evaluation Requirements Met',
                'Replies Submitted']
            titles = [title]

        elif report_type == "participation":
            user_titles = ['Last Name', 'First Name', 'Student No']
            data = participation_report(course, assignments, group)

            title_row1 = [""] * len(user_titles)
            title_row2 = user_titles

            for assignment in assignments:
                assignment_criteria = AssignmentCriterion.query \
                    .filter_by(
                        assignment_id=assignment.id,
                        active=True
                    ) \
                    .order_by(AssignmentCriterion.position) \
                    .all()

                title_row1 += [assignment.name] + [""] * len(assignment_criteria)
                title_row2.append('Percentage score for answer overall')
                for assignment_criterion in assignment_criteria:
                    title_row2.append('Percentage score for "' + assignment_criterion.criterion.name + '"')
                title_row2.append("Evaluations Submitted (" + str(assignment.total_comparisons_required) + ' required)')
                if assignment.enable_self_evaluation:
                    title_row1 += [""]
                    title_row2.append("Self Evaluation Submitted")
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
                "Last Name", "First Name", "Student No",
                "Last Name", "First Name", "Student No",
                "Feedback Type", "Feedback"
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
                Answer.active == True,
                Answer.assignment_id == assignment.id,
                Answer.comparable == True,
                Answer.draft == False,
                Answer.practice == False,
                or_(
                    Answer.user_id.in_(class_ids),
                    Answer.group_id.in_(group_ids)
                )
            )) \
            .order_by(Answer.created) \
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
            .with_entities(AnswerComment.user_id, func.count(AnswerComment.id)) \
            .group_by(AnswerComment.user_id) \
            .all()
        comments = {user_id: count for (user_id, count) in comments}

        total_req += assignment.total_comparisons_required  # for overall required

        for user_course in classlist:
            user = user_course.user
            temp = [assignment.name, user.uuid, user.lastname, user.firstname]

            # OVERALL
            total.setdefault(user.id, {
                'total_answers': 0,
                'total_evaluations': 0,
                'total_comments': 0
            })

            # each user has at least 1 line per assignment, regardless whether there is an answer
            submitted = len(user_answers.get(user.id, []))
            the_answer = user_answers[user.id][0] if submitted else None
            answer_uuid = the_answer.uuid if submitted else 'N/A'
            answer_text = snippet(the_answer.content) if submitted else 'N/A'
            answer_rank = the_answer.score.rank if submitted and the_answer.score else 'Not Evaluated'
            answer_score = the_answer.score.normalized_score if submitted and the_answer.score else 'Not Evaluated'
            total[user.id]['total_answers'] += submitted
            temp.extend([submitted, answer_uuid, answer_text, answer_rank, answer_score])

            evaluations = evaluation_submitted.get(user.id, 0)
            evaluation_req_met = 'Yes' if evaluations >= assignment.total_comparisons_required else 'No'
            total[user.id]['total_evaluations'] += evaluations
            temp.extend([evaluations, assignment.total_comparisons_required, evaluation_req_met])

            comment_count = comments[user.id] if user.id in comments else 0
            total[user.id]['total_comments'] += comment_count
            temp.append(comment_count)

            report.append(temp)

            # handle multiple answers from the user (normally only apply for instructors / TAs)
            if submitted > 1:
                for answer in user_answers[user.id][1:]:
                    answer_uuid = answer.uuid
                    answer_text = snippet(answer.content)
                    answer_rank = answer.score.rank if submitted and answer.score else 'Not Evaluated'
                    answer_score = answer.score.normalized_score if submitted and answer.score else 'Not Evaluated'
                    temp = [assignment.name, user.uuid, user.lastname,
                        user.firstname, submitted, answer_uuid, answer_text,
                        answer_rank, answer_score,
                        evaluations, assignment.total_comparisons_required,
                        evaluation_req_met, comment_count]

                    report.append(temp)

    if overall:
        for user_course_student in classlist:
            user = user_course_student.user
            sum_submission = total.setdefault(user.id, {
                'total_answers': 0,
                'total_evaluations': 0,
                'total_comments': 0
            })
            # assume a user can only at most do the required number
            req_met = 'Yes' if sum_submission['total_evaluations'] >= total_req else 'No'
            temp = [
                '(Overall in Course)', user.uuid, user.lastname, user.firstname,
                sum_submission['total_answers'], '', '',
                '', '',
                sum_submission['total_evaluations'], total_req, req_met,
                sum_submission['total_comments']]
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

    # SELF-EVALUATION - assuming no comparions
    self_evaluation = AnswerComment.query \
        .filter_by(comment_type=AnswerCommentType.self_evaluation) \
        .join(Answer) \
        .filter(Answer.assignment_id.in_(assignment_ids)) \
        .filter(AnswerComment.user_id.in_(class_ids)) \
        .filter(AnswerComment.draft == False) \
        .with_entities(Answer.assignment_id, AnswerComment.user_id, func.count(AnswerComment.id)) \
        .group_by(Answer.assignment_id, AnswerComment.user_id) \
        .all()

    comments = {}  # structure - user_id/assignment_id/count
    for (assignment_id, user_id, count) in self_evaluation:
        comments.setdefault(user_id, {}).setdefault(assignment_id, 0)
        comments[user_id][assignment_id] = count

    for user_courses in classlist:
        user = user_courses.user
        temp = [user.lastname, user.firstname, user.student_number]

        for assignment in assignments:
            if user.id not in scores or assignment.id not in scores[user.id]:
                score = 'No Answer'
            elif scores[user.id][assignment.id] == None:
                score = 'Not Evaluated'
            else:
                score = scores[user.id][assignment.id]
            temp.append(score)

            for criterion in criteria[assignment.id]:
                if user.id not in criteria_scores or assignment.id not in criteria_scores[user.id]:
                    criterion_score = 'No Answer'
                elif criterion not in criteria_scores[user.id][assignment.id]:
                    criterion_score = 'Not Evaluated'
                else:
                    criterion_score = criteria_scores[user.id][assignment.id][criterion]
                temp.append(criterion_score)
            if user.id not in comparisons or assignment.id not in comparisons[user.id]:
                compared = 0
            else:
                compared = comparisons[user.id][assignment.id]
            temp.append(str(compared))
            # self-evaluation
            if assignment.enable_self_evaluation:
                if user.id not in comments or assignment.id not in comments[user.id]:
                    temp.append(0)
                else:
                    temp.append(comments[user.id][assignment.id])
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

                    temp += [feedback_type, strip_html(feedback.content)]

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
    text = re.sub('<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', '\'')
    return text

def snippet(content, length=100, suffix='...'):
    if content == None:
        return ""
    content = strip_html(content)
    content = content.replace('\n', ' ').replace('\r', '').strip()
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length+1].split(' ')[:-1]) + suffix