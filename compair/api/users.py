from flask import Blueprint, current_app, session as sess
from bouncer.constants import MANAGE, EDIT, CREATE, READ
from flask_restful import Resource, marshal
from flask_restful.reqparse import RequestParser
from flask_login import login_required, current_user
from sqlalchemy.orm import load_only
from sqlalchemy import exc, asc, or_, and_, func, desc, asc
from six import text_type

from . import dataformat
from compair.authorization import is_user_access_restricted, require, allow
from compair.core import db, event, abort
from .util import new_restful_api, get_model_changes, pagination_parser
from compair.models import User, SystemRole, Course, UserCourse, CourseRole, \
    Assignment, LTIUser, LTIUserResourceLink, LTIContext, ThirdPartyUser, ThirdPartyType, \
    Answer, Comparison, AnswerComment, AnswerCommentType
from compair.api.login import authenticate

user_api = Blueprint('user_api', __name__)

def non_blank_text(value):
    if value is None:
        return None
    else:
        return None if text_type(value).strip() == "" else text_type(value)

new_user_parser = RequestParser()
new_user_parser.add_argument('username', type=non_blank_text, required=False)
new_user_parser.add_argument('student_number', type=non_blank_text)
new_user_parser.add_argument('system_role', required=True)
new_user_parser.add_argument('firstname', required=True)
new_user_parser.add_argument('lastname', required=True)
new_user_parser.add_argument('displayname', required=True)
new_user_parser.add_argument('email')
new_user_parser.add_argument('password', required=False)

existing_user_parser = RequestParser()
existing_user_parser.add_argument('id', required=True)
existing_user_parser.add_argument('username', type=non_blank_text, required=False)
existing_user_parser.add_argument('student_number', type=non_blank_text)
existing_user_parser.add_argument('system_role', required=True)
existing_user_parser.add_argument('firstname', required=True)
existing_user_parser.add_argument('lastname', required=True)
existing_user_parser.add_argument('displayname', required=True)
existing_user_parser.add_argument('email')

update_password_parser = RequestParser()
update_password_parser.add_argument('oldpassword', required=False)
update_password_parser.add_argument('newpassword', required=True)

user_list_parser = pagination_parser.copy()
user_list_parser.add_argument('search', required=False, default=None)
user_list_parser.add_argument('orderBy', required=False, default=None)
user_list_parser.add_argument('reverse', type=bool, default=False)
user_list_parser.add_argument('ids', required=False, default=None)

user_course_list_parser = pagination_parser.copy()
user_course_list_parser.add_argument('search', required=False, default=None)

user_id_course_list_parser = pagination_parser.copy()
user_id_course_list_parser.add_argument('search', required=False, default=None)
user_id_course_list_parser.add_argument('orderBy', required=False, default=None)
user_id_course_list_parser.add_argument('reverse', type=bool, default=False)

user_course_status_list_parser = RequestParser()
user_course_status_list_parser.add_argument('ids', required=True, default=None)

# events
on_user_modified = event.signal('USER_MODIFIED')
on_user_get = event.signal('USER_GET')
on_user_list_get = event.signal('USER_LIST_GET')
on_user_create = event.signal('USER_CREATE')
on_user_course_get = event.signal('USER_COURSE_GET')
on_user_course_status_get = event.signal('USER_COURSE_STATUS_GET')
on_teaching_course_get = event.signal('USER_TEACHING_COURSE_GET')
on_user_edit_button_get = event.signal('USER_EDIT_BUTTON_GET')
on_user_password_update = event.signal('USER_PASSWORD_UPDATE')

def check_valid_system_role(system_role, title=None):
    system_roles = [
        SystemRole.sys_admin.value,
        SystemRole.instructor.value,
        SystemRole.student.value
    ]
    if system_role not in system_roles:
        abort(400, title=title, message="Please select a valid system role from the list provided.")

