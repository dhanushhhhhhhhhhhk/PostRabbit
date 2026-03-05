"""
content_analysis.py — SQLAlchemy model for AI-generated analysis results.

Stores the outputs of the processing pipeline (transcript, summary,
key points) in a dedicated table rather than on the content row.

This separation exists because:
  - Analysis can be large (full transcript text) and we don't want to
    load it every time we list content.
  - Re-running the pipeline can overwrite or version analysis independently.
  - It keeps the content table focused on metadata and status.

Columns:
    id         — Primary key (UUID).
    content_id — Foreign key → content.id (one-to-one).
    transcript — Full speech transcript produced by Whisper.
    summary    — LLM-generated summary paragraph.
    key_points — JSON array of key takeaways from the LLM.
    created_at — When the analysis was stored.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ContentAnalysis(Base):
    """AI-generated analysis for a piece of content."""

    __tablename__ = "content_analysis"

    # Primary key — UUID generated on insert
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to the content this analysis belongs to (one-to-one)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id"), unique=True, nullable=False)

    # Full speech transcript (populated after the Whisper step)
    transcript = Column(Text, nullable=True)

    # LLM-generated summary paragraph
    summary = Column(Text, nullable=True)

    # Key points as a JSON array of strings
    key_points = Column(JSON, nullable=True)

    # When this analysis record was created
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # One-to-one back-reference to the parent content
    content = relationship("Content", back_populates="analysis")
