var UserFactory = require('../../factories/user_factory.js');
var userFactory = new UserFactory();

var SessionFactory  = require('../../factories/session_factory.js');
var sessionFactory = new SessionFactory();

var CourseFactory  = require('../../factories/course_factory.js');
var courseFactory = new CourseFactory();

var storage = {
    session: {},
    users: {},
    courses: {},
    user_courses: {}
}

var admin = userFactory.generateUser("1abcABC123-abcABC123_Z", "System Administrator", {
    username: "root",
    displayname: "root",
    firstname: "JaNy",
    lastname: "bwsV",
    fullname: "JaNy bwsV",
});
storage.users[admin.id] = admin;

var course1 = courseFactory.generateCourse("1abcABC123-abcABC123_Z", {
    name: "CHEM 111",
    year: 2015,
    term: "Winter",
    description: "<p>CHEM 111 description<p>",
});
storage.courses[course1.id] = course1;

var course2 = courseFactory.generateCourse("2abcABC123-abcABC123_Z", {
    name: "PHYS 101",
    year: 2015,
    term: "Winter",
    description: "<p>PHYS 101  description<p>",
});
storage.courses[course2.id] = course2;

// user_courses
storage.user_courses[admin.id] = [
    { courseId: course1.id, courseRole: "Instructor", groupName: null },
    { courseId: course2.id, courseRole: "Instructor", groupName: null }
];


storage.loginDetails = { id: admin.id, username: admin.username, password: "password" };
storage.session = sessionFactory.generateSession(admin.id, admin.system_role, {});

module.exports = storage;