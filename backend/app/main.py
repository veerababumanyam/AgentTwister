"""
AgentTwister Backend - FastAPI Application

Main application entry point for the AgentTwister payload library API.
Provides endpoints for managing security testing payload templates.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.api.routes import payloads_router, recruitment_router, chat_router, documents_router, streaming_router
from app.database import init_db, close_db, get_database_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the application.
    """
    # Startup
    logger.info("Starting AgentTwister Payload Library API...")
    try:
        # Initialize SQLite database
        await init_db()
        logger.info(f"Database initialized at {get_database_path()}")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.warning("API will start but database operations may fail")

    yield

    # Shutdown
    logger.info("Shutting down AgentTwister Payload Library API...")
    try:
        await close_db()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")


# Create FastAPI application
app = FastAPI(
    title="AgentTwister Payload Library API",
    description="""
    API for managing security testing payload templates.

    **Authorization Required**: All endpoints require proper authentication and
    scope attestation for authorized security research only.

    **Usage**: All payload usage is logged for audit trail purposes.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns the current status of the API and its dependencies.
    """
    db_status = "connected"
    try:
        db_path = get_database_path()
        if not db_path.exists():
            db_status = "not_initialized"
        else:
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": db_status,
    }


# API info endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "AgentTwister Payload Library API",
        "version": "1.0.0",
        "description": "Security testing payload template management for authorized red-teaming",
        "documentation": "/docs",
        "endpoints": {
            "payloads": "/api/v1/payloads/",
            "health": "/health",
        },
        "compliance": {
            "frameworks": ["OWASP LLM Top-10", "OWASP ASI", "MITRE ATLAS", "NIST AI RMF"],
            "authorization_required": "All usage requires explicit scope attestation",
        },
    }


# Include routers
app.include_router(payloads_router)
app.include_router(recruitment_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(streaming_router)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc) if logger.isEnabledFor(logging.DEBUG) else None,
        },
    )


def main():
    """
    Run the application directly.

    Usage: python -m app.main
    """
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
