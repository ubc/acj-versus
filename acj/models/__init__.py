# mixins
from .mixins import ActiveMixin, DefaultTableMixin, WriteTrackingMixin

# enums
from .answer_comment_type import AnswerCommentType
from .course_role import CourseRole
from .pairing_algorithm import PairingAlgorithm
from .scoring_algorithm import ScoringAlgorithm
from .system_role import SystemRole

# models
from .activity_log import ActivityLog
from .answer_comment import AnswerComment
from .answer import Answer
from .assignment_criterion import AssignmentCriterion
from .assignment_comment import AssignmentComment
from .comparison import Comparison
from .comparison_example import ComparisonExample
from .assignment import Assignment
from .course import Course
from .criterion import Criterion
from .file import File
from .score import Score
from .user import User
from .user_course import UserCourse

# LTI models
from .lti import LTIConsumer, LTIContext, LTIResourceLink, \
    LTIUser, LTIUserResourceLink

# oauth enums
from .oauth import AuthType

# oauth models
from .oauth import UserOAuth


from acj.core import db
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
db.metadata.naming_convention = convention