# /user_uuid
class UserAPI(Resource):
    @login_required
    def get(self, user_uuid):
        user = User.get_by_uuid_or_404(user_uuid)

        on_user_get.send(
            self,
            event_name=on_user_get.name,
            user=current_user,
            data={'id': user.id}
        )
        return marshal(user, dataformat.get_user(is_user_access_restricted(user)))

    @login_required
    def post(self, user_uuid):
        user = User.get_by_uuid_or_404(user_uuid)

        if is_user_access_restricted(user):
            abort(403, title="Account Not Updated", message="Your system role does not allow you to update this account.")

        params = existing_user_parser.parse_args()

        # make sure the user id in the url and the id matches
        if params['id'] != user_uuid:
            abort(400, title="Account Not Updated",
                message="The account's ID does not match the URL, which is required in order to update the account.")

        # only update username if user uses compair login method
        if user.uses_compair_login:
            username = params.get("username")
            if username == None:
                abort(400, title="Account Not Updated", message="The required field username is missing.")
            username_exists = User.query.filter_by(username=username).first()
            if username_exists and username_exists.id != user.id:
                abort(409, title="Account Not Updated", message="This username already exists. Please pick another.")

            user.username = username
        elif allow(MANAGE, user):
            #admins can optionally set username for users without a username
            username = params.get("username")
            if username:
                username_exists = User.query.filter_by(username=username).first()
                if username_exists and username_exists.id != user.id:
                    abort(409, title="Account Not Updated", message="This username already exists. Please pick another.")
            user.username = username
        else:
            user.username = None

        if allow(MANAGE, user):
            system_role = params.get("system_role", user.system_role.value)
            check_valid_system_role(system_role, title="Account Not Updated")
            user.system_role = SystemRole(system_role)

        # only students should have student numbers
        if user.system_role == SystemRole.student:
            student_number = params.get("student_number", user.student_number)
            student_number_exists = User.query.filter_by(student_number=student_number).first()
            if student_number is not None and student_number_exists and student_number_exists.id != user.id:
                abort(409, title="Account Not Updated", message="This student number already exists. Please pick another.")
            else:
                user.student_number = student_number
        else:
            user.student_number = None

        user.firstname = params.get("firstname", user.firstname)
        user.lastname = params.get("lastname", user.lastname)
        user.displayname = params.get("displayname", user.displayname)

        user.email = params.get("email", user.email)
        changes = get_model_changes(user)

        restrict_user = not allow(EDIT, user)

        try:
            db.session.commit()
            on_user_modified.send(
                self,
                event_name=on_user_modified.name,
                user=current_user,
                data={'id': user.id, 'changes': changes})
        except exc.IntegrityError:
            db.session.rollback()
            abort(409, title="Account Not Updated", message="A user with the same identifier already exists.")

        return marshal(user, dataformat.get_user(restrict_user))

