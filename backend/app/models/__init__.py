"""
Models package — SQLAlchemy ORM models.

Import all models here so that Base.metadata is aware of every table
when we run migrations or call Base.metadata.create_all().
"""

from app.models.user import User  # noqa: F401
from app.models.content import Content  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.content_analysis import ContentAnalysis  # noqa: F401
