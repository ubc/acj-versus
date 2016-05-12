# sqlalchemy
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import synonym, load_only, column_property, backref, contains_eager, joinedload, Load
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.hybrid import hybrid_property

from . import *

from acj.core import db

class Criteria(DefaultTableMixin, ActiveMixin, WriteTrackingMixin):
    # table columns
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"),
        nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    public = db.Column(db.Boolean(name='public'), default=False, nullable=False)
    default = db.Column(db.Boolean(name='default'), default=True, nullable=False)
    
    # relationships
    # user via User Model
    
    # assignment many-to-many criteria with association assignment_criteria
    assignment_criteria = db.relationship("AssignmentCriteria", 
        back_populates="criteria", lazy='dynamic')
    
    comparisons = db.relationship("Comparison", backref="criteria", lazy='dynamic')
    scores = db.relationship("Score", backref="criteria", lazy='dynamic')
    
    # hyprid and other functions
    compare_count = column_property(
        select([func.count(AssignmentCriteria.id)]).
        where(AssignmentCriteria.criteria_id == id)
    )

    @hybrid_property
    def compared(self):
        return self.compare_count > 0