# /
class UserListAPI(Resource):
    @login_required
    def get(self):
        restrict_user = not allow(READ, User)

        params = user_list_parser.parse_args()

        query = User.query
        if params['search']:
            # match each word of search
            for word in params['search'].strip().split(' '):
                if word != '':
                    search = '%'+word+'%'
                    query = query.filter(or_(
                        User.firstname.like(search),
                        User.lastname.like(search),
                        User.displayname.like(search)
                    ))

        if params['orderBy']:
            if params['reverse']:
                query = query.order_by(desc(params['orderBy']))
            else:
                query = query.order_by(asc(params['orderBy']))
        query.order_by(User.firstname.asc(), User.lastname.asc())

        page = query.paginate(params['page'], params['perPage'])

        on_user_list_get.send(
            self,
            event_name=on_user_list_get.name,
            user=current_user)

        return {"objects": marshal(page.items, dataformat.get_user(restrict_user)), "page": page.page,
                "pages": page.pages, "total": page.total, "per_page": page.per_page}

    def post(self):
        # login_required when oauth_create_user_link not set
        if not sess.get('oauth_create_user_link'):
            if not current_app.login_manager._login_disabled and \
                    not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()

        user = User()
        params = new_user_parser.parse_args()
        user.student_number = params.get("student_number", None)
        user.email = params.get("email")
        user.firstname = params.get("firstname")
        user.lastname = params.get("lastname")
        user.displayname = params.get("displayname")

        # if creating a cas user, do not set username or password
        if sess.get('oauth_create_user_link') and sess.get('LTI') and sess.get('CAS_CREATE'):
            user.username = None
            user.password = None
        else:
            # else enforce required password and unique username
            user.password = params.get("password")
            if user.password == None:
                abort(400, title="Account Not Saved", message="The required field password is missing.")

            user.username = params.get("username")
            if user.username == None:
                abort(400, title="Account Not Saved", message="The required field username is missing.")

            username_exists = User.query.filter_by(username=user.username).first()
            if username_exists:
                abort(409, title="Account Not Saved", message="This username already exists. Please pick another.")

        student_number_exists = User.query.filter_by(student_number=user.student_number).first()
        # if student_number is not left blank and it exists -> 409 error
        if user.student_number is not None and student_number_exists:
            abort(409, title="Account Not Saved", message="This student number already exists. Please pick another.")

        # handle oauth_create_user_link setup for third party logins
        if sess.get('oauth_create_user_link'):
            login_method = None

            if sess.get('LTI'):
                lti_user = LTIUser.query.get_or_404(sess['lti_user'])
                lti_user.compair_user = user
                user.system_role = lti_user.system_role
                login_method = 'LTI'

                if sess.get('lti_context') and sess.get('lti_user_resource_link'):
                    lti_context = LTIContext.query.get_or_404(sess['lti_context'])
                    lti_user_resource_link = LTIUserResourceLink.query.get_or_404(sess['lti_user_resource_link'])
                    if lti_context.is_linked_to_course():
                        # create new enrollment
                        new_user_course = UserCourse(
                            user=user,
                            course_id=lti_context.compair_course_id,
                            course_role=lti_user_resource_link.course_role
                        )
                        db.session.add(new_user_course)

                if sess.get('CAS_CREATE'):
                    thirdpartyuser = ThirdPartyUser(
                        third_party_type=ThirdPartyType.cas,
                        unique_identifier=sess.get('CAS_UNIQUE_IDENTIFIER'),
                        params=sess.get('CAS_PARAMS'),
                        user=user
                    )
                    login_method = ThirdPartyType.cas.value
                    db.session.add(thirdpartyuser)
        else:
            system_role = params.get("system_role")
            check_valid_system_role(system_role, title="Account Not Saved")
            user.system_role = SystemRole(system_role)

            require(CREATE, user,
                title="Account Not Saved",
                message="Your system role does not allow you to create accounts.")

        # only students can have student numbers
        if user.system_role != SystemRole.student:
            user.student_number = None

        try:
            db.session.add(user)
            db.session.commit()
            if current_user.is_authenticated:
                on_user_create.send(
                    self,
                    event_name=on_user_create.name,
                    user=current_user,
                    data=marshal(user, dataformat.get_user(False)))
            else:
                on_user_create.send(
                    self,
                    event_name=on_user_create.name,
                    data=marshal(user, dataformat.get_user(False)))

        except exc.IntegrityError:
            db.session.rollback()
            current_app.logger.error("Failed to add new user. Duplicate.")
            abort(409, title="Account Not Saved", message="A user with the same identifier already exists.")

        # handle oauth_create_user_link teardown for third party logins
        if sess.get('oauth_create_user_link'):
            authenticate(user, login_method=login_method)
            sess.pop('oauth_create_user_link')

            if sess.get('CAS_CREATE'):
                sess.pop('CAS_CREATE')
                sess.pop('CAS_UNIQUE_IDENTIFIER')
                sess['CAS_LOGIN'] = True

        return marshal(user, dataformat.get_user())


# /courses
class CurrentUserCourseListAPI(Resource):
    @login_required
    def get(self):
        params = user_course_list_parser.parse_args()

        # Note, start and end dates are optional so default sort is by start_date (course.start_date or min assignment start date), then name
        query = Course.query \
            .filter_by(active=True) \
            .order_by(Course.start_date_order.desc(), Course.name) \

        # we want to list user linked courses only, so only check the association table
        if not allow(MANAGE, Course):
            query = query.join(UserCourse) \
                .filter(and_(
                    UserCourse.user_id == current_user.id,
                    UserCourse.course_role != CourseRole.dropped
                ))

        if params['search']:
            search_terms = params['search'].split()
            for search_term in search_terms:
                if search_term != "":
                    search = '%'+search_term+'%'
                    query = query.filter(or_(
                        Course.name.like(search),
                        Course.year.like(search),
                        Course.term.like(search)
                    ))
        page = query.paginate(params['page'], params['perPage'])

        # TODO REMOVE COURSES WHERE COURSE IS UNAVAILABLE?

        on_user_course_get.send(
            self,
            event_name=on_user_course_get.name,
            user=current_user)

        return {"objects": marshal(page.items, dataformat.get_course()),
                "page": page.page, "pages": page.pages,
                "total": page.total, "per_page": page.per_page}

