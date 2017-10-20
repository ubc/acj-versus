// Controls the home page for this application, which is mainly just a listing
// of courses which this user is enroled in.

// Isolate this module's creation by putting it in an anonymous function
(function() {

var module = angular.module('ubc.ctlt.compair.home',
    [
        'ngSanitize',
        'ubc.ctlt.compair.common.xapi',
        'ubc.ctlt.compair.authentication',
        'ubc.ctlt.compair.authorization',
        'ubc.ctlt.compair.course',
        'ubc.ctlt.compair.toaster',
        'ubc.ctlt.compair.user',
        'ui.bootstrap'
    ]
);

/***** Providers *****/
// module.factory(...)

/***** Controllers *****/
module.controller(
    'HomeController',
    ["$rootScope", "$scope", "$location", "AssignmentResource",
     "Authorize", "CourseResource", "Toaster", "UserResource", "$uibModal", "xAPIStatementHelper", "resolvedData",
    function ($rootScope, $scope, $location, AssignmentResource,
              Authorize, CourseResource, Toaster, UserResource, $uibModal, xAPIStatementHelper, resolvedData)
    {
        $scope.totalNumCourses = 0;
        $scope.courseFilters = {
            page: 1,
            perPage: 10,
            search: null,
            includeSandbox: null
        };
        $scope.canAddCourse = resolvedData.canAddCourse;
        $scope.loggedInUserId = resolvedData.loggedInUser.id;
        $scope.canManageUsers = resolvedData.canManageUsers;

        $scope.updateCourseList = function() {
            UserResource.getUserCourses($scope.courseFilters).$promise.then(
                function(ret) {
                    $scope.courses = ret.objects;
                    $scope.totalNumCourses = ret.total;

                    _.forEach($scope.courses, function(course) {
                        Authorize.can(Authorize.MANAGE, AssignmentResource.MODEL, course.id).then(function(result) {
                            course.canManageAssignment = result;
                        });
                        Authorize.can(Authorize.EDIT, CourseResource.MODEL, course.id).then(function(result) {
                            course.canEditCourse = result;
                        });
                        Authorize.can(Authorize.DELETE, CourseResource.MODEL, course.id).then(function(result) {
                            course.canDeleteCourse = result;
                        });
                    });

                    var courseIds = $scope.courses.map(function(course) {
                        return course.id;
                    });
                    if (courseIds.length > 0) {
                        UserResource.getUserCoursesStatus({ ids: courseIds.join(",") }).$promise.then(
                            function(ret) {
                                var statuses = ret.statuses;
                                _.forEach($scope.courses, function(course) {
                                    course.status = statuses[course.id];
                                });
                            }
                        );
                    }
                }
            );
        };

        $scope.deleteCourse = function(course) {
            CourseResource.delete({'id': course.id},
                function (ret) {
                    Toaster.success('Course Deleted');
                    $scope.updateCourseList();
                }
            );
        };

        $scope.duplicateCourse = function(course) {
            var modalScope = $scope.$new();
            modalScope.originalCourse = course;

            $scope.modalInstance = $uibModal.open({
                animation: true,
                backdrop: 'static',
                controller: "CourseDuplicateModalController",
                templateUrl: 'modules/course/course-duplicate-partial.html',
                scope: modalScope
            });

            $scope.modalInstance.opened.then(function() {
                xAPIStatementHelper.opened_modal("Duplicate Course");
            });

            $scope.modalInstance.result.then(function (courseId) {
                $location.path('/course/' + courseId);
                xAPIStatementHelper.closed_modal("Duplicate Course");
            }, function () {
                //cancelled, do nothing
                xAPIStatementHelper.closed_modal("Duplicate Course");
            });
        };

        var filterWatcher = function(newValue, oldValue) {
            if (angular.equals(newValue, oldValue)) return;
            if (oldValue.search != newValue.search) {
                $scope.courseFilters.page = 1;
            }
            if(newValue.search === "") {
                $scope.courseFilters.search = null;
            }
            xAPIStatementHelper.filtered_page($scope.courseFilters);
            $scope.updateCourseList();
        };

        $scope.updateCourseList();
        $scope.$watchCollection('courseFilters', filterWatcher);
    }
]);
// End anonymous function
})();
