from bouncer.constants import CREATE, READ, EDIT, MANAGE, DELETE
from flask import Blueprint, abort
from flask.ext.login import login_required, current_user
from flask.ext.restful import Resource, marshal
from flask.ext.restful.reqparse import RequestParser
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload, undefer_group
from itertools import groupby
from operator import attrgetter

from . import dataformat
from acj.core import db, event
from acj.authorization import require, allow, is_user_access_restricted
from acj.models import Answer, Assignment, Course, User, Comparison, \
    Score, UserCourse, CourseRole, AnswerComment, AnswerCommentType

from .util import new_restful_api, get_model_changes, pagination_parser
from .file import add_new_file, delete_file

answers_api = Blueprint('answers_api', __name__)
api = new_restful_api(answers_api)

new_answer_parser = RequestParser()
new_answer_parser.add_argument('user_id', type=int, default=None)
new_answer_parser.add_argument('content', type=str, default=None)
new_answer_parser.add_argument('file_name', type=str, default=None)
new_answer_parser.add_argument('file_alias', type=str, default=None)
new_answer_parser.add_argument('draft', type=bool, default=False)

existing_answer_parser = new_answer_parser.copy()
existing_answer_parser.add_argument('id', type=int, required=True, help="Answer id is required.")
existing_answer_parser.add_argument('uploadedFile', type=bool, default=False)

answer_list_parser = pagination_parser.copy()
answer_list_parser.add_argument('group', type=str, required=False, default=None)
answer_list_parser.add_argument('author', type=int, required=False, default=None)
answer_list_parser.add_argument('orderBy', type=str, required=False, default=None)
answer_list_parser.add_argument('ids', type=str, required=False, default=None)

answer_comparison_list_parser = pagination_parser.copy()
answer_comparison_list_parser.add_argument('group', type=str, required=False, default=None)
answer_comparison_list_parser.add_argument('author', type=int, required=False, default=None)

flag_parser = RequestParser()
flag_parser.add_argument(
    'flagged', type=bool, required=True,
    help="Expected boolean value 'flagged' is missing."
)


# events
on_answer_modified = event.signal('ANSWER_MODIFIED')
on_answer_get = event.signal('ANSWER_GET')
on_answer_list_get = event.signal('ANSWER_LIST_GET')
on_answer_create = event.signal('ANSWER_CREATE')
on_answer_delete = event.signal('ANSWER_DELETE')
on_answer_flag = event.signal('ANSWER_FLAG')
on_user_answer_get = event.signal('USER_ANSWER_GET')
on_answer_comparisons_get = event.signal('ANSWER_COMPARISONS_GET')

# messages
answer_deadline_message = 'Answer deadline has passed.'

