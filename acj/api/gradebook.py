from __future__ import division

import copy

from bouncer.constants import MANAGE
from flask import Blueprint, jsonify
from flask.ext.login import login_required, current_user
from flask.ext.restful import Resource
from sqlalchemy import func, and_
from sqlalchemy.orm import load_only, undefer, joinedload

from acj.authorization import require
from acj.models import Course, Assignment, CourseRole, User, UserCourse, Comparison, \
    AnswerComment, Answer, Score
from .util import new_restful_api
from acj.core import event



# First declare a Flask Blueprint for this module
gradebook_api = Blueprint('gradebook_api', __name__)
# Then pack the blueprint into a Flask-Restful API
api = new_restful_api(gradebook_api)

# events
on_gradebook_get = event.signal('GRADEBOOK_GET')


def normalize_score(score, max_score, ndigits=0):
    return round(score / max_score, ndigits) if max_score is not 0 else 0


# declare an API URL
# /
class GradebookAPI(Resource):
    @login_required
    def get(self, course_id, assignment_id):
        Course.get_active_or_404(course_id)
        
        assignment = Assignment.get_active_or_404(
            assignment_id, 
            joinedloads=['criteria']
        )
        require(MANAGE, assignment)

        # get all students in this course
        students = User.query. \
            with_entities(User.id, User.displayname, User.firstname, User.lastname). \
            join(UserCourse, UserCourse.user_id == User.id). \
            filter(
                UserCourse.course_id == course_id,
                UserCourse.course_role == CourseRole.student,
            ). \
            all()
        student_ids = [student.id for student in students]
        
        # get students comparisons counts for this assignment
        comparisons = User.query. \
            with_entities(User.id, func.count(Comparison.id).label('compare_count')). \
            join(Comparison). \
            filter(Comparison.assignment_id == assignment_id).\
            filter(User.id.in_(student_ids)).\
            group_by(User.id).all()

        # we want only the count for comparisons by current students in the course
        num_comparisons_per_student = {user_id: int(compare_count/assignment.criteria_count)
                                      for (user_id, compare_count) in comparisons}

        # find out the scores that students get
        criteria_ids = [c.criteria_id for c in assignment.assignment_criteria]
        stmt = Answer.query. \
            with_entities(Answer.user_id, Answer.flagged, Score.criteria_id, Score.normalized_score.label('ns')). \
            outerjoin(Score, and_(
                Answer.id == Score.answer_id,
                Score.criteria_id.in_(criteria_ids))). \
            filter(Answer.assignment_id == assignment_id). \
            subquery()

        scores_by_user = User.query. \
            with_entities(User.id, stmt.c.flagged, stmt.c.criteria_id, stmt.c.ns). \
            outerjoin(stmt, User.id == stmt.c.user_id). \
            filter(User.id.in_(student_ids)). \
            all()

        # process the results into dicts
        init_scores = {c.criteria_id: 'Not Evaluated' for c in assignment.assignment_criteria}
        scores_by_user_id = {student_id: copy.deepcopy(init_scores) for student_id in student_ids}
        flagged_by_user_id = {}
        num_answers_per_student = {}
        for score in scores_by_user:
            # answer flag exists means there is an answer from a student
            if score[1] is not None:
                flagged_by_user_id[score[0]] = 'Yes' if score[1] else 'No'
                num_answers_per_student[score[0]] = 1
                if score[2] is not None:
                    scores_by_user_id[score[0]][score[2]] = round(score[3], 3)
            else:
                # no answer from the student
                scores_by_user_id[score[0]] = {c.criteria_id: 'No Answer' for c in assignment.assignment_criteria}

        include_self_eval = False
        num_self_eval_per_student = {}
        if assignment.enable_self_eval:
            include_self_eval = True
            # assuming self-evaluation with no comparison
            stmt = AnswerComment.query. \
                with_entities(AnswerComment.user_id, func.count('*').label('comment_count')). \
                filter_by(self_eval=True). \
                join(Answer, and_(
                    Answer.id == AnswerComment.answer_id,
                    Answer.assignment_id == assignment_id)) .\
                group_by(AnswerComment.user_id).subquery()

            comments_by_user_id = User.query. \
                with_entities(User.id, stmt.c.comment_count). \
                outerjoin(stmt, User.id == stmt.c.user_id). \
                filter(User.id.in_(student_ids)). \
                order_by(User.id). \
                all()

            num_self_eval_per_student = dict(comments_by_user_id)
            num_self_eval_per_student.update((k, 0) for k, v in num_self_eval_per_student.items() if v is None)

        # {'gradebook':[{user1}. {user2}, ...]}
        # user id, username, first name, last name, answer submitted, comparisons submitted
        gradebook = []
        no_answer = {c.criteria_id: 'No Answer' for c in assignment.assignment_criteria}
        for student in students:
            entry = {
                'userid': student.id,
                'displayname': student.displayname,
                'firstname': student.firstname,
                'lastname': student.lastname,
                'num_answers': num_answers_per_student.get(student.id, 0),
                'num_comparisons': num_comparisons_per_student.get(student.id, 0),
                'scores': scores_by_user_id.get(student.id, no_answer),
                'flagged': flagged_by_user_id.get(student.id, 'No Answer')
            }
            if include_self_eval:
                entry['num_self_eval'] = num_self_eval_per_student[student.id]
            gradebook.append(entry)

        ret = {
            'gradebook': gradebook,
            'num_comparisons_required': assignment.number_of_comparisons,
            'include_self_eval': include_self_eval
        }

        on_gradebook_get.send(
            self,
            event_name=on_gradebook_get.name,
            user=current_user,
            course_id=course_id,
            data={'assignment_id': assignment_id})

        return jsonify(ret)


api.add_resource(GradebookAPI, '')
