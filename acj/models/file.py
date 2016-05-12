# sqlalchemy
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import synonym, load_only, column_property, backref, contains_eager, joinedload, Load
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.hybrid import hybrid_property

from . import *

from acj.core import db

class File(DefaultTableMixin, ActiveMixin, WriteTrackingMixin):
    # table columns
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"),
        nullable=False)
    name = db.Column(db.String(255), nullable=False)
    alias = db.Column(db.String(255), nullable=False)
    
    # relationships
    # user via User Model
    
    assignments = db.relationship("Assignment", backref="file", lazy='dynamic')
    answers = db.relationship("Answer", backref="file", lazy='dynamic')