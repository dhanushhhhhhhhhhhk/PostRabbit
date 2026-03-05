"""
submissions.py — API endpoints for content ingestion and retrieval.

Endpoints:
    POST /api/ingest              — Ingest a video URL from the iOS Shortcut.
    GET  /api/submissions/{id}    — Retrieve the status / result for a submission.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.content import (
    IngestRequest,
    IngestResponse,
    ContentDetailResponse,
)
from app.services.content_service import (
    create_content,
    detect_source,
    get_content_by_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["submissions"])


# ---------------------------------------------------------------------------
# POST /api/ingest
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, db: Session = Depends(get_db)):
    """
    Accept a video URL from the iOS Shortcut and enqueue it for processing.

    Steps:
        1. Validate the URL (Pydantic handles well-formedness).
        2. Detect source platform (youtube / instagram) or reject.
        3. De-duplicate: if this user already submitted the same URL,
           return the existing content_id.
        4. Create Content + Job records.
        5. Return content_id and status.
    """
    url_str = str(payload.url)
    logger.info("Ingest request from user %s — URL: %s", payload.user_id, url_str)

    # --- Source detection ------------------------------------------------
    source = detect_source(url_str)
    if source is None:
        logger.warning("Unsupported URL rejected: %s", url_str)
        raise HTTPException(
            status_code=400,
            detail="Unsupported URL. Only YouTube and Instagram links are accepted.",
        )

    # --- Create or retrieve duplicate -----------------------------------
    content, created = create_content(
        db, user_id=payload.user_id, url=url_str, source=source
    )

    if not created:
        logger.info("Returning existing content %s (duplicate URL)", content.id)

    return IngestResponse(content_id=content.id, status=content.status)


# ---------------------------------------------------------------------------
# GET /api/submissions/{content_id}
# ---------------------------------------------------------------------------

@router.get("/submissions/{content_id}", response_model=ContentDetailResponse)
def get_submission(content_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieve the current status, analysis, and job history of a submission.

    Returns 404 if the submission does not exist.
    """
    content = get_content_by_id(db, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Submission not found")
    return content