# /
class AnswerRootAPI(Resource):
    @login_required
    def get(self, course_id, assignment_id):
        """
        Return a list of answers for a assignment based on search criteria. The
        list of the answers are paginated. If there is any answers from instructor
        or TA, their answers will be on top of the list.

        :param course_id: course id
        :param assignment_id: assignment id
        :return: list of answers
        """
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)
        require(READ, assignment)
        restrict_user = not allow(MANAGE, assignment)

        params = answer_list_parser.parse_args()

        if restrict_user and not assignment.after_comparing:
            # only the answer from student himself/herself should be returned
            params['author'] = current_user.id

        # this query could be further optimized by reduction the selected columns
        query = Answer.query \
            .options(joinedload('file')) \
            .options(joinedload('user')) \
            .options(joinedload('scores')) \
            .options(undefer_group('counts')) \
            .filter_by(
                assignment_id=assignment_id,
                active=True,
                draft=False
            )

        user_ids = []
        if params['author']:
            query = query.filter(Answer.user_id == params['author'])
            user_ids.append(params['author'])
        elif params['group']:
            # get all user ids in the group
            user_courses = UserCourse.query. \
                filter_by(
                    course_id=course_id,
                    group_name=params['group']
                ). \
                all()
            user_ids = [x.user_id for x in user_courses]

        if params['ids']:
            query = query.filter(Answer.id.in_(params['ids'].split(',')))

        # place instructor and TA's answer at the top of the list
        inst_subquery = Answer.query \
            .with_entities(Answer.id.label('inst_answer')) \
            .join(UserCourse, Answer.user_id == UserCourse.user_id) \
            .filter(and_(
                UserCourse.course_id == course_id,
                UserCourse.course_role == CourseRole.instructor
            ))
        ta_subquery = Answer.query \
            .with_entities(Answer.id.label('ta_answer')) \
            .join(UserCourse, Answer.user_id == UserCourse.user_id) \
            .filter(and_(
                UserCourse.course_id == course_id,
                UserCourse.course_role == CourseRole.teaching_assistant
            ))
        query = query.order_by(Answer.id.in_(inst_subquery).desc(), Answer.id.in_(ta_subquery).desc())

        if params['orderBy'] and len(user_ids) != 1:
            # order answer ids by one criterion and pagination, in case there are multiple criteria in assignment
            # left join on Score and add or condition for criterion_id is None to include all answers
            # that don't have score yet
            query = query.outerjoin(Score) \
                .filter(or_(
                    Score.criterion_id == params['orderBy'],
                    Score.criterion_id.is_(None)
                 ))
            query = query.order_by(Score.score.desc(), Answer.created.desc())
        else:
            query = query.order_by(Answer.created.desc())

        if user_ids:
            query = query.filter(Answer.user_id.in_(user_ids))

        page = query.paginate(params['page'], params['perPage'])

        on_answer_list_get.send(
            self,
            event_name=on_answer_list_get.name,
            user=current_user,
            course_id=course_id,
            data={'assignment_id': assignment_id})

        return {"objects": marshal(page.items, dataformat.get_answer(restrict_user)),
                "page": page.page, "pages": page.pages,
                "total": page.total, "per_page": page.per_page}

    @login_required
    def post(self, course_id, assignment_id):
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)
        if not assignment.answer_grace and not allow(MANAGE, assignment):
            return {'error': answer_deadline_message}, 403
        require(CREATE, Answer(course_id=course_id))
        restrict_user = not allow(MANAGE, assignment)

        answer = Answer(assignment_id=assignment_id)

        params = new_answer_parser.parse_args()
        answer.content = params.get("content")
        answer.draft = params.get("draft")

        file_name = params.get('file_name')
        if not (answer.content or file_name):
            return {"error": "The answer content is empty!"}, 400

        user_id = params.get("user_id")
        # we allow instructor and TA to submit multiple answers for other users in the class
        if user_id and not allow(MANAGE, Answer(course_id=course_id)):
            return {"error": "Only instructors and teaching assistants can submit an answer on behalf of another user."}, 400

        answer.user_id = user_id if user_id else current_user.id

        user_course = UserCourse.query \
            .filter_by(
                course_id=course_id,
                user_id=answer.user_id
            ) \
            .first_or_404()

        # we allow instructor and TA to submit multiple answers for their own,
        # but not for student. Each student can only have one answer.
        instructors_and_tas = [CourseRole.instructor.value, CourseRole.teaching_assistant.value]
        if user_course.course_role.value not in instructors_and_tas:
            # check if there is a previous answer submitted for the student
            prev_answer = Answer.query. \
                filter_by(
                    assignment_id=assignment_id,
                    user_id=answer.user_id,
                    active=True
                ). \
                first()
            if prev_answer:
                return {"error": "An answer has already been submitted."}, 400

        db.session.add(answer)
        db.session.commit()

        on_answer_create.send(
            self,
            event_name=on_answer_create.name,
            user=current_user,
            course_id=course_id,
            data=marshal(answer, dataformat.get_answer(restrict_user)))

        if file_name:
            answer.file_id = add_new_file(params.get('file_alias'), file_name,
                Answer.__name__, answer.id)

            db.session.commit()

        return marshal(answer, dataformat.get_answer(restrict_user))


api.add_resource(AnswerRootAPI, '')


