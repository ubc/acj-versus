import datetime

import dateutil.parser
from bouncer.constants import MANAGE, READ, CREATE, EDIT, DELETE
from flask import Blueprint, current_app
from flask_restful import Resource, marshal_with, marshal, reqparse
from flask_login import login_required, current_user
from sqlalchemy import exc, func
from flask_restplus import abort

from . import dataformat
from compair.authorization import require
from compair.core import db, event
from compair.models import Course, CourseRole, UserCourse, Answer, \
    Assignment, AssignmentCriterion, File, ComparisonExample
from .util import pagination, new_restful_api, get_model_changes

course_api = Blueprint('course_api', __name__)
api = new_restful_api(course_api)

new_course_parser = reqparse.RequestParser()
new_course_parser.add_argument('name', required=True, help='Course name is required.')
new_course_parser.add_argument('year', type=int, required=True, help='Course year is required.')
new_course_parser.add_argument('term', required=True, help='Course term/semester is required.')
new_course_parser.add_argument('start_date', default=None)
new_course_parser.add_argument('end_date', default=None)

existing_course_parser = new_course_parser.copy()
existing_course_parser.add_argument('id', required=True, help='Course id is required.')


duplicate_course_parser = reqparse.RequestParser()
duplicate_course_parser.add_argument('name', required=True, help='Course name is required.')
duplicate_course_parser.add_argument('year', type=int, required=True, help='Course year is required.')
duplicate_course_parser.add_argument('term', required=True, help='Course term/semester is required.')
duplicate_course_parser.add_argument('start_date', default=None)
duplicate_course_parser.add_argument('end_date', default=None)
# has to add location parameter, otherwise MultiDict will screw up the list
duplicate_course_parser.add_argument('assignments', type=list, default=[], location='json') #only ids and dates

# events
on_course_modified = event.signal('COURSE_MODIFIED')
on_course_get = event.signal('COURSE_GET')
on_course_delete = event.signal('COURSE_DELETE')
on_course_list_get = event.signal('COURSE_LIST_GET')
on_course_create = event.signal('COURSE_CREATE')
on_course_duplicate = event.signal('COURSE_DUPLICATE')


class CourseListAPI(Resource):
    @login_required
    def post(self):
        """
        Create new course
        """
        require(CREATE, Course,
            title="Course Creation Failed",
            message="You do not have permission to create a course since you are not an instructor.")
        params = new_course_parser.parse_args()

        new_course = Course(
            name=params.get("name"),
            year=params.get("year"),
            term=params.get("term"),
            start_date=params.get('start_date', None),
            end_date=params.get('end_date', None)
        )
        if new_course.start_date is not None:
            new_course.start_date = datetime.datetime.strptime(
                new_course.start_date,
                '%Y-%m-%dT%H:%M:%S.%fZ')

        if new_course.end_date is not None:
            new_course.end_date = datetime.datetime.strptime(
                new_course.end_date,
                '%Y-%m-%dT%H:%M:%S.%fZ')

        if new_course.start_date and new_course.end_date and new_course.start_date > new_course.end_date:
            abort(400, title="Course Not Saved", message="Course end time must be after course start time.")

        try:
            # create the course
            db.session.add(new_course)
            # also need to enrol the user as an instructor
            new_user_course = UserCourse(
                course=new_course,
                user_id=current_user.id,
                course_role=CourseRole.instructor
            )
            db.session.add(new_user_course)

            db.session.commit()

        except exc.SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error("Failed to add new course. " + str(e))
            raise

        on_course_create.send(
            self,
            event_name=on_course_create.name,
            user=current_user,
            course=new_course,
            data=marshal(new_course, dataformat.get_course()))

        return marshal(new_course, dataformat.get_course())


api.add_resource(CourseListAPI, '')


