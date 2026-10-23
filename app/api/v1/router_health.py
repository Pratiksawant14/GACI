"""
Health and Readiness Probes.
Provides liveness and readiness check endpoints for application orchestration and monitoring.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_db
from app.graph.client import neo4j_client
from app.schemas.api import HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness Probe")
def health_check() -> HealthResponse:
    """Returns liveness status of the API service."""
    return HealthResponse(
        status="healthy",
        environment=settings.ENVIRONMENT,
        version="1.0.0"
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness Probe")
def readiness_check(db: Session = Depends(get_db)) -> ReadinessResponse:
    """Checks relational database and Neo4j graph database connectivity."""
    db_ok = False
    neo_ok = False
    details = {}

    # Check relational database
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        details["relational_db"] = "connected"
    except Exception as exc:
        details["relational_db"] = f"error: {str(exc)}"

    # Check Neo4j graph database
    try:
        neo_ok = bool(neo4j_client and neo4j_client.verify_connectivity())
        details["neo4j_graph"] = "connected" if neo_ok else "offline (fallback to relational graph)"
    except Exception as exc:
        details["neo4j_graph"] = f"error: {str(exc)}"

    # Service is considered ready if relational DB is accessible (Neo4j has in-memory fallback)
    overall_status = "ready" if db_ok else "degraded"

    return ReadinessResponse(
        status=overall_status,
        database_connected=db_ok,
        neo4j_connected=neo_ok,
        details=details
    )
