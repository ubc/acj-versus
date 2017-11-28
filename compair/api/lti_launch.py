from bouncer.constants import CREATE, READ, EDIT, DELETE, MANAGE
from flask import Blueprint, jsonify, request, current_app, url_for, redirect, session as sess
from flask_login import login_required, current_user, logout_user
from flask_restful import Resource, marshal
from flask_restful.reqparse import RequestParser
from sqlalchemy import and_, or_

from . import dataformat
from compair.core import event, db, abort
from compair.authorization import require, allow
from .login import authenticate
from compair.models import User, Course, LTIConsumer, LTIContext, LTIMembership, \
    LTIResourceLink, LTIUser, LTIUserResourceLink, LTINonce
from compair.models.lti_models import MembershipNoValidContextsException, \
    MembershipNoResultsException, MembershipInvalidRequestException
from .util import new_restful_api, get_model_changes, pagination_parser
from compair.tasks import update_lti_course_membership

from compair.api.classlist import display_name_generator
from lti.contrib.flask import FlaskToolProvider
from oauthlib.oauth1 import RequestValidator

lti_api = Blueprint("lti_api", __name__)
api = new_restful_api(lti_api)

lti_launch_parser = RequestParser()
lti_launch_parser.add_argument('assignment', default=None)

# /auth
class LTIAuthAPI(Resource):
    def post(self):
        """
        Kickstarts the LTI integration flow.
        """
        if not current_app.config.get('LTI_LOGIN_ENABLED'):
            abort(403, title="Log In Failed",
                message="Please try an alternate way of logging in. The LTI login has been disabled by your system administrator.")

        tool_provider = FlaskToolProvider.from_flask_request(request=request)
        validator = ComPAIRRequestValidator()
        ok = tool_provider.is_valid_request(validator)

        if ok:
            lti_consumer = LTIConsumer.get_by_tool_provider(tool_provider)
            # override user_id if set to override
            if lti_consumer.user_id_override and lti_consumer.user_id_override in tool_provider.launch_params:
                tool_provider.user_id = tool_provider.launch_params[lti_consumer.user_id_override]

            params = lti_launch_parser.parse_args()
            # override custom_assignment if not set in launch body but is in querystring
            if not tool_provider.custom_assignment and params.get('assignment'):
                tool_provider.custom_assignment = params.get('assignment')

            # chec
            if tool_provider.user_id != None:
                # log current user out if needed
                logout_user()
                sess.clear()

                sess['LTI'] = True

                sess['lti_consumer'] = lti_consumer.id

                lti_user = LTIUser.get_by_tool_provider(lti_consumer, tool_provider)
                sess['lti_user'] = lti_user.id

                lti_context = LTIContext.get_by_tool_provider(lti_consumer, tool_provider)
                if lti_context:
                    sess['lti_context'] = lti_context.id

                lti_resource_link = LTIResourceLink.get_by_tool_provider(lti_consumer, tool_provider, lti_context)
                sess['lti_resource_link'] = lti_resource_link.id

                lti_user_resource_link = LTIUserResourceLink.get_by_tool_provider(lti_resource_link, lti_user, tool_provider)
                sess['lti_user_resource_link'] = lti_user_resource_link.id

                setup_required = False
                angular_route = None

                # if user linked
                if lti_user.is_linked_to_user():
                    authenticate(lti_user.compair_user, login_method='LTI')

                    # upgrade user system role if needed
                    lti_user.upgrade_system_role()

                    # create/update enrollment if context exists
                    if lti_context and lti_context.is_linked_to_course():
                        lti_context.update_enrolment(lti_user.compair_user_id, lti_user_resource_link.course_role)
                else:
                    # need to create user link
                    sess['oauth_create_user_link'] = True
                    setup_required = True

                if not lti_context:
                    # no context, redriect to home page
                    angular_route = "/"
                elif lti_context.is_linked_to_course():
                    # redirect to course page or assignment page if available
                    angular_route = "/course/"+lti_context.compair_course_uuid
                    if lti_resource_link.is_linked_to_assignment():
                        angular_route += "/assignment/"+lti_resource_link.compair_assignment_uuid
                else:
                    # instructors can select course, students will recieve a warning message
                    setup_required = True

                if setup_required:
                    # if account/course setup required, redirect to lti controller
                    angular_route = "/lti"
                elif angular_route == None:
                    # set angular route to home page by default
                    angular_route = "/"

                return current_app.make_response(redirect("/app/#"+angular_route))

        display_message = "Invalid Request"
        if ok and tool_provider.user_id == None:
            display_message = "ComPAIR requires the LTI tool consumer to provide a user_id."

        tool_provider.lti_errormsg = display_message
        return_url = tool_provider.build_return_url()
        if return_url:
            return redirect(return_url)
        else:
            return display_message, 400