#/course_uuid
class CourseAPI(Resource):
    @login_required
    def get(self, course_uuid):
        course = Course.get_active_by_uuid_or_404(course_uuid)
        require(READ, course,
            title="Failed to Retrieve Course",
            message="You do not have permission to view this course since you are not enrolled in it.")

        on_course_get.send(
            self,
            event_name=on_course_get.name,
            user=current_user,
            data={'id': course.id})
        return marshal(course, dataformat.get_course())

    @login_required
    def post(self, course_uuid):
        course = Course.get_active_by_uuid_or_404(course_uuid)
        require(EDIT, course,
            title="Course Update Failed",
            message="You do not have permission to update this course since you are not its instructor.")

        params = existing_course_parser.parse_args()

        # make sure the course id in the url and the course id in the params match
        if params['id'] != course_uuid:
            abort(400, title="Course Update Failed", message="Course id does not match URL.")

        # modify course according to new values, preserve original values if values not passed
        course.name = params.get("name", course.name)
        course.year = params.get("year", course.year)
        course.term = params.get("term", course.term)

        course.start_date = params.get("start_date", None)
        if course.start_date is not None:
            course.start_date = datetime.datetime.strptime(
                course.start_date,
                '%Y-%m-%dT%H:%M:%S.%fZ')

        course.end_date = params.get("end_date", None)
        if course.end_date is not None:
            course.end_date = datetime.datetime.strptime(
                course.end_date,
                '%Y-%m-%dT%H:%M:%S.%fZ')

        if course.start_date and course.end_date and course.start_date > course.end_date:
            return {"error": 'Course end time must be after course start time'}, 400

        db.session.commit()

        on_course_modified.send(
            self,
            event_name=on_course_modified.name,
            user=current_user,
            course=course,
            data=get_model_changes(course))

        return marshal(course, dataformat.get_course())

    @login_required
    def delete(self, course_uuid):
        course = Course.get_active_by_uuid_or_404(course_uuid)
        require(DELETE, course,
            title="Course Deletion Failed",
            message="You do not have permission to delete this course since you are not its instructor.")

        course.active = False
        db.session.commit()

        on_course_delete.send(
            self,
            event_name=on_course_delete.name,
            user=current_user,
            course=course,
            data={'id': course.id})

        return {'id': course.uuid}

api.add_resource(CourseAPI, '/<course_uuid>')