# /id
class AnswerIdAPI(Resource):
    @login_required
    def get(self, course_id, assignment_id, answer_id):
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)

        answer = Answer.get_active_or_404(
            answer_id,
            joinedloads=['file', 'user', 'scores']
        )
        require(READ, answer)
        restrict_user = not allow(MANAGE, assignment)

        on_answer_get.send(
            self,
            event_name=on_answer_get.name,
            user=current_user,
            course_id=course_id,
            data={'assignment_id': assignment_id, 'answer_id': answer_id})

        return marshal(answer, dataformat.get_answer(restrict_user))

    @login_required
    def post(self, course_id, assignment_id, answer_id):
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)
        if not assignment.answer_grace and not allow(MANAGE, assignment):
            return {'error': answer_deadline_message}, 403
        answer = Answer.get_active_or_404(answer_id)
        require(EDIT, answer)
        restrict_user = not allow(MANAGE, assignment)

        params = existing_answer_parser.parse_args()
        # make sure the answer id in the url and the id matches
        if params['id'] != answer_id:
            return {"error": "Answer id does not match the URL."}, 400

        # modify answer according to new values, preserve original values if values not passed
        answer.content = params.get("content")
        # can only change draft status while a draft
        if answer.draft:
            answer.draft = params.get("draft")
        uploaded = params.get('uploadFile')
        file_name = params.get('file_name')
        if not (answer.content or uploaded or file_name):
            return {"error": "The answer content is empty!"}, 400

        db.session.add(answer)
        db.session.commit()

        on_answer_modified.send(
            self,
            event_name=on_answer_modified.name,
            user=current_user,
            course_id=course_id,
            data=get_model_changes(answer))

        if file_name:
            answer.file_id = add_new_file(params.get('file_alias'), file_name,
                Answer.__name__, answer.id)

            db.session.commit()

        return marshal(answer, dataformat.get_answer(restrict_user))

    @login_required
    def delete(self, course_id, assignment_id, answer_id):
        Course.get_active_or_404(course_id)
        Assignment.get_active_or_404(assignment_id)
        answer = Answer.get_active_or_404(answer_id)
        require(DELETE, answer)

        delete_file(answer.file_id)
        answer.file_id = None
        answer.active = False
        db.session.commit()

        on_answer_delete.send(
            self,
            event_name=on_answer_delete.name,
            user=current_user,
            course_id=course_id,
            data={'assignment_id': assignment_id, 'answer_id': answer_id})

        return {'id': answer.id}


api.add_resource(AnswerIdAPI, '/<int:answer_id>')


# /comparisons
class AnswerComparisonsAPI(Resource):
    @login_required
    def get(self, course_id, assignment_id):
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)
        require(READ, assignment)

        can_manage = allow(MANAGE, Comparison(course_id=course_id))
        restrict_user = is_user_access_restricted(current_user)

        params = answer_comparison_list_parser.parse_args()

        # each pagination entry would be one comparison set by a user for the assignment
        comparison_sets = Comparison.query \
            .with_entities(Comparison.user_id, Comparison.answer1_id, Comparison.answer2_id) \
            .filter_by(assignment_id=assignment_id) \
            .group_by(Comparison.user_id, Comparison.answer1_id, Comparison.answer2_id)

        if not can_manage:
            comparison_sets = comparison_sets.filter_by(user_id=current_user.id)
        elif params['author']:
            comparison_sets = comparison_sets.filter_by(user_id=params['author'])
        elif params['group']:
            subquery = User.query \
                .with_entities(User.id) \
                .join('user_courses') \
                .filter_by(group_name=params['group']) \
                .subquery()
            comparison_sets = comparison_sets.filter(Comparison.user_id.in_(subquery))

        page = comparison_sets.paginate(params['page'], params['perPage'])

        results = []

        if page.total:

            # retrieve the comparisons
            conditions = []
            for user_id, answer1_id, answer2_id in page.items:
                conditions.append(and_(
                    Comparison.user_id == user_id,
                    Comparison.answer1_id == answer1_id,
                    Comparison.answer2_id == answer2_id
                ))
            comparisons = Comparison.query \
                .options(joinedload('answer1')) \
                .options(joinedload('answer2')) \
                .options(joinedload('criterion')) \
                .filter_by(completed=True) \
                .filter(or_(*conditions)) \
                .order_by(Comparison.user_id, Comparison.created) \
                .all()

            # retrieve the answer comments
            user_comparioson_answers = {}
            for (user_id, answer1_id, answer2_id), group_set in groupby(comparisons, attrgetter('user_id', 'answer1_id', 'answer2_id')):
                user_answers = user_comparioson_answers.setdefault(user_id, set())
                user_answers.add(answer1_id)
                user_answers.add(answer2_id)

            conditions = []
            for user_id, answer_set in user_comparioson_answers.iteritems():
                conditions.append(and_(
                        AnswerComment.user_id == user_id,
                        AnswerComment.comment_type == AnswerCommentType.evaluation,
                        AnswerComment.answer_id.in_(list(answer_set))
                ))
                conditions.append(and_(
                    AnswerComment.comment_type == AnswerCommentType.self_evaluation,
                    AnswerComment.user_id == user_id
                ))

            answer_comments = AnswerComment.query \
                .filter(or_(*conditions)) \
                .filter_by(draft=False) \
                .all()

            for (user_id, answer1_id, answer2_id), group_set in groupby(comparisons, attrgetter('user_id', 'answer1_id', 'answer2_id')):
                group = list(group_set)
                default = group[0]

                comparison_set = {
                    'course_id': default.course_id,
                    'assignment_id': default.assignment_id,
                    'user_id': default.user_id,

                    'comparisons': [comparison for comparison in group],
                    'answer1_id': default.answer1_id,
                    'answer2_id': default.answer2_id,
                    'answer1': default.answer1,
                    'answer2': default.answer2,

                    'user_fullname': default.user_fullname,
                    'user_displayname': default.user_displayname,
                    'user_avatar': default.user_avatar,

                    'answer1_feedback': [comment for comment in answer_comments if
                        comment.user_id == user_id and
                        comment.answer_id == default.answer1_id and
                        comment.comment_type == AnswerCommentType.evaluation
                    ],
                    'answer2_feedback': [comment for comment in answer_comments if
                        comment.user_id == user_id and
                        comment.answer_id == default.answer2_id and
                        comment.comment_type == AnswerCommentType.evaluation
                    ],
                    'self_evaluation': [comment for comment in answer_comments if
                        comment.user_id == user_id and
                        comment.comment_type == AnswerCommentType.self_evaluation
                    ],

                    'created': default.created
                }

                results.append(comparison_set)

        on_answer_comparisons_get.send(
            self,
            event_name=on_answer_comparisons_get.name,
            user=current_user,
            course_id=course_id,
            data={'assignment_id': assignment_id}
        )

        return {'objects': marshal(results, dataformat.get_comparison_set(restrict_user)), "page": page.page,
                "pages": page.pages, "total": page.total, "per_page": page.per_page}