# /id/courses
class UserCourseListAPI(Resource):
    @login_required
    def get(self, user_uuid):
        user = User.get_by_uuid_or_404(user_uuid)

        require(MANAGE, User,
            title="User's Courses Unavailable",
            message="Your system role does not allow you to view courses for this user.")

        params = user_id_course_list_parser.parse_args()

        query = Course.query \
            .join(UserCourse) \
            .add_columns(UserCourse.course_role, UserCourse.group_name) \
            .filter(and_(
                Course.active == True,
                UserCourse.user_id == user.id,
                UserCourse.course_role != CourseRole.dropped
            ))

        if params['search']:
            search_terms = params['search'].split()
            for search_term in search_terms:
                if search_term != "":
                    search = '%'+search_term+'%'
                    query = query.filter(or_(
                        Course.name.like(search),
                        Course.year.like(search),
                        Course.term.like(search)
                    ))

        if params['orderBy']:
            if params['reverse']:
                query = query.order_by(desc(params['orderBy']))
            else:
                query = query.order_by(asc(params['orderBy']))
        query = query.order_by(Course.start_date_order.desc(), Course.name)

        page = query.paginate(params['page'], params['perPage'])

        # fix results
        courses = []
        for (_course, _course_role, _group_name) in page.items:
            _course.course_role = _course_role
            _course.group_name = _group_name
            courses.append(_course)
        page.items = courses

        on_user_course_get.send(
            self,
            event_name=on_user_course_get.name,
            user=user)

        return {"objects": marshal(page.items, dataformat.get_user_courses()),
                "page": page.page, "pages": page.pages,
                "total": page.total, "per_page": page.per_page}

# /courses/status
class UserCourseStatusListAPI(Resource):
    @login_required
    def get(self):
        params = user_course_status_list_parser.parse_args()
        course_uuids = params['ids'].split(',')

        if params['ids'] == '' or len(course_uuids) == 0:
            abort(400, title="Course Status Unavailable", message="Please select a valid course.")

        query = Course.query \
            .filter(and_(
                Course.uuid.in_(course_uuids),
                Course.active == True,
            )) \
            .add_columns(UserCourse.course_role) \

        if not allow(MANAGE, Course):
            query = query.join(UserCourse, and_(
                    UserCourse.user_id == current_user.id,
                    UserCourse.course_id == Course.id,
                    UserCourse.course_role != CourseRole.dropped
                ))
        else:
            query = query.outerjoin(UserCourse, and_(
                    UserCourse.user_id == current_user.id,
                    UserCourse.course_id == Course.id
                ))

        results = query.all()

        if len(course_uuids) != len(results):
            abort(400, title="Course Status Unavailable",
                message="Your are not enrolled in one or more users selected courses yet.")

        statuses = {}

        for course, course_role in results:
            incomplete_assignment_ids = set()
            answer_period_assignments = [assignment for assignment in course.assignments if assignment.active and assignment.answer_period]
            compare_period_assignments = [assignment for assignment in course.assignments if assignment.active and assignment.compare_period]

            if not allow(MANAGE, Course) and course_role == CourseRole.student:
                if len(answer_period_assignments) > 0:
                    answer_period_assignment_ids = [assignment.id for assignment in answer_period_assignments]
                    answers = Answer.query \
                        .filter(and_(
                            Answer.user_id == current_user.id,
                            Answer.assignment_id.in_(answer_period_assignment_ids),
                            Answer.active == True,
                            Answer.practice == False,
                            Answer.draft == False
                        ))
                    for assignment in answer_period_assignments:
                        answer = next(
                            (answer for answer in answers if answer.assignment_id == assignment.id),
                            None
                        )
                        if answer is None:
                            incomplete_assignment_ids.add(assignment.id)

                if len(compare_period_assignments) > 0:
                    compare_period_assignment_ids = [assignment.id for assignment in compare_period_assignments]
                    comparisons = Comparison.query \
                        .filter(and_(
                            Comparison.user_id == current_user.id,
                            Comparison.assignment_id.in_(compare_period_assignment_ids),
                            Comparison.completed == True
                        ))

                    self_evaluations = AnswerComment.query \
                        .join("answer") \
                        .with_entities(
                            Answer.assignment_id,
                            func.count(Answer.assignment_id).label('self_evaluation_count')
                        ) \
                        .filter(and_(
                            AnswerComment.user_id == current_user.id,
                            AnswerComment.active == True,
                            AnswerComment.comment_type == AnswerCommentType.self_evaluation,
                            AnswerComment.draft == False,
                            Answer.active == True,
                            Answer.practice == False,
                            Answer.draft == False,
                            Answer.assignment_id.in_(compare_period_assignment_ids)
                        )) \
                        .group_by(Answer.assignment_id) \
                        .all()

                    for assignment in compare_period_assignments:
                        assignment_comparisons = [comparison for comparison in comparisons if comparison.assignment_id == assignment.id]
                        if len(assignment_comparisons) < assignment.total_comparisons_required:
                            incomplete_assignment_ids.add(assignment.id)

                        if assignment.enable_self_evaluation:
                            self_evaluation_count = next(
                                (result.self_evaluation_count for result in self_evaluations if result.assignment_id == assignment.id),
                                0
                            )
                            if self_evaluation_count == 0:
                                incomplete_assignment_ids.add(assignment.id)

            statuses[course.uuid] = {
                'incomplete_assignments': len(incomplete_assignment_ids)
            }

        on_user_course_status_get.send(
            self,
            event_name=on_user_course_status_get.name,
            user=current_user,
            data=statuses)

        return {"statuses": statuses}

