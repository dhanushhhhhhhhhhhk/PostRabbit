"""
health.py — Health-check endpoint.

Provides a lightweight route used by load balancers, Kubernetes probes,
or simple uptime monitors to verify the API is running.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Return a simple OK status."""
    return {"status": "ok"}
