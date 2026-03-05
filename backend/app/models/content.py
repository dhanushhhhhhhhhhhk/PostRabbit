"""
content.py — SQLAlchemy model for submitted content (videos / reels).

Represents a single video URL shared by a user.  This table owns the
metadata about the content itself (URL, source platform, title, thumbnail)
and its high-level processing status.

The actual AI outputs (transcript, summary, key points) live in the
separate `content_analysis` table so that:
  - Content metadata stays lightweight and fast to query.
  - Analysis results can be regenerated without touching the content row.
  - The schema cleanly separates *input* from *output*.

Columns:
    id         — Primary key (UUID).
    user_id    — Foreign key → users.id (who submitted this).
    url        — Original video URL.
    source     — Platform identifier: "youtube" or "instagram".
    title      — Video title (populated after download/metadata fetch).
    thumbnail  — Thumbnail URL (populated after download/metadata fetch).
    status     — High-level status: pending | processing | completed | failed.
    created_at — Timestamp when the content was submitted.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Index, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Content(Base):
    """A submitted video / reel and its metadata."""

    __tablename__ = "content"

    # Primary key — UUID generated on insert
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to the user who submitted this content
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Original URL shared by the user (Instagram Reel or YouTube link)
    # Indexed for fast duplicate lookups during ingestion
    url = Column(String, nullable=False, index=True)

    # Source platform — "youtube" or "instagram"
    source = Column(String, nullable=False)

    # Video title (may be populated later during the download step)
    title = Column(String, nullable=True)

    # Thumbnail URL (may be populated later during the download step)
    thumbnail = Column(String, nullable=True)

    # High-level processing status: pending | processing | completed | failed
    status = Column(String, nullable=False, default="pending")

    # Timestamp of submission
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Many-to-one: each content item belongs to a user
    user = relationship("User", back_populates="contents")

    # One-to-many: a content item can have multiple processing jobs
    # (e.g. retries), ordered by creation time
    jobs = relationship("Job", back_populates="content", order_by="Job.created_at")

    # One-to-one: the AI analysis result for this content
    analysis = relationship("ContentAnalysis", back_populates="content", uselist=False)
