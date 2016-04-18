Feature: Create Course
  As user, I want to create courses

  Scenario: Loading add course page by Add Course button as admin
    Given I'm "admin"
    And I'm on "home" page
    When I select "Add Course" button
    Then "Add Course" page should load

  Scenario: Loading add course page by add a course button as instructor
    Given I'm "instructor1"
    And I'm on "home" page
    When I select "Add Course" button
    Then "Add Course" page should load

  Scenario: Creating a course as instructor
    Given I'm "instructor1"
    And I'm on "create course" page
    And I toggle the "Add a course description:" checkbox
    And I fill in rich text "This is the description for Test Course 2" for "cke_courseDescription"
    And I fill in:
      | element     | content       |
      | course.name | Test Course 2 |
    When I submit form with "Save" button
    Then I should be on the "course" page
    And I should see "Test Course 2" in "h1" on the page
    And I should see "This is the description for Test Course 2" in "div.intro-text" on the page