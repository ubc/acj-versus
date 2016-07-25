# sqlalchemy
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.hybrid import hybrid_property

from . import *

from acj.core import db

class LTIUser(DefaultTableMixin, WriteTrackingMixin):
    __tablename__ = 'lti_user'

    # table columns
    lti_consumer_id = db.Column(db.Integer, db.ForeignKey("lti_consumer.id", ondelete="CASCADE"),
        nullable=False)
    user_id = db.Column(db.String(255), nullable=False)
    lis_person_name_given = db.Column(db.String(255), nullable=True)
    lis_person_name_family = db.Column(db.String(255), nullable=True)
    lis_person_name_full = db.Column(db.String(255), nullable=True)
    lis_person_contact_email_primary = db.Column(db.String(255), nullable=True)
    user_oauth_id = db.Column(db.Integer, db.ForeignKey("user_oauth.id", ondelete="CASCADE"),
        nullable=True)

    # relationships
    # TODO: build relationship on UserOAuth with
    # auth_type == AuthType.lti && auth_source_id = self.id

    # hyprid and other functions
    def is_linked_to_user(self):
        return self.user_oauth_id != None

    @classmethod
    def get_by_lti_consumer_id_and_user_id(cls, lti_consumer_id, user_id):
        lti_user = LTIContext.query \
            .filter_by(
                lti_consumer_id=lti_consumer_id,
                user_id=user_id
            ) \
            .one()

        return lti_user

    @classmethod
    def get_by_launch_request(cls, lti_consumer, launch_request):
        lti_user = LTIUser.get_by_lti_consumer_id_and_user_id(
            lti_consumer.id, launch_request['user_id'])

        if lti_user == None:
            lti_user = LTIUser(
                lti_consumer_id=lti_consumer.id,
                user_id=launch_request['user_id']
            )
        lti_user.lis_person_name_given = launch_request['lis_person_name_given']
        lti_user.lis_person_name_family = launch_request['lis_person_name_family']
        lti_user.lis_person_name_full = launch_request['lis_person_name_full']
        lti_user.lis_person_contact_email_primary = launch_request['lis_person_contact_email_primary']

        # create/update if needed
        if lti_user.session.is_modified(lti_user, include_collections=False):
            db.session.add(lti_user)
            db.session.commit()

        return lti_user

    @classmethod
    def __declare_last__(cls):
        super(cls, cls).__declare_last__()

    __table_args__ = (
        # prevent duplicate resource link in consumer
        db.UniqueConstraint('lti_consumer_id', 'user_id', name='_unique_lti_consumer_and_lti_user'),
        DefaultTableMixin.default_table_args
    )