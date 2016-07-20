import dateutil.parser
import datetime
import pytz

# sqlalchemy
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.hybrid import hybrid_property

from . import *

from acj.core import db

class Course(DefaultTableMixin, ActiveMixin, WriteTrackingMixin):
    # table columns
    name = db.Column(db.String(255), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    term = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.DateTime(timezone=True), nullable=True)
    end_date = db.Column(db.DateTime(timezone=True), nullable=True)
    # relationships

    # user many-to-many course with association user_course
    user_courses = db.relationship("UserCourse", back_populates="course", lazy="dynamic")
    assignments = db.relationship("Assignment", backref="course", lazy="dynamic")

    # lti
    lti_contexts = db.relationship("LTIContext", backref="acj_user", lazy='dynamic')

    # hyprid and other functions
    @hybrid_property
    def fullname(self):
        return '%s %s %s' % (self.name, self.term, self.year)

    @hybrid_property
    def available(self):
        now = dateutil.parser.parse(datetime.datetime.utcnow().replace(tzinfo=pytz.utc).isoformat())

        # must be after start date if set
        if self.start_date and self.start_date.replace(tzinfo=pytz.utc) > now:
            return False

        # must be before end date if set
        if self.end_date and now >= self.end_date.replace(tzinfo=pytz.utc):
            return False

        return True

    @classmethod
    def __declare_last__(cls):
        super(cls, cls).__declare_last__()