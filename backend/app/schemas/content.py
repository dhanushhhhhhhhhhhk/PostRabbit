"""
content.py — Pydantic schemas for content submissions and responses.

Defines the data shapes used in API requests and responses for the
refactored multi-table architecture. Schemas are grouped by domain entity
(content, job, analysis, user) and kept separate from SQLAlchemy models to
decouple the transport layer from the persistence layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl


# ---------------------------------------------------------------------------
# Ingest schemas (iOS Shortcut → POST /api/ingest)
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    """
    Request body sent by the iOS Shortcut when sharing a video URL.

    Validation:
        - url must be a valid HTTP(S) URL (enforced by Pydantic HttpUrl).
        - user_id must be a valid UUID.
    """
    url: HttpUrl
    user_id: uuid.UUID


class IngestResponse(BaseModel):
    """
    Lightweight acknowledgement returned after ingestion.

    Contains only the content_id and current status so the client
    can poll for results later.
    """
    content_id: uuid.UUID
    status: str


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """Request body for creating a new user."""
    email: str


class UserResponse(BaseModel):
    """Response body for a user record."""
    id: uuid.UUID
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Content schemas
# ---------------------------------------------------------------------------

class ContentSubmit(BaseModel):
    """
    Request body when a user submits a new video URL.

    The caller provides the URL and user_id; the source field
    (youtube | instagram) is determined by the backend.
    """
    url: HttpUrl
    user_id: uuid.UUID


class ContentResponse(BaseModel):
    """
    Response body representing a content item and its current status.

    Does NOT embed the full analysis — use ContentDetailResponse for that.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    url: str
    source: str
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ContentDetailResponse(ContentResponse):
    """
    Extended response that includes the analysis and latest job info.

    Used on the GET /api/content/{id} detail endpoint so the client
    can see transcript, summary, and key points alongside the metadata.
    """
    analysis: Optional[ContentAnalysisResponse] = None
    jobs: Optional[List[JobResponse]] = None


# ---------------------------------------------------------------------------
# Job schemas
# ---------------------------------------------------------------------------

class JobResponse(BaseModel):
    """Response body for a processing job."""
    id: uuid.UUID
    content_id: uuid.UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Content analysis schemas
# ---------------------------------------------------------------------------

class ContentAnalysisResponse(BaseModel):
    """Response body for the AI-generated analysis of a content item."""
    id: uuid.UUID
    content_id: uuid.UUID
    transcript: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Rebuild forward-referenced models so nested types resolve correctly.
# ---------------------------------------------------------------------------

ContentDetailResponse.model_rebuild()
