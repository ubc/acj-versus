import io
import json

from data.fixtures.test_data import TestFixture, ThirdPartyAuthTestData
from acj.tests.test_acj import ACJAPITestCase

from acj.models import UserCourse, CourseRole, ThirdPartyType


class CourseGroupsAPITests(ACJAPITestCase):
    def setUp(self):
        super(CourseGroupsAPITests, self).setUp()
        self.fixtures = TestFixture().add_course(num_students=30, num_groups=3)

    def test_get_active_groups(self):
        url = '/api/courses/'+self.fixtures.course.uuid+'/groups'

        # test login required
        rv = self.client.get(url)
        self.assert401(rv)

        # test unauthorized user
        with self.login(self.fixtures.unauthorized_instructor.username):
            rv = self.client.get(url)
            self.assert403(rv)

        # test invalid course id
        with self.login(self.fixtures.instructor.username):
            invalid_url = '/api/courses/999/groups'
            rv = self.client.get(invalid_url)
            self.assert404(rv)

            # test successful query
            rv = self.client.get(url)
            self.assert200(rv)
            actual = rv.json['objects']
            self.assertEqual(len(actual), 3)
            self.assertEqual(actual[0], self.fixtures.groups[0])

        # test TA
        with self.login(self.fixtures.ta.username):
            self.assert200(rv)
            actual = rv.json['objects']
            self.assertEqual(len(actual), 3)
            self.assertEqual(actual[0], self.fixtures.groups[0])

    def test_get_group_members(self):
        course = self.fixtures.course
        group_name = self.fixtures.groups[0]
        url = '/api/courses/'+course.uuid+'/groups/'+group_name

        # test login required
        rv = self.client.get(url)
        self.assert401(rv)

        # test unauthorized user
        with self.login(self.fixtures.unauthorized_instructor.username):
            rv = self.client.get(url)
            self.assert403(rv)

        # test invalid course id
        with self.login(self.fixtures.instructor.username):
            rv = self.client.get('/api/courses/999/groups/'+group_name)
            self.assert404(rv)

            # test invalid group id
            rv = self.client.get('/api/courses/'+course.uuid+'/groups/asdasdasdasd')
            self.assert404(rv)

            # test authorized instructor
            rv = self.client.get(url)
            self.assert200(rv)
            self.assertEqual(10, len(rv.json['students']))
            self.assertEqual(self.fixtures.students[0].uuid, rv.json['students'][0]['id'])

        # test authorized teaching assistant
        with self.login(self.fixtures.ta.username):
            rv = self.client.get(url)
            self.assert200(rv)
            self.assertEqual(10, len(rv.json['students']))
            self.assertEqual(self.fixtures.students[0].uuid, rv.json['students'][0]['id'])

    def test_group_enrolment(self):
        # frequently used objects
        course = self.fixtures.course
        group_name = self.fixtures.groups[0]

        # test login required
        url = self._create_group_user_url(course, self.fixtures.students[0], group_name)
        rv = self.client.post(url, data={}, content_type='application/json')
        self.assert401(rv)

        # test unauthorized user
        with self.login(self.fixtures.unauthorized_instructor.username):
            url = self._create_group_user_url(course, self.fixtures.students[0], group_name)
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert403(rv)

        with self.login(self.fixtures.instructor.username):
            # test user that is already in group
            url = self._create_group_user_url(course, self.fixtures.students[0], group_name)
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert200(rv)
            self.assertEqual(rv.json['group_name'], group_name)

            # test user that has never been in the group
            url = self._create_group_user_url(course, self.fixtures.instructor, group_name)
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert200(rv)
            self.assertEqual(rv.json['group_name'], group_name)

            # test user that has left the group
            url = self._create_group_user_url(course, self.fixtures.ta, group_name)
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert200(rv)
            self.assertEqual(rv.json['group_name'], group_name)

            # test user that is not enroled in the course anymore - eg. DROPPED
            url = self._create_group_user_url(course, self.fixtures.dropped_instructor, group_name)
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert404(rv)

            # test user that has never been in the course
            url = self._create_group_user_url(course, self.fixtures.unauthorized_student, group_name)
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert404(rv)

            # test invalid course id
            url = '/api/courses/999/users/'+self.fixtures.students[0].uuid+'/groups/'+group_name
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert404(rv)

            # test invalid user id
            url = '/api/courses/'+course.uuid+'/users/999/groups/'+group_name
            rv = self.client.post(url, data={}, content_type='application/json')
            self.assert404(rv)

    def test_group_unenrolment(self):
        course = self.fixtures.course

        # test login required
        url = self._create_group_user_url(course, self.fixtures.students[0])
        rv = self.client.delete(url)
        self.assert401(rv)

        # test unauthorzied user
        with self.login(self.fixtures.unauthorized_instructor.username):
            url = self._create_group_user_url(course, self.fixtures.students[0])
            rv = self.client.delete(url)
            self.assert403(rv)

        with self.login(self.fixtures.instructor.username):
            # test user in course
            url = self._create_group_user_url(course, self.fixtures.students[0])
            rv = self.client.delete(url)
            self.assert200(rv)
            self.assertEqual(rv.json['user_id'], self.fixtures.students[0].uuid)
            self.assertEqual(rv.json['course_id'], course.uuid)

            # test user not in course
            url = self._create_group_user_url(course, self.fixtures.unauthorized_student)
            rv = self.client.delete(url)
            self.assert404(rv)

            # test invalid course id
            url = '/api/courses/999/users/'+self.fixtures.students[0].uuid+'/groups'
            rv = self.client.delete(url)
            self.assert404(rv)

            # test invalid user id
            url = '/api/courses/'+course.uuid+'/users/999/groups'
            rv = self.client.delete(url)
            self.assert404(rv)

    def test_import_groups(self):
        auth_data = ThirdPartyAuthTestData()
        url = '/api/courses/' + self.fixtures.course.uuid + '/groups'

        content = self.fixtures.students[0].username + "," + self.fixtures.groups[0]
        encoded_content = content.encode()
        filename = "groups.csv"

        # test login required
        uploaded_file = io.BytesIO(encoded_content)
        rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
        self.assert401(rv)
        uploaded_file.close()

        # test unauthorized user
        uploaded_file = io.BytesIO(encoded_content)
        with self.login(self.fixtures.students[0].username):
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert403(rv)
            uploaded_file.close()

        uploaded_file = io.BytesIO(encoded_content)
        with self.login(self.fixtures.ta.username):
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert403(rv)
            uploaded_file.close()

        uploaded_file = io.BytesIO(encoded_content)
        with self.login(self.fixtures.unauthorized_instructor.username):
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert403(rv)
            uploaded_file.close()

        with self.login(self.fixtures.instructor.username):
            # test invalid course id
            invalid_url = '/api/courses/999/groups'
            uploaded_file = io.BytesIO(encoded_content)
            rv = self.client.post(invalid_url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert404(rv)
            uploaded_file.close()

            # test invalid file type
            invalid_file = "groups.png"
            uploaded_file = io.BytesIO(encoded_content)
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, invalid_file)))
            self.assert400(rv)
            uploaded_file.close()

            # test invalid user identifier
            uploaded_file = io.BytesIO(encoded_content)
            rv = self.client.post(url, data=dict(userIdentifier="lastname", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(0, rv.json['success'])
            self.assertEqual({}, rv.json['invalids'][0]['member'])
            self.assertEqual("A valid user identifier is not given.", rv.json['invalids'][0]['message'])
            uploaded_file.close()

            # test missing user identifier
            uploaded_file = io.BytesIO(encoded_content)
            rv = self.client.post(url, data=dict(file=(uploaded_file, filename)))
            self.assert400(rv)
            uploaded_file.close()

            # test duplicate users in file
            duplicate = "".join([content, "\n", content])
            uploaded_file = io.BytesIO(duplicate.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(1, len(rv.json['invalids']))
            invalid = rv.json['invalids'][0]
            member = [
                '["', self.fixtures.students[0].username, '", "',
                self.fixtures.groups[0], '"]']
            self.assertEqual("".join(member), invalid['member'])
            self.assertEqual("This user already exists in the file.", invalid['message'])
            uploaded_file.close()

            # test missing username
            missing_username = "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(missing_username.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(1, len(rv.json['invalids']))
            invalid = rv.json['invalids'][0]
            member = ['["", "', self.fixtures.groups[0], '"]']
            self.assertEqual("".join(member), invalid['member'])
            self.assertEqual("No user with this ComPAIR username exists.", invalid['message'])
            uploaded_file.close()

            # test missing group name
            missing_group = self.fixtures.students[0].username + ","
            uploaded_file = io.BytesIO(missing_group.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(0, rv.json['success'])
            self.assertEqual(1, len(rv.json['invalids']))
            invalid = rv.json['invalids'][0]
            member = ['["', self.fixtures.students[0].username, '", ""]']
            self.assertEqual("".join(member), invalid['member'])
            self.assertEqual("The group name is invalid.", invalid['message'])
            uploaded_file.close()

            # test invalid user
            invalid_user = "username9999," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(invalid_user.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(1, len(rv.json['invalids']))
            invalid = rv.json['invalids'][0]
            member = ['["username9999", "', self.fixtures.groups[0], '"]']
            self.assertEqual("".join(member), invalid['member'])
            self.assertEqual("No user with this ComPAIR username exists.", invalid['message'])
            uploaded_file.close()

            # test successful import with username
            with_username = self.fixtures.students[0].username + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(with_username.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(0, len(rv.json['invalids']))
            uploaded_file.close()

            # test invalid import with username
            self.app.config['APP_LOGIN_ENABLED'] = False
            with_username = self.fixtures.students[0].username + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(with_username.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert400(rv)
            uploaded_file.close()
            self.app.config['APP_LOGIN_ENABLED'] = True

            # test successful import with student number
            with_studentno = self.fixtures.students[0].student_number + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(with_studentno.encode())
            rv = self.client.post(url, data=dict(userIdentifier="student_number", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(0, len(rv.json['invalids']))
            uploaded_file.close()

            # test successful import with cwl username
            cas_auth = auth_data.create_cas_user_auth(CourseRole.student)
            cas_user = cas_auth.user
            self.fixtures.enrol_user(cas_user, self.fixtures.course, CourseRole.student)

            with_cwl_username = cas_auth.unique_identifier + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(with_cwl_username.encode())
            rv = self.client.post(url, data=dict(userIdentifier=ThirdPartyType.cwl.value, file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(0, len(rv.json['invalids']))
            uploaded_file.close()

            # test invalid import with cwl username
            self.app.config['CAS_LOGIN_ENABLED'] = False
            with_cwl_username = cas_auth.unique_identifier + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(with_cwl_username.encode())
            rv = self.client.post(url, data=dict(userIdentifier=ThirdPartyType.cwl.value, file=(uploaded_file, filename)))
            self.assert400(rv)
            uploaded_file.close()
            self.app.config['CAS_LOGIN_ENABLED'] = True

            # test import user not in course
            unauthorized_student = self.fixtures.unauthorized_student.username + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(unauthorized_student.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(1, len(rv.json['invalids']))
            invalid = rv.json['invalids'][0]
            member = [
                '["', self.fixtures.unauthorized_student.username, '", "',
                self.fixtures.groups[0], '"]']
            self.assertEqual("".join(member), invalid['member'])
            self.assertEqual("The user is not enroled in the course", invalid['message'])
            uploaded_file.close()

            # test placing instructor in group
            add_instructor = self.fixtures.instructor.username + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(add_instructor.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(0, len(rv.json['invalids']))
            uploaded_file.close()

            # test placing TA in group
            add_ta = self.fixtures.ta.username + "," + self.fixtures.groups[0]
            uploaded_file = io.BytesIO(add_ta.encode())
            rv = self.client.post(url, data=dict(userIdentifier="username", file=(uploaded_file, filename)))
            self.assert200(rv)
            self.assertEqual(1, rv.json['success'])
            self.assertEqual(0, len(rv.json['invalids']))
            uploaded_file.close()

    def test_group_multiple_enrolment(self):
        # frequently used objects
        course = self.fixtures.course
        group_name = self.fixtures.groups[0]
        group_name_2 = self.fixtures.groups[1]
        student_ids = [self.fixtures.students[0].uuid, self.fixtures.students[1].uuid]
        url = self._create_group_users_url(course, group_name)

        params = { 'ids': student_ids }

        # test login required
        rv = self.client.post(url,
            data=json.dumps(params),
            content_type='application/json')
        self.assert401(rv)

        # test unauthorized user
        with self.login(self.fixtures.unauthorized_instructor.username):
            rv = self.client.post(url,
                data=json.dumps(params),
                content_type='application/json')
            self.assert403(rv)

        with self.login(self.fixtures.instructor.username):
            # test invalid course id
            rv = self.client.post('/api/courses/999/users/groups/'+group_name,
                data=json.dumps(params),
                content_type='application/json')
            self.assert404(rv)

            # test missing ids
            rv = self.client.post(url,
                data=json.dumps({'ids': []}),
                content_type='application/json')
            self.assert400(rv)

            # test invalid ids
            rv = self.client.post(url,
                data=json.dumps({'ids': [self.fixtures.unauthorized_student.uuid]}),
                content_type='application/json')
            self.assert400(rv)

            # test enrol users into group
            rv = self.client.post(url,
                data=json.dumps(params),
                content_type='application/json')
            self.assert200(rv)
            self.assertEqual(rv.json['group_name'], group_name)

            for user_course in course.user_courses:
                if user_course.user_id in student_ids:
                    self.assertEqual(user_course.group_name, group_name)

            # test enrol users into another group
            url = self._create_group_users_url(course, group_name_2)
            rv = self.client.post(url,
                data=json.dumps(params),
                content_type='application/json')
            self.assert200(rv)
            self.assertEqual(rv.json['group_name'], group_name_2)

            for user_course in course.user_courses:
                if user_course.user_id in student_ids:
                    self.assertEqual(user_course.group_name, group_name_2)

    def test_group_multiple_unenrolment(self):
        course = self.fixtures.course
        url = self._create_group_users_url(course)

        student_ids = [self.fixtures.students[0].uuid, self.fixtures.students[1].uuid]
        params = { 'ids': student_ids }

        # test login required
        rv = self.client.post(url,
            data=json.dumps(params),
            content_type='application/json')
        self.assert401(rv)

        # test unauthorzied user
        with self.login(self.fixtures.unauthorized_instructor.username):
            rv = self.client.post(url,
                data=json.dumps(params),
                content_type='application/json')
            self.assert403(rv)

        with self.login(self.fixtures.instructor.username):
            # test invalid course id
            rv = self.client.post('/api/courses/999/users/groups',
                data=json.dumps(params),
                content_type='application/json')
            self.assert404(rv)

            # test missing ids
            rv = self.client.post(url,
                data=json.dumps({ 'ids': [] }),
                content_type='application/json')
            self.assert400(rv)

            # test invalid ids
            rv = self.client.post(url,
                data=json.dumps({ 'ids': [self.fixtures.unauthorized_student.uuid] }),
                content_type='application/json')
            self.assert400(rv)

            # test users in course
            rv = self.client.post(url,
                data=json.dumps(params),
                content_type='application/json')
            self.assert200(rv)
            self.assertEqual(rv.json['course_id'], course.uuid)

            for user_course in course.user_courses:
                if user_course.user_id in student_ids:
                    self.assertEqual(user_course.group_name, None)

    def _create_group_user_url(self, course, user, group_name=None):
        url = '/api/courses/'+course.uuid+'/users/'+user.uuid+'/groups'
        if group_name:
            url = url+'/'+group_name
        return url

    def _create_group_users_url(self, course, group_name=None):
        url = '/api/courses/'+course.uuid+'/users/groups'
        if group_name:
            url = url+'/'+group_name
        return url
