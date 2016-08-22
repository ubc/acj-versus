import os
from flask import Blueprint, jsonify, request, session as sess, current_app, url_for, redirect, Flask, render_template
from flask_login import current_user, login_required, login_user, logout_user

from acj import cas
from acj.authorization import get_logged_in_user_permissions
from acj.models import User
from pylti.flask import lti, LTI_SESSION_KEY
import logging

login_api = Blueprint("login_api", __name__, url_prefix='/api')
VERSION = '0.0.1'
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='myapp.log',
                    filemode='w')
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)

def error(exception=None):
    return str(exception)

@login_api.route('/login', methods=['POST'])
def login():
    # expecting login params to be in json format
    param = request.json
    if param is None:
        return jsonify({"error": 'Invalid login data format. Expecting json.'}), 400
    username = param['username']
    password = param['password']
    # grab the user from the username
    user = User.query.filter_by(username=username).first()
    if not user:
        current_app.logger.debug("Login failed, invalid username for: " + username)
    elif not user.verify_password(password):
        current_app.logger.debug("Login failed, invalid password for: " + username)
    else:
        permissions = authenticate(user)
        return jsonify({"userid": user.id, "permissions": permissions})

    # login unsuccessful
    return jsonify({"error": 'Sorry, unrecognized username or password.'}), 400

@login_api.route('/lti/auth', methods=['POST'])
@lti(request='initial', error=error)
def lti_auth(lti=lti):
    """Kickstarts the LTI integration flow.
    """
    return lti.user_id

@login_api.route('/logout', methods=['DELETE'])
@login_required
def logout():
    current_user.update_last_online()
    logout_user()  # flask-login delete user info
    if 'CAS_LOGIN' in sess:
        sess.pop('CAS_LOGIN')
        return jsonify({'redirect': url_for('cas.logout')})
    else:
        return ""


@login_api.route('/session', methods=['GET'])
@login_required
def session():
    return jsonify({"id": current_user.id, "permissions": get_logged_in_user_permissions()})


@login_api.route('/session/permission', methods=['GET'])
@login_required
def get_permission():
    return jsonify(get_logged_in_user_permissions())


@login_api.route('/auth/cas', methods=['GET'])
def auth_cas():
    """
    CAS Authentication Endpoint. Authenticate user through CAS. If user doesn't exists,
    set message in session so that frontend can get the message through /session call
    """
    username = cas.username

    if username is not None:
        user = User.query.filter_by(username=username).first()
        msg = None
        if not user:
            current_app.logger.debug("Login failed, invalid username for: " + username)
            msg = 'You don\'t have access to this application.'
        else:
            authenticate(user)
            sess['CAS_LOGIN'] = True
    else:
        msg = 'Login Failed. Expecting CAS username to be set.'

    if msg is not None:
        sess['CAS_AUTH_MSG'] = msg

    return redirect('/')


def authenticate(user):
    # username valid, password valid, login successful
    # "remember me" functionality is available, do we want to implement?
    user.update_last_online()
    login_user(user)  # flask-login store user info
    current_app.logger.debug("Login successful for: " + user.username)
    return get_logged_in_user_permissions()
