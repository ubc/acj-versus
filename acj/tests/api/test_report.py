import csv
import json
import io
import os

from data.fixtures.test_data import TestFixture
from acj.tests.test_acj import ACJAPITestCase
from acj.models import CourseRole, Answer, Comparison, AnswerComment
from flask import current_app

class ReportAPITest(ACJAPITestCase):
    def setUp(self):
        super(ReportAPITest, self).setUp()
        self.fixtures = TestFixture().add_course(num_students=30, num_assignments=2, num_groups=2, num_answers=25)
        self.url = "/api/courses/" + str(self.fixtures.course.id) + "/report"
        self.files_to_cleanup = []
    
    def tearDown(self):
        folder = current_app.config['REPORT_FOLDER']
        
        for file_name in self.files_to_cleanup:
            file_path = os.path.join(folder, file_name)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(e)
        


    def test_generate_report(self):
        # test login required
        rv = self.client.post(self.url)
        self.assert401(rv)

        # test unauthorized user
        with self.login(self.fixtures.unauthorized_instructor.username):
            rv = self.client.post(self.url)
            self.assert403(rv)
            
            
        # valid instructor with invalid input
        with self.login(self.fixtures.instructor.username):
            input = {
                'group_name': None,
                'type': "participation",
                'assignment': None
            }
        
            # test invalid course id
            rv = self.client.post('/api/courses/999/report', data=json.dumps(input), content_type='application/json')
            self.assert404(rv)
            
            # test missing report type
            invalid_input = input.copy()
            invalid_input['type'] = None
            rv = self.client.post(self.url, data=json.dumps(invalid_input), content_type='application/json')
            self.assert400(rv)
            
            # test invalid  report type
            invalid_input = input.copy()
            invalid_input['type'] = "invalid_type"
            rv = self.client.post(self.url, data=json.dumps(invalid_input), content_type='application/json')
            self.assert400(rv)
            
            # test invalid assignment id 
            invalid_input = input.copy()
            invalid_input['assignment'] = 999
            rv = self.client.post(self.url, data=json.dumps(invalid_input), content_type='application/json')
            self.assert404(rv)
            
            # test invalid group name
            invalid_input = input.copy()
            invalid_input['group_name'] = "invalid_group_name"
            rv = self.client.post(self.url, data=json.dumps(invalid_input), content_type='application/json')
            self.assert404(rv)
        
        # participation with valid instructor
        with self.login(self.fixtures.instructor.username):
            input = {
                'group_name': None,
                'type': "participation",
                'assignment': None
            }
        
            # test authorized user entire course
            rv = self.client.post(self.url, data=json.dumps(input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading1 = next(reader)
                heading2 = next(reader)
                assignments = self.fixtures.assignments
                self._check_participation_report_heading_rows(assignments, heading1, heading2)
                
                for student in self.fixtures.students:
                    next_row = next(reader)
                    self._check_participation_report_user_row(assignments, student, next_row)
        
            # test authorized user one assignment
            single_assignment_input = input.copy()
            single_assignment_input['assignment'] = self.fixtures.assignments[0].id
            rv = self.client.post(self.url, data=json.dumps(single_assignment_input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading1 = next(reader)
                heading2 = next(reader)
                assignments = [self.fixtures.assignments[0]]
                self._check_participation_report_heading_rows(assignments, heading1, heading2)
                
                for student in self.fixtures.students:
                    next_row = next(reader)
                    self._check_participation_report_user_row(assignments, student, next_row)
        
            # test authorized user entire course with group name filter
            group_name_input = input.copy()
            group_name_input['group_name'] = self.fixtures.groups[0]
            rv = self.client.post(self.url, data=json.dumps(group_name_input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading1 = next(reader)
                heading2 = next(reader)
                assignments = self.fixtures.assignments
                self._check_participation_report_heading_rows(assignments, heading1, heading2)
                
                for student in self.fixtures.students:
                    if student.user_courses[0].group_name != self.fixtures.groups[0]:
                        continue
                    
                    next_row = next(reader)
                    self._check_participation_report_user_row(assignments, student, next_row)
        
            # test authorized single assignment with group name filter
            group_name_input = input.copy()
            group_name_input['assignment'] = self.fixtures.assignments[0].id
            group_name_input['group_name'] = self.fixtures.groups[0]
            rv = self.client.post(self.url, data=json.dumps(group_name_input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading1 = next(reader)
                heading2 = next(reader)
                assignments = [self.fixtures.assignments[0]]
                self._check_participation_report_heading_rows(assignments, heading1, heading2)
                
                for student in self.fixtures.students:
                    if student.user_courses[0].group_name != self.fixtures.groups[0]:
                        continue
                    
                    next_row = next(reader)
                    self._check_participation_report_user_row(assignments, student, next_row)
        
        # participation_stat with valid instructor
        with self.login(self.fixtures.instructor.username):
            input = {
                'group_name': None,
                'type': "participation_stat",
                'assignment': None
            }
            
            # test authorized user entire course
            rv = self.client.post(self.url, data=json.dumps(input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading = next(reader)
                assignments = self.fixtures.assignments
                self._check_participation_stat_report_heading_rows(heading)
                
                overall_stats = {}
                
                for assignment in assignments:
                    for student in self.fixtures.students:
                        next_row = next(reader)
                        user_stats = self._check_participation_stat_report_user_row(assignment, student, next_row, overall_stats)
                        
                # overall 
                for student in self.fixtures.students:
                    next_row = next(reader)    
                    self._check_participation_stat_report_user_overall_row(student, next_row, overall_stats)
            
            # test authorized user one assignment
            single_assignment_input = input.copy()
            single_assignment_input['assignment'] = self.fixtures.assignments[0].id
            rv = self.client.post(self.url, data=json.dumps(single_assignment_input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading = next(reader)
                self._check_participation_stat_report_heading_rows(heading)
                
                overall_stats = {}
                
                for student in self.fixtures.students:
                    next_row = next(reader)
                    user_stats = self._check_participation_stat_report_user_row(self.fixtures.assignments[0], student, next_row, overall_stats)
            
            # test authorized user entire course with group_name filter
            group_name_input = input.copy()
            group_name_input['group_name'] = self.fixtures.groups[0]
            rv = self.client.post(self.url, data=json.dumps(group_name_input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading = next(reader)
                assignments = self.fixtures.assignments
                self._check_participation_stat_report_heading_rows(heading)
                
                overall_stats = {}
                
                for assignment in assignments:
                    for student in self.fixtures.students:
                        if student.user_courses[0].group_name != self.fixtures.groups[0]:
                            continue
                        next_row = next(reader)
                        user_stats = self._check_participation_stat_report_user_row(assignment, student, next_row, overall_stats)
                        
                # overall 
                for student in self.fixtures.students:
                    if student.user_courses[0].group_name != self.fixtures.groups[0]:
                        continue
                    next_row = next(reader)    
                    self._check_participation_stat_report_user_overall_row(student, next_row, overall_stats)
            
            # test authorized user one assignment
            group_name_input = input.copy()
            group_name_input['group_name'] = self.fixtures.groups[0]
            group_name_input['assignment'] = self.fixtures.assignments[0].id
            rv = self.client.post(self.url, data=json.dumps(group_name_input), content_type='application/json')
            self.assert200(rv)
            self.assertIsNotNone(rv.json['file'])
            file_name = rv.json['file'].split("/")[-1]
            self.files_to_cleanup.append(file_name)
            
            tmp_name = os.path.join(current_app.config['REPORT_FOLDER'], file_name)
            with open(tmp_name, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')
                
                heading = next(reader)
                self._check_participation_stat_report_heading_rows(heading)
                
                overall_stats = {}
                
                for student in self.fixtures.students:
                    if student.user_courses[0].group_name != self.fixtures.groups[0]:
                        continue
                    next_row = next(reader)
                    user_stats = self._check_participation_stat_report_user_row(self.fixtures.assignments[0], student, next_row, overall_stats)
                       
            
        
    def _check_participation_stat_report_heading_rows(self, heading):
            expected_heading = ['Assignment', 'Username', 'Last Name', 'First Name', 
                'Answer Submitted', 'Answer ID', 'Evaluations Submitted', 'Evaluations Required', 
                'Evaluation Requirements Met', 'Replies Submitted']
                
            self.assertEqual(expected_heading, heading)
            
    def _check_participation_stat_report_user_overall_row(self, student, row, overall_stats):
            default_criteria = self.fixtures.default_criteria
            excepted_row = []
            
            overall_stats.setdefault(student.id, {
                'answers_submitted': 0,
                'evaluations_submitted': 0,
                'evaluations_required': 0,
                'evaluation_requirments_met': True,
                'replies_submitted': 0
            })
            user_stats = overall_stats[student.id]
            
            excepted_row.append("(Overall in Course)")
            excepted_row.append(str(student.id))
            excepted_row.append(student.lastname)
            excepted_row.append(student.firstname)
            excepted_row.append(str(user_stats["answers_submitted"]))
            excepted_row.append("(Overall in Course)")
            excepted_row.append(str(user_stats["evaluations_submitted"]))
            excepted_row.append(str(user_stats["evaluations_required"]))
            excepted_row.append("Yes" if user_stats["evaluation_requirments_met"] else "No")
            excepted_row.append(str(user_stats["replies_submitted"]))
            
            self.assertEqual(row, excepted_row)
            									
    
    def _check_participation_stat_report_user_row(self, assignment, student, row, overall_stats):
            default_criteria = self.fixtures.default_criteria
            excepted_row = []
            
            overall_stats.setdefault(student.id, {
                'answers_submitted': 0,
                'evaluations_submitted': 0,
                'evaluations_required': 0,
                'evaluation_requirments_met': True,
                'replies_submitted': 0
            })
            user_stats = overall_stats[student.id]
            
            excepted_row.append(assignment.name)
            excepted_row.append(student.username)
            excepted_row.append(student.lastname)
            excepted_row.append(student.firstname)
            
            answer = Answer.query \
                .filter(
                    Answer.user_id == student.id,
                    Answer.assignment_id == assignment.id
                ) \
                .first()
                
            if answer:
                user_stats["answers_submitted"] += 1
                excepted_row.append("1")
                excepted_row.append(str(answer.id))
            else:
                excepted_row.append("0")
                excepted_row.append("N/A")
            
            comparisons = Comparison.query \
                .filter(
                    Comparison.user_id == student.id,
                    Comparison.assignment_id == assignment.id,
                    Comparison.criteria_id == default_criteria.id
                ) \
                .all()
            evaulations_submitted = len(comparisons)
            
            user_stats["evaluations_submitted"] += evaulations_submitted
            excepted_row.append(str(evaulations_submitted))
            
            user_stats["evaluations_required"] += assignment.number_of_comparisons
            excepted_row.append(str(assignment.number_of_comparisons))
            
            if assignment.number_of_comparisons > evaulations_submitted:
                user_stats["evaluation_requirments_met"] = False
                excepted_row.append("No")
            else:
                excepted_row.append("Yes")
            
            answer_comments = AnswerComment.query \
                .filter(
                    AnswerComment.user_id == student.id,
                    AnswerComment.assignment_id == assignment.id
                ) \
                .all()
                
            replies_submitted = len(answer_comments)
            
            user_stats["replies_submitted"] += replies_submitted
            excepted_row.append(str(replies_submitted))
            
            self.assertEqual(row, excepted_row)
                
                
    def _check_participation_report_heading_rows(self, assignments, heading1, heading2):
            default_criteria = self.fixtures.default_criteria
            
            expected_heading1 = ['', '', '']
            for assignment in assignments:
                expected_heading1.append(assignment.name)
                expected_heading1.append("")
            
            expected_heading2 = ['Last Name', 'First Name', 'Student No']
            for assignment in assignments:
                expected_heading2.append("Percentage Score for \""+default_criteria.name+"\"")
                expected_heading2.append("Evaluations Submitted ("+str(assignment.number_of_comparisons)+" required)")
                
            self.assertEqual(expected_heading1, heading1)
            self.assertEqual(expected_heading2, heading2)
    
    def _check_participation_report_user_row(self, assignments, student, row):
            default_criteria = self.fixtures.default_criteria
            
            self.assertEqual(row[0], student.lastname)
            self.assertEqual(row[1], student.firstname)
            self.assertEqual(row[2], student.student_number)
            
            index = 3
            for assignment in assignments:
                answer = Answer.query \
                    .filter(
                        Answer.user_id == student.id,
                        Answer.assignment_id == assignment.id
                    ) \
                    .first()
                    
                if answer:
                    if len(answer.scores) > 0:
                        normalized_score = answer.scores[0].normalized_score
                        self.assertAlmostEqual(float(row[index]), normalized_score)
                    else:
                        self.assertEqual(row[index], "Not Evaluated")
                else:
                    self.assertEqual(row[index], "No Answer")
                index += 1
                
                
                comparisons = Comparison.query \
                    .filter(
                        Comparison.user_id == student.id,
                        Comparison.assignment_id == assignment.id,
                        Comparison.criteria_id == default_criteria.id
                    ) \
                    .all()
                evaulations_submitted = len(comparisons)
                
                self.assertEqual(row[index], str(evaulations_submitted))
                index += 1
            