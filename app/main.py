"""
FastAPI Application Entrypoint and Factory.
Configures CORS, standardized error handling, and API routers.
"""

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logging import logger
from app.db.session import engine
from app.models.base import Base
from app.api.v1.router_health import router as health_router
from app.api.v1.router_ingest import router as ingest_router
from app.api.v1.router_analysis import router as analysis_router
from app.api.v1.router_graph import router as graph_router
from app.api.v1.router_agent import router as agent_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-initializes canonical tables if not already created."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified and initialized.")
    except Exception as exc:
        logger.warning(f"Database auto-init notice: {exc}")
    yield


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application instance."""
    app = FastAPI(
        title="Graph-Based Agentic Cash-Flow Intelligence System",
        description="Decision-support intelligence detecting wholesale MSME cash blockages, contagion paths, and grounded explanations.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Standardized Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "details": None
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": exc.errors()
                }
            }
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "details": str(exc) if settings.ENVIRONMENT == "development" else None
                }
            }
        )

    # Register Routers
    # Liveness and readiness at both root and under /api/v1
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(analysis_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")

    return app


app = create_app()