# courses/teaching
class TeachingUserCourseListAPI(Resource):
    @login_required
    def get(self):
        if allow(MANAGE, Course()):
            courses = Course.query.filter_by(active=True).all()
        else:
            courses = []
            for user_course in current_user.user_courses:
                if user_course.course.active and allow(MANAGE, Assignment(course_id=user_course.course_id)):
                    courses.append(user_course.course)

        course_list = [{'id': c.uuid, 'name': c.name} for c in courses]

        on_teaching_course_get.send(
            self,
            event_name=on_teaching_course_get.name,
            user=current_user
        )

        return {'courses': course_list}

# /user_uuid/edit
class UserEditButtonAPI(Resource):
    @login_required
    def get(self, user_uuid):
        user = User.get_by_uuid_or_404(user_uuid)
        available = allow(EDIT, user)

        on_user_edit_button_get.send(
            self,
            event_name=on_user_edit_button_get.name,
            user=current_user,
            data={'user_id': user.id, 'available': available})

        return {'available': available}

# /password
class UserUpdatePasswordAPI(Resource):
    @login_required
    def post(self, user_uuid):
        user = User.get_by_uuid_or_404(user_uuid)
        # anyone who passes checking below should be an instructor or admin
        require(EDIT, user,
            title="Password Not Updated",
            message="Your system role does not allow you to update passwords for this account.")

        if not user.uses_compair_login:
            abort(400, title="Password Not Updated",
                message="Cannot update password. User does not use the ComPAIR account login authentication method.")

        params = update_password_parser.parse_args()
        oldpassword = params.get('oldpassword')

        if current_user.id == user.id and not oldpassword:
            abort(400, title="Password Not Updated", message="The old password is missing.")
        elif current_user.id == user.id and not user.verify_password(oldpassword):
            abort(400, title="Password Not Updated", message="The old password is incorrect.")

        user.password = params.get('newpassword')
        db.session.commit()
        on_user_password_update.send(
            self,
            event_name=on_user_password_update.name,
            user=current_user)
        return marshal(user, dataformat.get_user(False))

api = new_restful_api(user_api)
api.add_resource(UserAPI, '/<user_uuid>')
api.add_resource(UserListAPI, '')
api.add_resource(UserCourseListAPI, '/<user_uuid>/courses')
api.add_resource(CurrentUserCourseListAPI, '/courses')
api.add_resource(UserCourseStatusListAPI, '/courses/status')
api.add_resource(TeachingUserCourseListAPI, '/courses/teaching')
api.add_resource(UserEditButtonAPI, '/<user_uuid>/edit')
api.add_resource(UserUpdatePasswordAPI, '/<user_uuid>/password')