api.add_resource(LTIAuthAPI, '/auth')

# /status
class LTIStatusAPI(Resource):
    def get(self):
        """
        Returns information related to the current user:
        any linked course, assignment, etc. Helps inform
        the app as to what to do next, for a given state.
        """

        if not sess.get('LTI'):
            return { "status" : { 'valid': False } }

        lti_resource_link = LTIResourceLink.query.get(sess.get('lti_resource_link'))
        lti_context = LTIContext.query.get(sess.get('lti_context')) if sess.get('lti_context') else None
        lti_user_resource_link = LTIUserResourceLink.query.get(sess.get('lti_user_resource_link'))
        lti_user = LTIUser.query.get(sess.get('lti_user'))
        status = {
            'valid' : True,
            'assignment': {
                'id': lti_resource_link.compair_assignment_uuid if lti_resource_link.compair_assignment_id != None else None,
                'exists': lti_resource_link.compair_assignment_id != None
            },
            'course': {
                'name': lti_context.context_title if lti_context else None,
                'id': lti_context.compair_course_uuid if lti_context and lti_context.compair_course_id else None,
                'exists': lti_context and lti_context.compair_course_id != None,
                'course_role': lti_user_resource_link.course_role.value if lti_user_resource_link else None
            },
            'user': {
                'exists': lti_user.compair_user_id != None,
                'firstname': lti_user.lis_person_name_given,
                'lastname': lti_user.lis_person_name_family,
                'displayname': display_name_generator(lti_user.system_role.value),
                'email': lti_user.lis_person_contact_email_primary,
                'system_role': lti_user.system_role.value
            }
        }

        return { "status" : status }

api.add_resource(LTIStatusAPI, '/status')

class ComPAIRRequestValidator(RequestValidator):
    @property
    def enforce_ssl(self):
        return current_app.config.get('ENFORCE_SSL', True)

    @property
    def client_key_length(self):
        return 10, 255

    @property
    def request_token_length(self):
        return 10, 255

    @property
    def access_token_length(self):
        return 10, 255

    @property
    def timestamp_lifetime(self):
        return 600

    @property
    def nonce_length(self):
        return 10, 255

    @property
    def verifier_length(self):
        return 10, 255

    def check_client_key(self, client_key):
        """
        Check that the client key is no shorter than lower and no longer than upper.
        removed bit about safe characters since it doesn't allow common special characters like '_' or '.'
        """
        lower, upper = self.client_key_length
        return lower <= len(client_key) <= upper

    def validate_timestamp_and_nonce(self, client_key, timestamp, nonce,
                                     request, request_token=None, access_token=None):
        return LTINonce.is_valid_nonce(client_key, nonce, timestamp)

    def validate_client_key(self, client_key, request):
        lti_consumer = LTIConsumer.query \
            .filter_by(
                active=True,
                oauth_consumer_key=client_key
            ) \
            .one_or_none()

        return lti_consumer != None

    def get_client_secret(self, client_key, request):
        lti_consumer = LTIConsumer.query \
            .filter_by(
                active=True,
                oauth_consumer_key=client_key
            ) \
            .one_or_none()
        return lti_consumer.oauth_consumer_secret if lti_consumer else None
