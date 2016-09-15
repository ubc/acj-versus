# sqlalchemy
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import column_property
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.hybrid import hybrid_property

from . import *
from importlib import import_module

from acj.core import db

class Answer(DefaultTableMixin, UUIDMixin, ActiveMixin, WriteTrackingMixin):
    # table columns
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id', ondelete="CASCADE"),
        nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"),
        nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id', ondelete="SET NULL"),
        nullable=True)
    content = db.Column(db.Text)
    round = db.Column(db.Integer, default=0, nullable=False)
    practice = db.Column(db.Boolean(name='practice'), default=False, nullable=False, index=True)
    flagged = db.Column(db.Boolean(name='flagged'), default=False, nullable=False)
    flagger_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="SET NULL"),
        nullable=True)
    draft = db.Column(db.Boolean(name='draft'), default=False, nullable=False)

    # relationships
    # assignment via Assignment Model
    # user via User Model
    # file via File Model

    comments = db.relationship("AnswerComment", backref="answer")
    scores = db.relationship("Score", backref="answer")

    # hyprid and other functions
    course_id = association_proxy('assignment', 'course_id', creator=lambda course_id:
        import_module('acj.models.assignment').Assignment(course_id=course_id))
    course_uuid = association_proxy('assignment', 'course_uuid')

    assignment_uuid = association_proxy('assignment', 'uuid')

    user_avatar = association_proxy('user', 'avatar')
    user_uuid = association_proxy('user', 'uuid')
    user_displayname = association_proxy('user', 'displayname')
    user_fullname = association_proxy('user', 'fullname')
    user_system_role = association_proxy('user', 'system_role')

    @hybrid_property
    def private_comment_count(self):
        return self.comment_count - self.public_comment_count

    @classmethod
    def __declare_last__(cls):
        super(cls, cls).__declare_last__()

        cls.comment_count = column_property(
            select([func.count(AnswerComment.id)]).
            where(and_(
                AnswerComment.answer_id == cls.id,
                AnswerComment.active == True,
                AnswerComment.draft == False
            )),
            deferred=True,
            group='counts'
        )

        cls.public_comment_count = column_property(
            select([func.count(AnswerComment.id)]).
            where(and_(
                AnswerComment.answer_id == cls.id,
                AnswerComment.active == True,
                AnswerComment.draft == False,
                AnswerComment.comment_type == AnswerCommentType.public
            )),
            deferred=True,
            group='counts'
        )

        cls.self_evaluation_count = column_property(
            select([func.count(AnswerComment.id)]).
            where(and_(
                AnswerComment.comment_type == AnswerCommentType.self_evaluation,
                AnswerComment.active == True,
                AnswerComment.draft == False,
                AnswerComment.answer_id == cls.id
            )),
            deferred=True,
            group='counts'
        )






