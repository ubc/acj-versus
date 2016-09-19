from flask import redirect
from flask import render_template


def register_api_blueprints(app):
    # Initialize rest of the api modules
    from .course import course_api
    app.register_blueprint(
        course_api,
        url_prefix='/api/courses')

    from .classlist import classlist_api
    app.register_blueprint(
        classlist_api,
        url_prefix='/api/courses/<course_uuid>/users')

    from .course_group import course_group_api
    app.register_blueprint(
        course_group_api,
        url_prefix='/api/courses/<course_uuid>/groups')

    from .course_group_user import course_group_user_api
    app.register_blueprint(
        course_group_user_api,
        url_prefix='/api/courses/<course_uuid>/users')

    from .login import login_api
    app.register_blueprint(login_api)

    from .lti_launch import lti_api
    app.register_blueprint(lti_api)

    from .users import user_api
    app.register_blueprint(
        user_api,
        url_prefix='/api/users')

    from .assignment import assignment_api
    app.register_blueprint(
        assignment_api,
        url_prefix='/api/courses/<course_uuid>/assignments')

    from .answer import answers_api
    app.register_blueprint(
        answers_api,
        url_prefix='/api/courses/<course_uuid>/assignments/<assignment_uuid>/answers')

    from .file import file_api
    app.register_blueprint(
        file_api,
        url_prefix='/api/attachment')

    from .assignment_comment import assignment_comment_api
    app.register_blueprint(
        assignment_comment_api,
        url_prefix='/api/courses/<course_uuid>/assignments/<assignment_uuid>/comments')

    from .answer_comment import answer_comment_api
    app.register_blueprint(
        answer_comment_api,
        url_prefix='/api/courses/<course_uuid>/assignments/<assignment_uuid>')

    from .criterion import criterion_api
    app.register_blueprint(
        criterion_api,
        url_prefix='/api/criteria')

    from .assignment_criterion import assignment_criterion_api
    app.register_blueprint(
        assignment_criterion_api,
        url_prefix='/api/courses/<course_uuid>/assignments/<assignment_uuid>/criteria')

    from .comparison import comparison_api
    app.register_blueprint(
        comparison_api,
        url_prefix='/api/courses/<course_uuid>/assignments/<assignment_uuid>/comparisons')

    from .comparison_example import comparison_example_api
    app.register_blueprint(
        comparison_example_api,
        url_prefix='/api/courses/<course_uuid>/assignments/<assignment_uuid>/comparisons/examples')

    from .report import report_api
    app.register_blueprint(
        report_api,
        url_prefix='/api/courses/<course_uuid>/report')

    from .gradebook import gradebook_api
    app.register_blueprint(
        gradebook_api,
        url_prefix='/api/courses/<course_uuid>/assignments/<assignment_uuid>/gradebook')

    from .common import timer_api
    app.register_blueprint(
        timer_api,
        url_prefix='/api/timer')

    from .healthz import healthz_api
    app.register_blueprint(healthz_api)

    @app.route('/app/')
    def route_app():
        if app.debug:
            return render_template(
                'index-dev.html',
                ga_tracking_id=app.config['GA_TRACKING_ID'])

        # running in prod mode, figure out asset location
        assets = app.config['ASSETS']
        prefix = ''
        if app.config['ASSET_LOCATION'] == 'cloud':
            prefix = app.config['ASSET_CLOUD_URI_PREFIX']
        elif app.config['ASSET_LOCATION'] == 'local':
            prefix = app.static_url_path + '/dist/'
        else:
            app.logger.error('Invalid ASSET_LOCATION value ' + app.config['ASSET_LOCATION'] + '.')

        return render_template(
            'index.html',
            bower_js_libs=prefix + assets['bowerJsLibs.js'],
            acj_js=prefix + assets['acj.js'],
            acj_css=prefix + assets['acj.css'],
            ga_tracking_id=app.config['GA_TRACKING_ID'])

    @app.route('/')
    def route_root():
        return redirect("/app/")

    return app


