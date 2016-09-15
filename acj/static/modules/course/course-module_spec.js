describe('course-module', function () {
    var $httpBackend, sessionRequestHandler;
    var id = "1abcABC123-abcABC123_Z";
    var mockSession = {
        "id": id,
        "permissions": {
            "Course": {
                "create": true,
                "delete": true,
                "edit": true,
                "manage": true,
                "read": true
            },
            "Assignment": {
                "create": true,
                "delete": true,
                "edit": true,
                "manage": true,
                "read": true
            },
            "User": {
                "create": true,
                "delete": true,
                "edit": true,
                "manage": true,
                "read": true
            }
        }
    };
    var mockUser = {
        avatar: "63a9f0ea7bb98050796b649e85481845",
        created: "Tue, 27 May 2014 00:02:38 -0000",
        displayname: "root",
        email: null,
        firstname: "John",
        fullname: "John Smith",
        id: id,
        lastname: "Smith",
        last_online: "Tue, 12 Aug 2014 20:53:31 -0000",
        modified: "Tue, 12 Aug 2014 20:53:31 -0000",
        username: "root",
        system_role: "System Administrator"
    };
    var mockCourse = {
        "available": true,
        "start_date": null,
        "end_date": null,
        "created": "Fri, 09 Jan 2015 17:23:59 -0000",
        "description": null,
        "id": "1abcABC123-abcABC123_Z",
        "modified": "Fri, 09 Jan 2015 17:23:59 -0000",
        "name": "Test Course",
        "year": 2015,
        "term": "Winter"
    };
    beforeEach(module('ubc.ctlt.acj.course'));
    beforeEach(inject(function ($injector) {
        $httpBackend = $injector.get('$httpBackend');
        sessionRequestHandler = $httpBackend.when('GET', '/api/session').respond(mockSession);
        $httpBackend.when('GET', '/api/users/' + id).respond(mockUser);
    }));

    afterEach(function () {
        $httpBackend.verifyNoOutstandingExpectation();
        $httpBackend.verifyNoOutstandingRequest();
    });

    describe('CourseController', function () {
        var $rootScope, createController, $location, $modal, $q;

        beforeEach(inject(function ($controller, _$rootScope_, _$location_, _$modal_, _$q_) {
            $rootScope = _$rootScope_;
            $location = _$location_;
            $modal = _$modal_;
            $q = _$q_;
            createController = function (route, params) {
                return $controller('CourseController', {
                    $scope: $rootScope,
                    $routeParams: params || {},
                    $route: route || {}
                });
            }
        }));

        it('should have correct initial states', function () {
            //double check nothing to initialize
        });

        describe('view:', function () {
            var controller;
            describe('new', function () {
                var toaster;
                var course = {
                    "name": "Test111",
                    "year": 2015,
                    "term": "Winter",
                    "start_date": null,
                    "end_date": null,
                    "descriptionCheck": true,
                    "description": "<p>Description</p>\n"
                };
                beforeEach(inject(function (_Toaster_) {
                    toaster = _Toaster_;
                    spyOn(toaster, 'error');
                }));

                beforeEach(function () {
                    controller = createController({current: {method: 'new'}});
                });

                it('should be correctly initialized', function () {
                    //double check nothing to initialize
                });

                it('should error when start date is not before end date', function () {
                    $rootScope.course = angular.copy(course);
                    $rootScope.course.id = undefined;
                    $rootScope.date.course_start.date = new Date();
                    $rootScope.date.course_start.time = new Date();
                    $rootScope.date.course_end.date = new Date();
                    $rootScope.date.course_end.time = new Date();
                    $rootScope.date.course_end.date.setDate($rootScope.date.course_end.date.getDate()-1);
                    var currentPath = $location.path();

                    $rootScope.save();
                    expect($rootScope.submitted).toBe(false);
                    expect(toaster.error).toHaveBeenCalledWith('Course Period Conflict', 'Course end date/time must be after course start date/time.');
                    expect($location.path()).toEqual(currentPath);
                });

                it('should be able to save new course', function () {
                    $rootScope.course = angular.copy(course);
                    $rootScope.course.id = undefined;
                    $httpBackend.expectPOST('/api/courses', $rootScope.course).respond(angular.merge({}, course, {id: "2abcABC123-abcABC123_Z",}));
                    $rootScope.save();
                    expect($rootScope.submitted).toBe(true);
                    $httpBackend.flush();
                    expect($location.path()).toEqual('/course/2abcABC123-abcABC123_Z');
                    expect($rootScope.submitted).toBe(false);
                });
            });

            describe('edit', function () {
                var editCourse;
                var toaster;
                beforeEach(inject(function (_Toaster_) {
                    toaster = _Toaster_;
                    spyOn(toaster, 'error');
                }));

                beforeEach(function () {
                    editCourse = angular.copy(mockCourse);
                    editCourse.id = "2abcABC123-abcABC123_Z";
                    controller = createController({current: {method: 'edit'}}, {courseId: "2abcABC123-abcABC123_Z"});
                    $httpBackend.expectGET('/api/courses/2abcABC123-abcABC123_Z').respond(editCourse);
                    $httpBackend.flush();
                });

                it('should be correctly initialized', function () {
                    expect($rootScope.course).toEqualData(_.merge(editCourse));
                });

                it('should error when start date is not before end date', function () {
                    var editedCourse = angular.copy(editCourse);
                    $rootScope.course = editedCourse;
                    $rootScope.date.course_start.date = new Date();
                    $rootScope.date.course_start.time = new Date();
                    $rootScope.date.course_end.date = new Date();
                    $rootScope.date.course_end.time = new Date();
                    $rootScope.date.course_end.date.setDate($rootScope.date.course_end.date.getDate()-1);
                    var currentPath = $location.path();

                    $rootScope.save();
                    expect($rootScope.submitted).toBe(false);
                    expect(toaster.error).toHaveBeenCalledWith('Course Period Conflict', 'Course end date/time must be after course start date/time.');
                    expect($location.path()).toEqual(currentPath);
                });

                it('should be able to save edited course', function () {
                    var editedCourse = angular.copy(editCourse);
                    editedCourse.name = 'new name';
                    editedCourse.year = 2016;
                    editedCourse.term = "Summer";
                    $rootScope.course = editedCourse;
                    $httpBackend.expectPOST('/api/courses/2abcABC123-abcABC123_Z', $rootScope.course).respond(editedCourse);
                    $rootScope.save();
                    expect($rootScope.submitted).toBe(true);
                    $httpBackend.flush();
                    expect($location.path()).toEqual('/course/2abcABC123-abcABC123_Z');
                    expect($rootScope.submitted).toBe(false);
                });

                it('should enable save button even if save failed', function() {
                    $rootScope.course = angular.copy(editCourse);
                    $httpBackend.expectPOST('/api/courses/2abcABC123-abcABC123_Z', $rootScope.course).respond(400, '');
                    $rootScope.save();
                    expect($rootScope.submitted).toBe(true);
                    $httpBackend.flush();
                    expect($rootScope.submitted).toBe(false);
                });
            });
        });
    });
});