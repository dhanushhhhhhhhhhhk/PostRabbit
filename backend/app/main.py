"""
main.py — FastAPI application entry point.

Initializes the FastAPI app instance, includes all route modules,
and sets up application-level event hooks (e.g. database init on startup).

Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from app.routes import submissions, health

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PostRabbit",
    description="Social-media video summarization API",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

# Health-check / readiness probe
app.include_router(health.router)

# Content submission endpoints
app.include_router(submissions.router)
