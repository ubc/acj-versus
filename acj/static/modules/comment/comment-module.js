// Handles comment creation and editing.

(function() {

var module = angular.module('ubc.ctlt.acj.comment',
	[
		'ngResource',
		'ubc.ctlt.acj.answer',
		'ubc.ctlt.acj.classlist',
		'ubc.ctlt.acj.common.form',
		'ubc.ctlt.acj.common.mathjax',
		'ubc.ctlt.acj.common.interceptor',
		'ubc.ctlt.acj.course',
		'ubc.ctlt.acj.criteria',
		'ubc.ctlt.acj.judgement',
		'ubc.ctlt.acj.question',
		'ubc.ctlt.acj.toaster'
	]
);

/***** Providers *****/
module.factory(
	"QuestionCommentResource",
	function ($resource)
	{
		var ret = $resource(
			'/api/courses/:courseId/questions/:questionId/comments/:commentId',
			{commentId: '@id'}
		);
		ret.MODEL = "PostsForQuestionsAndPostsForComments";
		return ret;
	}
);

module.factory(
	"AnswerCommentResource",
	function ($resource, Interceptors)
	{
		var url = '/api/courses/:courseId/questions/:questionId/answers/:answerId/comments/:commentId';
		var ret = $resource(
			url, {commentId: '@id'},
			{
				'save': {method: 'POST', url: url, interceptor: Interceptors.answerCache},
				'delete': {method: 'DELETE', url: url, interceptor: Interceptors.answerCache},
				selfEval: {url: '/api/selfeval/courses/:courseId/questions/:questionId'},
				allSelfEval: {url: '/api/selfeval/courses/:courseId/questions'}
			}
		);
		ret.MODEL = "PostsForAnswersAndPostsForComments";
		return ret;
	}
);

module.factory(
	"UserAnswerCommentResource",
	function ($resource)
	{
		var ret = $resource(
			'/api/courses/:courseId/questions/:questionId/answers/:answerId/users/comments'
		);
		ret.MODEL = "PostsForAnswersAndPostsForComments";
		return ret;
	}
);

/***** Controllers *****/
module.controller(
	"QuestionCommentCreateController",
	function ($scope, $log, $location, $routeParams, QuestionCommentResource, QuestionResource, Toaster)
	{
		var courseId = $scope.courseId = $routeParams['courseId'];
		var questionId = $scope.questionId = $routeParams['questionId'];
	
		$scope.comment = {};
		QuestionResource.get({'courseId': courseId, 'questionId': questionId}).$promise.then(
			function(ret) {
				$scope.parent = ret.question;
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve the question "+questionId, ret);
			}
		);
		$scope.commentSubmit = function () {
			$scope.submitted = true;
			QuestionCommentResource.save({'courseId': courseId, 'questionId': questionId},
				$scope.comment).$promise.then(
					function (ret)
					{
						$scope.submitted = false;
						Toaster.success("New comment posted!");
						$location.path('/course/'+courseId+'/question/'+questionId);
					},
					function (ret)
					{
						$scope.submitted = false;
						Toaster.reqerror("Unable to post new comment.", ret);
					}
				);
		};
	}
);

module.controller(
	"QuestionCommentEditController",
	function ($scope, $log, $location, $routeParams, QuestionCommentResource, QuestionResource, Toaster)
	{
		var courseId = $scope.courseId = $routeParams['courseId'];
		var questionId = $scope.questionId = $routeParams['questionId'];
		var commentId = $routeParams['commentId'];

		$scope.comment = {};
		$scope.parent = {}; // question
		QuestionCommentResource.get({'courseId': courseId, 'questionId': questionId, 'commentId': commentId}).$promise.then(
			function(ret) {
				$scope.comment = ret;
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve comment "+commentId, ret);
			}
		);
		QuestionResource.get({'courseId': courseId, 'questionId': questionId}).$promise.then(
			function(ret) {
				$scope.parent = ret.question;
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve the question "+questionId, ret);
			}
		);
		$scope.commentSubmit = function () {
			QuestionCommentResource.save({'courseId': courseId, 'questionId': questionId}, $scope.comment).$promise.then(
				function() { 
					Toaster.success("Comment Updated!");
					$location.path('/course/' + courseId + '/question/' +questionId);
				},
				function(ret) { Toaster.reqerror("Comment Save Failed.", ret);}
			);
		};
	}
);

module.controller(
	"AnswerCommentCreateController",
	function ($scope, $log, $location, $routeParams, AnswerCommentResource, AnswerResource,
			  QuestionResource, Authorize, Toaster)
	{
		var courseId = $scope.courseId = $routeParams['courseId'];
		var questionId = $scope.questionId = $routeParams['questionId'];
		var answerId = $routeParams['answerId'];
		$scope.answerComment = true;
		$scope.canManagePosts = 
			Authorize.can(Authorize.MANAGE, QuestionResource.MODEL, courseId);
		$scope.comment = {};

		AnswerResource.get({'courseId': courseId, 'questionId': questionId, 'answerId': answerId}).$promise.then(
			function (ret) {
				$scope.parent = ret;
				$scope.replyToUser = ret.user_displayname;
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve answer "+answerId, ret);
			}
		);

		// only need to do this query if the user cannot manage users
		QuestionResource.get({'courseId': courseId, 'questionId': questionId}).$promise.then(
			function (ret) {
				if (!$scope.canManagePosts && !ret.question.can_reply) {
					Toaster.error("No replies can be made for answers in this question.");
					$location.path('/course/' + courseId + '/question/' + questionId);
				}
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve the question.", ret);
			});
		$scope.commentSubmit = function () {
			$scope.submitted = true;
			AnswerCommentResource.save({'courseId': courseId, 'questionId': questionId, 'answerId': answerId},
				$scope.comment).$promise.then(
					function (ret)
					{
						$scope.submitted = false;
						Toaster.success("New reply posted!");
						$location.path('/course/'+courseId+'/question/'+questionId);
					},
					function (ret)
					{
						$scope.submitted = false;
						Toaster.reqerror("Unable to post new reply.", ret);
					}
				);
		};	
	}
);

module.controller(
	"AnswerCommentEditController",
	function ($scope, $log, $location, $routeParams, AnswerCommentResource, AnswerResource, Toaster)
	{
		var courseId = $scope.courseId = $routeParams['courseId'];
		var questionId = $scope.questionId = $routeParams['questionId'];
		var answerId = $routeParams['answerId'];
		var commentId = $routeParams['commentId'];
		$scope.answerComment = true;

		$scope.comment = {};
		$scope.parent = {}; // answer
		AnswerCommentResource.get({'courseId': courseId, 'questionId': questionId, 'answerId': answerId, 'commentId': commentId}).$promise.then(
			function(ret) {
				$scope.comment = ret;
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve reply "+commentId, ret);
			}
		);
		AnswerResource.get({'courseId': courseId, 'questionId': questionId, 'answerId': answerId}).$promise.then(
			function (ret) {
				$scope.parent = ret;
				$scope.replyToUser = ret.user_displayname;
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve answer "+answerId, ret);
			}
		);
		$scope.commentSubmit = function () {
			AnswerCommentResource.save({'courseId': courseId, 'questionId': questionId, 'answerId': answerId}, $scope.comment).$promise.then(
				function() {
					Toaster.success("Reply Updated!");
					$location.path('/course/' + courseId + '/question/' +questionId);
				},
				function(ret) { Toaster.reqerror("Reply Not Updated", ret);}
			);
		};
	}
);

module.controller(
	"JudgementCommentController",
	function ($scope, $log, $routeParams, breadcrumbs, EvalCommentResource, CoursesCriteriaResource,
			  CourseResource, QuestionResource, AnswerResource, AttachmentResource, GroupResource, Toaster)
	{
		var courseId = $routeParams['courseId'];
		var questionId = $routeParams['questionId'];
		$scope.search = {'userId': null};
		$scope.course = {};
		$scope.courseId = courseId;
		$scope.questionId = questionId;
		$scope.deletedAnsMsg = '<i>(This answer has been deleted.)</i>';
		$scope.noAnsMsg = '<p><i>(No answer has been submitted by this student.)</i></p>';

		var allStudents = {};
		var userIds = {};
		$scope.group = null;

		$scope.ans = {};
		$scope.userToAns = {};
		var gotAnswers = false;

		CourseResource.get({'id':courseId}).$promise.then(
			function (ret) {
				breadcrumbs.options = {'Course Questions': ret['name']};
			},
			function (ret) {
				Toaster.reqerror("Course Not Found For ID "+ courseId, ret);
			}
		);

		EvalCommentResource.view({'courseId': courseId, 'questionId': questionId}).$promise.then(
			function (ret) {
				$scope.comparisons = ret.comparisons;
			},
			function (ret) {
				Toaster.reqerorr('Error', ret);
			}
		);

		CourseResource.getStudents({'id': courseId}).$promise.then(
			function (ret) {
				allStudents = ret.students;
				userIds = getUserIds(allStudents);
				$scope.students = allStudents;
			},
			function (ret) {
				Toaster.reqerror("Class list retrieval failed", ret);
			}
		);
		
		QuestionResource.get({'courseId': courseId, 'questionId': questionId}).$promise.then(
			function(ret) {
				$scope.parent = ret.question;
				$scope.criteria = {};
				angular.forEach(ret.question.criteria, function(criterion, key){
					$scope.criteria[criterion['id']] = criterion['criterion']['name'];
				});
				$scope.search.criteriaId = $scope.criteria[0];
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve the question "+questionId, ret);
			}
		);

		GroupResource.get({'courseId': courseId}).$promise.then(
			function (ret) {
				$scope.groups = ret.groups;
			},
			function (ret) {
				Toaster.reqerror("Unable to retrieve the groups in the course.", ret);
			}
		);

		var getUserIds = function(students) {
			var users = {};
			angular.forEach(students, function(s, key){
				users[s.user.id] = 1;
			});
			return users;
		};

		$scope.updateGroup = function() {
			$scope.search.userId = null;
			if ($scope.group == null) {
				$scope.students = allStudents;
				userIds = getUserIds($scope.students);
			} else {
				GroupResource.get({'courseId': courseId, 'groupId': $scope.group.id}).$promise.then(
					function (ret) {
						$scope.students = ret.students;
						userIds = getUserIds($scope.students);
					},
					function (ret) {
						Toaster.reqerror("Unable to retrieve the group members", ret);
					}
				);
			}
		};

		$scope.commentFilter = function(user_id) {
			return function(comment) {
				return ((user_id == null && comment[0].user_id in userIds) || comment[0].user_id == user_id);
			}
		};

		$scope.answers = function() {
			if (!gotAnswers) {
				AnswerResource.get({'courseId': courseId, 'questionId': questionId}).$promise.then(
					function (ret) {
						for (var key in ret.objects) {
							var answer = ret.objects[key];
							var scores = {};
							for (var index in answer.scores) {
								scores[answer.scores[index].criteriaandquestions_id] = answer.scores[index].normalized_score;
							}
							answer.scores = scores;
							$scope.ans[answer.id] = answer;
							$scope.userToAns[answer.user_id] = answer.id;
						}
						gotAnswers = true;
					},
					function (ret) {
						Toaster.reqerror("Failed to retrieve the answers", ret);
					}
				);
			}
		};
	}
);

// End anonymouse function
}) ();