# /course/:course_uuid/duplicate
class CourseDuplicateAPI(Resource):
    @login_required
    def post(self, course_uuid):
        """
        Duplicate a course
        """
        course = Course.get_active_by_uuid_or_404(course_uuid)
        require(EDIT, course,
            title="Course Duplication Failed",
            message="You do not have permission to duplicate this course since you are not its instructor.")

        params = duplicate_course_parser.parse_args()

        start_date = datetime.datetime.strptime(
            params.get("start_date"), '%Y-%m-%dT%H:%M:%S.%fZ'
        ) if params.get("start_date") else None

        end_date = datetime.datetime.strptime(
            params.get("end_date"), '%Y-%m-%dT%H:%M:%S.%fZ'
        ) if params.get("end_date") else None

        if start_date and end_date and start_date > end_date:
            abort(400, title="Course Not Saved", message="Course end time must be after course start time.")

        assignments = [assignment for assignment in course.assignments if assignment.active]
        assignments_copy_data = params.get("assignments")

        if len(assignments) != len(assignments_copy_data):
            abort(400, title="Course Duplication Failed", message="Not enough assignment data provided to duplication course.")

        for assignment_copy_data in assignments_copy_data:
            if not assignment_copy_data.get('answer_start'):
                abort(400, title="Course Duplication Failed", message="No answer start date provided for assignment "+assignment_copy_data.id+".")

            if not assignment_copy_data.get('answer_end'):
                abort(400, title="Course Duplication Failed", message="No answer end date provided for assignment "+assignment_copy_data.id+".")

            assignment_copy_data['answer_start'] = datetime.datetime.strptime(
                assignment_copy_data.get('answer_start'), '%Y-%m-%dT%H:%M:%S.%fZ')

            assignment_copy_data['answer_end'] = datetime.datetime.strptime(
                assignment_copy_data.get('answer_end'), '%Y-%m-%dT%H:%M:%S.%fZ')

            if assignment_copy_data.get('compare_start'):
                assignment_copy_data['compare_start'] = datetime.datetime.strptime(
                    assignment_copy_data.get('compare_start'), '%Y-%m-%dT%H:%M:%S.%fZ')

            if assignment_copy_data.get('compare_end'):
                assignment_copy_data['compare_end'] = datetime.datetime.strptime(
                    assignment_copy_data.get('compare_end'), '%Y-%m-%dT%H:%M:%S.%fZ')

            valid, error_message = Assignment.validate_periods(start_date, end_date,
                assignment_copy_data.get('answer_start'), assignment_copy_data.get('answer_end'),
                assignment_copy_data.get('compare_start'), assignment_copy_data.get('compare_end'))
            if not valid:
                error_message = error_message.replace(".", "") + " for assignment "+assignment_copy_data.get('name', '')
                abort(400, title="Course Not Saved", message=error_message)

        # duplicate course
        duplicate_course = Course(
            name=params.get("name"),
            year=params.get("year"),
            term=params.get("term"),
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(duplicate_course)

        # also need to enrol the user as an instructor
        new_user_course = UserCourse(
            course=duplicate_course,
            user_id=current_user.id,
            course_role=CourseRole.instructor
        )
        db.session.add(new_user_course)

        # duplicate assignments
        for assignment in assignments:
            # this should never be null due
            assignment_copy_data = next((assignment_copy_data
                for assignment_copy_data in assignments_copy_data
                if assignment_copy_data.get('id') == assignment.uuid),
                None
            )

            if not assignment_copy_data:
                abort(400, title="Course Duplication Failed", message="No assignment data provided for assignment "+assignment.uuid+".")

            duplicate_assignment = Assignment(
                course=duplicate_course,
                user_id=current_user.id,
                file=assignment.file,
                name=assignment.name,
                description=assignment.description,

                answer_start=assignment_copy_data.get('answer_start'),
                answer_end=assignment_copy_data.get('answer_end'),
                compare_start=assignment_copy_data.get('compare_start'),
                compare_end=assignment_copy_data.get('compare_end'),

                #TODO: uncomment when grade pull request is accepted
                #answer_grade_weight=assignment.answer_grade_weight,
                #comparison_grade_weight=assignment.comparison_grade_weight,
                #self_evaluation_grade_weight=assignment.self_evaluation_grade_weight,

                number_of_comparisons=assignment.number_of_comparisons,
                students_can_reply=assignment.students_can_reply,
                enable_self_evaluation=assignment.enable_self_evaluation,
                pairing_algorithm=assignment.pairing_algorithm
            )
            db.session.add(duplicate_assignment)

            # duplicate assignment criteria
            for assignment_criterion in assignment.assignment_criteria:
                if not assignment_criterion.active:
                    continue

                duplicate_assignment_criterion = AssignmentCriterion(
                    assignment=duplicate_assignment,
                    criterion_id=assignment_criterion.criterion_id
                )
                db.session.add(duplicate_assignment_criterion)

            # duplicate assignment comparisons examples
            for comparison_example in assignment.comparison_examples:
                answer1 = comparison_example.answer1
                answer2 = comparison_example.answer2

                # duplicate assignemnt comparisons example answers
                duplicate_answer1 = Answer(
                    assignment=duplicate_assignment,
                    user_id=current_user.id,
                    file=answer1.file,
                    content=answer1.content,
                    practice=answer1.practice,
                    active=answer1.active,
                    draft=answer1.draft
                )
                db.session.add(duplicate_answer1)

                # duplicate assignemnt comparisons example answers
                duplicate_answer2 = Answer(
                    assignment=duplicate_assignment,
                    user_id=current_user.id,
                    file=answer2.file,
                    content=answer2.content,
                    practice=answer2.practice,
                    active=answer2.active,
                    draft=answer2.draft
                )
                db.session.add(duplicate_answer2)

                duplicate_comparison_example = ComparisonExample(
                    assignment=duplicate_assignment,
                    answer1=duplicate_answer1,
                    answer2=duplicate_answer2
                )
                db.session.add(duplicate_comparison_example)

        db.session.commit()

        on_course_duplicate.send(
            self,
            event_name=on_course_duplicate.name,
            user=current_user,
            course=duplicate_course,
            data=marshal(course, dataformat.get_course()))

        return marshal(duplicate_course, dataformat.get_course())

api.add_resource(CourseDuplicateAPI, '/<course_uuid>/duplicate')