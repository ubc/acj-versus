"""
This module manages to load the application configuration from various places. (Priority from high to low)

* Environment variables
* config.py
* Default Settings: acj/settings.py

The configuration will be merged in above order and config variable is available for the final result.

The database settings can be defined as a string in DATABASE_URI or as a dictionary in DATABASE in different
configuration locations. (Priority from high to low)

* Environment variables
* DATABASE_URI
* DATABASE

Currently the supported environment variables:

* OpenShift
* DATABASE_URI
"""

import os

from flask import Config
from sqlalchemy.engine.url import URL


config = Config('.')
config.from_object('acj.settings')
config.from_pyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../config.py'), silent=True)

if os.environ.get('OPENSHIFT_MYSQL_DB_HOST'):
    config['SQLALCHEMY_DATABASE_URI'] = URL(
        'mysql+pymysql',
        host=os.getenv('OPENSHIFT_MYSQL_DB_HOST', 'localhost'),
        port=os.getenv('OPENSHIFT_MYSQL_DB_PORT', '3306'),
        username=os.getenv('OPENSHIFT_MYSQL_DB_USERNAME', 'compair'),
        password=os.getenv('OPENSHIFT_MYSQL_DB_PASSWORD', 'compair'),
        database=os.getenv('OPENSHIFT_GEAR_NAME', 'compair'),
    )
elif os.environ.get('DB_HOST') or os.environ.get('DB_PORT') or os.environ.get('DB_USERNAME') \
        or os.environ.get('DB_PASSWORD') or os.environ.get('DB_NAME'):
    config['SQLALCHEMY_DATABASE_URI'] = URL(
        os.getenv('DB_DRIVER', 'mysql+pymysql'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '3306'),
        username=os.getenv('DB_USERNAME', 'compair'),
        password=os.getenv('DB_PASSWORD', 'compair'),
        database=os.getenv('DB_NAME', 'compair'),
    )
elif os.environ.get('DATABASE_URI'):
    config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI')
elif "DATABASE" in config and 'DATABASE_URI' not in config:
    config['SQLALCHEMY_DATABASE_URI'] = URL(**config['DATABASE'])
elif "DATABASE_URI" in config:
    config['SQLALCHEMY_DATABASE_URI'] = config['DATABASE_URI']

# clear DATABASE value
if 'DATABASE' in config:
    del config['DATABASE']

env_overridables = [
    'APP_LOGIN_ENABLED', 'CAS_LOGIN_ENABLED', 'LTI_LOGIN_ENABLED',
    'CAS_SERVER', 'CAS_AFTER_LOGIN', 'REPORT_FOLDER',
    'CAS_LOGIN_ROUTE', 'CAS_LOGOUT_ROUTE',
    'CAS_LOGOUT_RETURN_URL', 'CAS_VERSION',
    'CAS_VALIDATE_ROUTE',
    'SECRET_KEY', 'UPLOAD_FOLDER', 'ATTACHMENT_UPLOAD_FOLDER',
    'ASSET_LOCATION', 'ASSET_CLOUD_URI_PREFIX',
    'GA_TRACKING_ID']

for env in env_overridables:
    if os.environ.get(env):
        config[env] = os.environ.get(env)

# print config
