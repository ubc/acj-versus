#!/usr/bin/env python

from flask_script import Manager, Server

from acj.manage.database import manager as database_manager
from acj.manage.report import manager as report_generator
from acj.manage.user import manager as user_manager
from acj.manage.utils import manager as util_manager
from acj import create_app

manager = Manager(create_app)
# register sub-managers
manager.add_command("database", database_manager)
manager.add_command("report", report_generator)
manager.add_command("runserver", Server(port=8080))
manager.add_command("user", user_manager)
manager.add_command("util", util_manager)


@manager.command
def list_routes():
    import urllib

    output = []
    for rule in manager.app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        line = urllib.unquote("{:50s} {:20s} {}".format(rule.endpoint, methods, rule))
        output.append(line)

    for line in sorted(output):
        print(line)


if __name__ == "__main__":
    manager.run()