def log_events(log):
    # user events
    from .users import on_user_modified, on_user_get, on_user_list_get, on_user_create, on_user_course_get, \
        on_user_password_update, on_user_edit_button_get, on_teaching_course_get
    on_user_modified.connect(log)
    on_user_get.connect(log)
    on_user_list_get.connect(log)
    on_user_create.connect(log)
    on_user_course_get.connect(log)
    on_teaching_course_get.connect(log)
    on_user_edit_button_get.connect(log)
    on_user_password_update.connect(log)

    # course events
    from .course import on_course_modified, on_course_get, on_course_list_get, on_course_create, \
        on_course_duplicate
    on_course_modified.connect(log)
    on_course_get.connect(log)
    on_course_list_get.connect(log)
    on_course_create.connect(log)
    on_course_duplicate.connect(log)

    # assignment events
    from .assignment import on_assignment_modified, on_assignment_get, on_assignment_list_get, on_assignment_create, \
        on_assignment_delete, on_assignment_list_get_status, on_assignment_get_status
    on_assignment_modified.connect(log)
    on_assignment_get.connect(log)
    on_assignment_list_get.connect(log)
    on_assignment_create.connect(log)
    on_assignment_delete.connect(log)
    on_assignment_list_get_status.connect(log)
    on_assignment_get_status.connect(log)

    # assignment comment events
    from .assignment_comment import on_assignment_comment_modified, on_assignment_comment_get, \
        on_assignment_comment_list_get, on_assignment_comment_create, on_assignment_comment_delete
    on_assignment_comment_modified.connect(log)
    on_assignment_comment_get.connect(log)
    on_assignment_comment_list_get.connect(log)
    on_assignment_comment_create.connect(log)
    on_assignment_comment_delete.connect(log)

    # answer events
    from .answer import on_answer_modified, on_answer_get, on_answer_list_get, on_answer_create, on_answer_flag, \
        on_answer_delete, on_user_answer_get, on_answer_comparisons_get
    on_answer_modified.connect(log)
    on_answer_get.connect(log)
    on_answer_list_get.connect(log)
    on_answer_create.connect(log)
    on_answer_flag.connect(log)
    on_answer_delete.connect(log)
    on_user_answer_get.connect(log)
    on_answer_comparisons_get.connect(log)

    # answer comment events
    from .answer_comment import on_answer_comment_modified, on_answer_comment_get, on_answer_comment_list_get, \
        on_answer_comment_create, on_answer_comment_delete
    on_answer_comment_modified.connect(log)
    on_answer_comment_get.connect(log)
    on_answer_comment_list_get.connect(log)
    on_answer_comment_create.connect(log)
    on_answer_comment_delete.connect(log)

    # criterion events
    from .criterion import criterion_get, criterion_update, on_criterion_list_get, criterion_create
    criterion_get.connect(log)
    criterion_update.connect(log)
    on_criterion_list_get.connect(log)
    criterion_create.connect(log)

    # assignment criterion events
    from .assignment_criterion import on_assignment_criterion_get
    on_assignment_criterion_get.connect(log)

    # comparison events
    from .comparison import on_comparison_get, on_comparison_create, on_comparison_update
    on_comparison_get.connect(log)
    on_comparison_create.connect(log)
    on_comparison_update.connect(log)

    # comparison example events
    from .comparison_example import on_comparison_example_create, on_comparison_example_delete, \
        on_comparison_example_list_get, on_comparison_example_modified
    on_comparison_example_create.connect(log)
    on_comparison_example_delete.connect(log)
    on_comparison_example_list_get.connect(log)
    on_comparison_example_modified.connect(log)

    # classlist events
    from .classlist import on_classlist_get, on_classlist_upload, on_classlist_enrol, on_classlist_unenrol, \
        on_classlist_instructor_label, on_classlist_instructor, on_classlist_student, \
        on_classlist_update_users_course_roles
    on_classlist_get.connect(log)
    on_classlist_upload.connect(log)
    on_classlist_enrol.connect(log)
    on_classlist_unenrol.connect(log)
    on_classlist_instructor_label.connect(log)
    on_classlist_instructor.connect(log)
    on_classlist_student.connect(log)
    on_classlist_update_users_course_roles.connect(log)

    # course group events
    from .course_group import on_course_group_get, on_course_group_import, on_course_group_members_get
    on_course_group_get.connect(log)
    on_course_group_import.connect(log)
    on_course_group_members_get.connect(log)

    # course user group events
    from .course_group_user import on_course_group_user_create, on_course_group_user_delete, \
        on_course_group_user_list_create, on_course_group_user_list_delete
    on_course_group_user_create.connect(log)
    on_course_group_user_delete.connect(log)
    on_course_group_user_list_create.connect(log)
    on_course_group_user_list_delete.connect(log)

    # report event
    from .report import on_export_report
    on_export_report.connect(log)

    # file attachment event
    from .file import on_save_tmp_file, on_file_get, on_file_delete
    on_save_tmp_file.connect(log)
    on_file_get.connect(log)
    on_file_delete.connect(log)

    # gradebook event
    from .gradebook import on_gradebook_get
    on_gradebook_get.connect(log)

    from .lti_launch import on_lti_course_link, on_lti_course_membership_update, \
        on_lti_course_membership_status_get
    on_lti_course_link.connect(log)
    on_lti_course_membership_update.connect(log)
    on_lti_course_membership_status_get.connect(log)
