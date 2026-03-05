"""
user.py — SQLAlchemy model for application users.

Represents a registered user who submits content for summarization.
Separated into its own table so we can:
  - Track who submitted each piece of content.
  - Support per-user rate limits, preferences, or billing in the future.
  - Associate multiple content items with a single identity.

Columns:
    id         — Primary key (UUID).
    email      — User's email address (unique).
    created_at — Timestamp when the user was first created.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """A registered user of the platform."""

    __tablename__ = "users"

    # Primary key — UUID generated on insert
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User's email — unique constraint prevents duplicate accounts
    email = Column(String, unique=True, nullable=False)

    # Timestamp of account creation
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # One user can submit many content items
    contents = relationship("Content", back_populates="user")
