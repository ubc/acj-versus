// TODO
// Insert short explanation of what this module does, for this module, it'd be:
// An example/template of how to create functionally isolated modules in
// Angular for organizing code.

// Isolate this module's creation by putting it in an anonymous function
(function() {

var module = angular.module('ubc.ctlt.compair.user', [
    'ngResource',
    'ngRoute',
    'ng-breadcrumbs',
    'ubc.ctlt.compair.session',
    'ubc.ctlt.compair.authorization',
    'ubc.ctlt.compair.toaster'
]);

/***** Providers *****/
module.factory('UserResource', ['$resource', function($resource) {
    var User = $resource('/api/users/:id', {id: '@id'}, {
        getUserCourses: {url: '/api/users/courses'},
        getUserCoursesById: {url: '/api/users/:id/courses'},
        getUserCoursesStatus: {url: '/api/users/courses/status'},
        getTeachingUserCourses: {url: '/api/users/courses/teaching'},
        getEditButton: {url: '/api/users/:id/edit'},
        updateNotifcations: {method: 'POST', url: '/api/users/:id/notification'},
        password: {method: 'POST', url: '/api/users/:id/password'}
    });
    User.MODEL = "User";

    User.prototype.isLoggedIn = function() {
        return this.hasOwnProperty('id');
    };

    return User;
}]);

module.constant('UserSettings', {
    notifications: false
});

module.constant('SystemRole', {
    student: "Student",
    instructor: "Instructor",
    sys_admin: "System Administrator"
});

module.constant('EmailNotificationMethod', {
    enable: "enable",
    disable: "disable",
    //digest: "digest"
});

module.constant('CourseRole', {
    dropped: "Dropped",
    instructor: "Instructor",
    teaching_assistant: "Teaching Assistant",
    student: "Student"
});

/***** Controllers *****/
module.controller("UserWriteController",
    ['$scope', '$route', '$routeParams', '$location', 'breadcrumbs', 'Session',
     'UserResource', 'SystemRole', 'Toaster', 'resolvedData', 'UserSettings', 'EmailNotificationMethod',
    function($scope, $route, $routeParams, $location, breadcrumbs, Session,
             UserResource, SystemRole, Toaster, resolvedData, UserSettings, EmailNotificationMethod)
    {
        $scope.userId = $routeParams.userId;

        $scope.user = resolvedData.user || {};
        $scope.canManageUsers = resolvedData.canManageUsers;
        $scope.loggedInUser = resolvedData.loggedInUser;
        $scope.ownProfile = $scope.loggedInUser.id == $scope.userId;
        $scope.loggedInUserIsInstructor = $scope.loggedInUser.system_role == SystemRole.instructor;

        $scope.method = $scope.user.id ? 'edit' : 'create';
        $scope.password = {};

        $scope.UserSettings = UserSettings;
        $scope.EmailNotificationMethod = EmailNotificationMethod;
        $scope.SystemRole = SystemRole;
        $scope.system_roles = [SystemRole.student, SystemRole.instructor, SystemRole.sys_admin]
        // remove system admin from system roles if current_user is not an admin
        if ($scope.user.system_role != SystemRole.sys_admin) {
            $scope.system_roles.pop()
        }

        if ($scope.method == 'edit') {
            breadcrumbs.options = {'View User': "{0}'s Profile".format($scope.user.displayname)};
        } else if ($scope.method == 'create') {
            $scope.user.uses_compair_login = true;
            $scope.user.email_notification_method = EmailNotificationMethod.enable;
            $scope.user.system_role = SystemRole.student;
        }

        $scope.save = function() {
            $scope.submitted = true;

            UserResource.save({'id': $scope.userId}, $scope.user, function(ret) {
                if ($scope.method == 'edit') {
                    Toaster.success('User Successfully Updated', 'Your changes were saved.');
                } else if ($scope.method == 'create') {
                    Toaster.success('New User Created', 'User should now have access.');
                }
                // refresh User's info on editing own profile and displayname changed
                if ($scope.ownProfile && $scope.user.displayname != $scope.loggedInUser.displayname) {
                    Session.refresh();
                }
                $location.path('/user/' + ret.id);
            }).$promise.finally(function() {
                $scope.submitted = false;
            });
        };

        $scope.changePassword = function() {
            $scope.submitted = true;
            UserResource.password({'id': $scope.user.id}, $scope.password, function (ret) {
                Toaster.success("Password Successfully Updated", "Your password has been changed.");
                $location.path('/user/' + ret.id);
            }).$promise.finally(function() {
                $scope.submitted = false;
            });
        };
    }]
);

module.controller("UserViewController",
    ['$scope', '$routeParams', 'breadcrumbs', 'SystemRole', 'resolvedData',
     'UserResource', 'UserSettings', 'EmailNotificationMethod', 'Toaster',
    function($scope, $routeParams, breadcrumbs, SystemRole, resolvedData,
             UserResource, UserSettings, EmailNotificationMethod, Toaster)
    {
        $scope.userId = $routeParams.userId;

        $scope.user = resolvedData.user;
        $scope.showEditButton = resolvedData.userEditButton;
        $scope.canManageUsers = resolvedData.canManageUsers;
        $scope.loggedInUser = resolvedData.loggedInUser;
        $scope.ownProfile = $scope.loggedInUser.id == $scope.userId;
        $scope.loggedInUserIsInstructor = $scope.loggedInUser.system_role == SystemRole.instructor;
        $scope.UserSettings = UserSettings;
        $scope.EmailNotificationMethod = EmailNotificationMethod;

        $scope.SystemRole = SystemRole;
        breadcrumbs.options = {'View User': "{0}'s Profile".format($scope.user.displayname)};

        $scope.updateNotificationSettings = function() {
            $scope.submitted = true;

            UserResource.updateNotifcations({'id': $scope.userId}, $scope.user, function(ret) {
                Toaster.success('Notification Settings Successfully Updated', 'Your changes were saved.');
            }).$promise.finally(function() {
                $scope.submitted = false;
            });
        };
    }]
);

module.controller("UserListController",
    ['$scope', '$location', 'UserResource', 'Toaster', 'breadcrumbs', 'SystemRole',
     'xAPIStatementHelper', 'resolvedData',
    function($scope, $location, UserResource, Toaster, breadcrumbs, SystemRole,
             xAPIStatementHelper, resolvedData)
    {
        $scope.loggedInUserId = resolvedData.loggedInUser.id;
        $scope.canManageUsers = resolvedData.canManageUsers;

        $scope.predicate = 'firstname';
        $scope.reverse = false;
        $scope.users = [];
        $scope.totalNumUsers = 0;
        $scope.userFilters = {
            page: 1,
            perPage: 20,
            search: null,
            orderBy: null,
            reverse: null
        };

        // redirect user if doesn't have permission to view page
        if (!$scope.canManageUsers) {
            $location.path('/');
        }

        $scope.updateUser = function(user) {
            UserResource.save({'id': user.id}, user,
                function (ret) {
                    Toaster.success("User Successfully Updated", 'Your changes were saved.');
                    $route.reload();
                }
            );
        };

        $scope.updateTableOrderBy = function(predicate) {
            $scope.reverse = $scope.predicate == predicate && !$scope.reverse;
            $scope.predicate = predicate;
            $scope.userFilters.orderBy = $scope.predicate;
            $scope.userFilters.reverse = $scope.reverse ? true : null;
        };

        $scope.updateUserList = function() {
            UserResource.get($scope.userFilters).$promise.then(
                function(ret) {
                    $scope.users = ret.objects;
                    $scope.totalNumUsers = ret.total;
                }
            );
        };
        $scope.updateUserList();

        var filterWatcher = function(newValue, oldValue) {
            if (angular.equals(newValue, oldValue)) return;
            if (oldValue.search != newValue.search) {
                $scope.userFilters.page = 1;
            }
            if (oldValue.orderBy != newValue.orderBy) {
                $scope.userFilters.page = 1;
            }
            if(newValue.search === "") {
                $scope.userFilters.search = null;
            }
            xAPIStatementHelper.filtered_page($scope.userFilters);
            $scope.updateUserList();
        };
        $scope.$watchCollection('userFilters', filterWatcher);
    }]
);

module.controller("UserCourseController",
    ['$scope', '$location', '$route', '$routeParams', 'UserResource', 'CourseResource', 'GroupResource', 'ClassListResource',
     'Toaster', 'breadcrumbs', 'CourseRole', 'xAPIStatementHelper', "moment", "resolvedData",
    function($scope, $location, $route, $routeParams, UserResource, CourseResource, GroupResource, ClassListResource,
             Toaster, breadcrumbs, CourseRole, xAPIStatementHelper, moment, resolvedData)
    {
        $scope.userId = $routeParams.userId;

        $scope.user = resolvedData.user;
        $scope.canManageUsers = resolvedData.canManageUsers;

        $scope.totalNumCourses = 0;
        $scope.courseFilters = {
            page: 1,
            perPage: 20,
            search: null,
            orderBy: null,
            reverse: null
        };

        breadcrumbs.options = {'Manage User Courses': "Manage {0}'s Courses".format($scope.user.displayname)};
        $scope.course_roles = [CourseRole.student, CourseRole.teaching_assistant, CourseRole.instructor];

        if (!$scope.canManageUsers) {
            $location.path('/');
        }

        $scope.updateTableOrderBy = function(predicate) {
            $scope.reverse = $scope.predicate == predicate && !$scope.reverse;
            $scope.predicate = predicate;
            $scope.courseFilters.orderBy = $scope.predicate;
            $scope.courseFilters.reverse = $scope.reverse ? true : null;
        };

        $scope.updateCourseList = function() {
            var params = angular.merge({'id': $scope.userId}, $scope.courseFilters);
            UserResource.getUserCoursesById(params).$promise.then(
                function(ret) {
                    $scope.courses = ret.objects;
                    _.forEach($scope.courses, function(course) {
                        course.completed = course.end_date && moment().isAfter(course.end_date);
                        course.before_start = course.start_date && moment().isBefore(course.start_date);
                        course.in_progress = !(course.completed || course.before_start);

                        course.groups = [];
                        GroupResource.get({'courseId':course.id}).$promise.then(
                            function (ret) {
                                course.groups = ret.objects;
                            }
                        );
                    });
                    $scope.totalNumCourses = ret.total;
                }
            );
        };
        $scope.updateCourseList();

        $scope.dropCourse = function(course) {
            ClassListResource.unenrol({'courseId': course.id, 'userId': $scope.userId},
                function (ret) {
                    Toaster.success("User Removed", "Successfully unenrolled " + ret.fullname + " from the course.");
                    $route.reload();
                }
            )
        };

        $scope.updateRole = function(course) {
            ClassListResource.enrol({'courseId': course.id, 'userId': $scope.userId}, course,
                function (ret) {
                    Toaster.success("User Added", 'Successfully changed '+ ret.fullname +'\'s course role to ' + ret.course_role);
                }
            );
        };

        $scope.updateGroup = function(course) {
            if (course.group_name && course.group_name != "") {
                GroupResource.enrol({'courseId': course.id, 'userId': $scope.userId, 'groupName': course.group_name}, {},
                    function (ret) {
                        Toaster.success("Update Complete", "Successfully added the user to group " + ret.group_name);
                    }
                );
            } else {
                GroupResource.unenrol({'courseId': course.id, 'userId': $scope.userId},
                    function (ret) {
                        Toaster.success("User Removed", "Successfully removed the user from the group.");
                    }
                );
            }
        };

        var filterWatcher = function(newValue, oldValue) {
            if (angular.equals(newValue, oldValue)) return;
            if (oldValue.search != newValue.search) {
                $scope.courseFilters.page = 1;
            }
            if (oldValue.orderBy != newValue.orderBy) {
                $scope.courseFilters.page = 1;
            }
            if(newValue.search === "") {
                $scope.courseFilters.search = null;
            }
            xAPIStatementHelper.filtered_page($scope.courseFilters);
            $scope.updateCourseList();
        };
        $scope.$watchCollection('courseFilters', filterWatcher);
    }]
);

// End anonymous function
})();
