from __future__ import division
import operator
import random

from bouncer.constants import READ, CREATE, MANAGE
from flask import Blueprint, current_app
from flask.ext.login import login_required, current_user
from flask.ext.restful import Resource, marshal
from flask.ext.restful.reqparse import RequestParser
from sqlalchemy import or_, and_

from . import dataformat
from acj.core import db, event
from acj.authorization import require, allow
from acj.models import Answer, Score, Comparison, Course, \
    Assignment, UserCourse, CourseRole, AssignmentCriterion
from .util import new_restful_api

from acj.algorithms import InsufficientObjectsForPairException, \
    UserComparedAllObjectsException, UnknownPairGeneratorException

# First declare a Flask Blueprint for this module
# Then pack the blueprint into a Flask-Restful API
comparison_api = Blueprint('comparison_api', __name__)
api = new_restful_api(comparison_api)

def comparisons_type(value):
    return dict(value)

update_comparison_parser = RequestParser()
update_comparison_parser.add_argument(
    'comparisons', type=comparisons_type, required=True,
    action="append", help="Missing comparisons.")


# events
on_comparison_get = event.signal('COMPARISON_GET')
on_comparison_create = event.signal('COMPARISON_CREATE')
on_comparison_update = event.signal('COMPARISON_UPDATE')

#messages
comparison_deadline_message = 'Assignment comparison deadline has passed.'

# /
class CompareRootAPI(Resource):
    @login_required
    def get(self, course_id, assignment_id):
        """
        Get (or create if needed) a comparison set for assignment.
        """
        course = Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)
        require(READ, assignment)
        restrict_user = not allow(MANAGE, assignment)

        if not assignment.compare_grace:
            return {'error': comparison_deadline_message}, 403

        # check if user has comparisons they have not completed yet
        comparisons = Comparison.query \
            .filter_by(
                assignment_id=assignment_id,
                user_id=current_user.id,
                completed=False
            ) \
            .all()

        if len(comparisons) > 0:
            on_comparison_get.send(
                self,
                event_name=on_comparison_get.name,
                user=current_user,
                course_id=course_id,
                data=marshal(comparisons, dataformat.get_comparison(restrict_user)))
        else:
            # if there aren't incomplete comparisons, assign a new one
            try:
                comparisons = Comparison.create_new_comparison_set(assignment_id, current_user.id)

                on_comparison_create.send(
                    self,
                    event_name=on_comparison_create.name,
                    user=current_user,
                    course_id=course_id,
                    data=marshal(comparisons, dataformat.get_comparison(restrict_user)))
            except InsufficientObjectsForPairException:
                return {"error": "Not enough answers are available for an evaluation."}, 400
            except UserComparedAllObjectsException:
                return {"error": "You have compared all the currently available answers."}, 400
            except UnknownPairGeneratorException:
                return {"error": "Generating scored pairs failed, this really shouldn't happen."}, 500



        return {'objects': marshal(comparisons, dataformat.get_comparison(restrict_user))}

    @login_required
    def post(self, course_id, assignment_id):
        """
        Stores comparison set into the database.
        """
        Course.get_active_or_404(course_id)
        assignment = Assignment.get_active_or_404(assignment_id)

        if not assignment.compare_grace:
            return {'error': comparison_deadline_message}, 403

        require(READ, assignment)
        require(CREATE, Comparison)
        restrict_user = not allow(MANAGE, assignment)

        comparisons = Comparison.query \
            .filter_by(
                assignment_id=assignment_id,
                user_id=current_user.id,
                completed=False
            ) \
            .all()

        params = update_comparison_parser.parse_args()
        completed = True

        # check if there are any comparisons to update
        if len(comparisons) == 0:
            return {"error": "There are no comparisons open for evaluation."}, 400

        is_comparison_example = comparisons[0].comparison_example_id != None

        # check if number of comparisons submitted matches number of comparisons needed
        if len(comparisons) != len(params['comparisons']):
            return {"error": "Not all criteria were evaluated."}, 400

        # check if each comparison has a criterion Id and a winner id
        for comparison_to_update in params['comparisons']:
            # check if saving a draft
            if 'draft' in comparison_to_update and comparison_to_update['draft']:
                completed = False

            # ensure criterion param is present
            if 'criterion_id' not in comparison_to_update:
                return {"error": "Missing criterion_id in evaluation."}, 400

            # set default values for cotnent and winner
            comparison_to_update.setdefault('content', None)
            winner_id = comparison_to_update.setdefault('winner_id', None)

            # if winner isn't set for any comparisons, then the comparison set isn't complete yet
            if winner_id == None:
                completed = False

            # check that we're using criteria that were assigned to the course and that we didn't
            # get duplicate criteria in comparisons
            known_criterion = False
            for comparison in comparisons:
                if comparison_to_update['criterion_id'] == comparison.criterion_id:
                    known_criterion = True

                    # check that the winner id matches one of the answer pairs
                    if winner_id not in [comparison.answer1_id, comparison.answer2_id, None]:
                        return {"error": "Selected answer does not match the available answers in comparison."}, 400

                    break

            if not known_criterion:
                return {"error": "Unknown criterion submitted!"}, 400


        # update comparisons
        for comparison in comparisons:
            comparison.completed = completed

            for comparison_to_update in params['comparisons']:
                if comparison_to_update['criterion_id'] != comparison.criterion_id:
                    continue

                comparison.winner_id = comparison_to_update['winner_id']
                comparison.content = comparison_to_update['content']

            db.session.add(comparison)

        db.session.commit()

        # update answer scores
        if completed and not is_comparison_example:
            current_app.logger.debug("Doing scoring")
            Comparison.update_scores_1vs1(comparisons)
            #Comparison.calculate_scores(assignment_id)

        on_comparison_update.send(
            self,
            event_name=on_comparison_update.name,
            user=current_user,
            course_id=course_id,
            data=marshal(comparisons, dataformat.get_comparison(restrict_user)))

        return {'objects': marshal(comparisons, dataformat.get_comparison(restrict_user))}

api.add_resource(CompareRootAPI, '')
