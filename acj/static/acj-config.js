var myApp = angular.module('myApp', [
	'ngRoute', 
	'http-auth-interceptor', 
	'ngCookies', 
	'ng-breadcrumbs',
	'angular-loading-bar',
	'ubc.ctlt.acj.answer',
	'ubc.ctlt.acj.classlist',
	'ubc.ctlt.acj.comment',
	'ubc.ctlt.acj.course',
	'ubc.ctlt.acj.criteria',
	'ubc.ctlt.acj.home',
	'ubc.ctlt.acj.judgement',
	'ubc.ctlt.acj.login',
	'ubc.ctlt.acj.navbar',
	'ubc.ctlt.acj.question'
]);

myApp.config( function ($routeProvider) {
	$routeProvider
		.when ('/', 
			{
				templateUrl: 'modules/home/home-partial.html',
				label: "Home" // breadcrumb label
			})
		.when ('/course/new', 
			{
				templateUrl: 'modules/course/course-create-partial.html',
				label: "Create New Course"
			})
		.when ('/course/:courseId', 
			{
				templateUrl: 'modules/course/course-questions-partial.html',
				label: "Course Questions"
			})
		.when ('/course/:courseId/configure', 
			{
				templateUrl: 'modules/course/course-configure-partial.html',
				label: "Course Configuration"
			})
		.when ('/course/:courseId/user',
			{
				templateUrl: 'modules/classlist/classlist-view-partial.html',
				label: "Class List"
			})
		.when ('/course/:courseId/question/create', 
			{
				templateUrl: 'modules/question/question-create-partial.html',
				label: "Create Question"
			})
		.when ('/course/:courseId/question/:questionId', 
			{
				templateUrl: 'modules/question/question-view-partial.html',
				label: "View Question"
			})
		.when ('/course/:courseId/question/:questionId/edit',
			{
				templateUrl: 'modules/question/question-edit-partial.html',
				label: "Question Configuration"
			})
		.when ('/course/:courseId/question/:questionId/answer/create', 
			{
				templateUrl: 'modules/answer/answer-create-partial.html',
				label: "Post Answer"
			})
		.when ('/course/:courseId/question/:questionId/answer/:answerId/edit',
			{
				templateUrl: 'modules/answer/answer-edit-partial.html',
				label: "Edit Answer"
			})
		.when ('/course/:courseId/question/:questionId/comment/create',
			{
				templateUrl: 'modules/comment/comment-question-create-partial.html',
				label: "Post Comment"
			})
		.when ('/course/:courseId/question/:questionId/comment/:commentId/edit',
			{
				templateUrl: 'modules/comment/comment-question-edit-partial.html',
				label: "Edit Comment"
			})
		.when('/course/:courseId/question/:questionId/answer/:answerId/comment/create',
			{
				templateUrl: 'modules/comment/comment-answer-create-partial.html',
				label: "Post Comment"
			})
		.when('/course/:courseId/question/:questionId/answer/:answerId/comment/:commentId/edit',
			{
				templateUrl: 'modules/comment/comment-answer-edit-partial.html',
				label: "Edit Comment"
			})
		.when ('/course/:courseId/question/:questionId/judgement', 
			{
				templateUrl: 'modules/judgement/judgement-partial.html',
				label: "Evaluate Answers"
			})
		.when('/user/create',
			{
				templateUrl: 'modules/user/user-create-partial.html',
				label: "Create User"
			})
		.when('/user/:userId/edit',
			{
				templateUrl: 'modules/user/user-edit-partial.html',
				label: "Edit User"
			})
		.when('/user/:userId',
			{
				templateUrl: 'modules/user/user-view-partial.html',
				label: "View User"
			})
		.when('/user/profile',
			{
				templateUrl: 'modules/user/user-edit-profile-partial.html',
				label: "User Profile"
			})
		.otherwise({redirectTo: '/'});
});