api.add_resource(AnswerComparisonsAPI, '/comparisons')


# /user
class AnswerUserIdAPI(Resource):
    @login_required
    def get(self, course_id, assignment_id):
        """
        Get answers submitted to the assignment submitted by current user

        :param course_id:
        :param assignment_id:
        :return: answers
        """
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)
        require(READ, Answer(user_id=current_user.id))
        restrict_user = not allow(MANAGE, assignment)

        answers = Answer.query. \
            options(joinedload('comments')). \
            options(joinedload('file')). \
            options(joinedload('user')). \
            options(joinedload('scores')). \
            filter_by(
                active=True,
                assignment_id=assignment_id,
                course_id=course_id,
                user_id=current_user.id
            ). \
            all()

        on_user_answer_get.send(
            self,
            event_name=on_user_answer_get.name,
            user=current_user,
            course_id=course_id,
            data={'assignment_id': assignment_id})

        return {"objects": marshal( answers, dataformat.get_answer(restrict_user))}


api.add_resource(AnswerUserIdAPI, '/user')

# /flag
class AnswerFlagAPI(Resource):
    @login_required
    def post(self, course_id, assignment_id, answer_id):
        """
        Mark an answer as inappropriate or incomplete to instructors
        :param course_id:
        :param assignment_id:
        :param answer_id:
        :return: marked answer
        """
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)
        answer = Answer.get_active_or_404(answer_id)
        require(READ, answer)
        restrict_user = not allow(MANAGE, assignment)

        # anyone can flag an answer, but only the original flagger or someone who can manage
        # the answer can unflag it
        if answer.flagged and answer.flagger_user_id != current_user.id and \
                not allow(MANAGE, answer):
            return {"error": "You do not have permission to unflag this answer."}, 400

        params = flag_parser.parse_args()
        answer.flagged = params['flagged']
        answer.flagger_user_id = current_user.id
        db.session.add(answer)

        on_answer_flag.send(
            self,
            event_name=on_answer_flag.name,
            user=current_user,
            course_id=course_id,
            assignment_id=assignment_id,
            data={'answer_id': answer_id, 'flag': answer.flagged})

        db.session.commit()
        return marshal(answer, dataformat.get_answer(restrict_user))

api.add_resource(AnswerFlagAPI, '/<int:answer_id>/flagged')