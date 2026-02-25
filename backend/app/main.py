"""
ArmorIQ Agent Backend - FastAPI Application
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, APIRoutes
from app.db import init_db, close_db
from app.api.routes import api_router
from app.models import HealthResponse
from app.services.mcp_manager import get_mcp_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    print(f"Starting {settings.app_name}...")
    mcp_manager = get_mcp_manager()

    # Initialize database (create tables if needed)
    if settings.is_development:
        await init_db()

    await mcp_manager.start()

    try:
        yield
    finally:
        # Shutdown
        print(f"Shutting down {settings.app_name}...")
        await mcp_manager.stop()
        await close_db()


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        title=settings.app_name,
        description="Multi-LLM Chatbot Agent with MCP Integration and ArmorIQ SDK",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.app_url,
            "http://localhost:3000",  # Next.js dev
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(status="ok", version="0.1.0")

    # Include API routes
    app.include_router(api_router, prefix=APIRoutes.PREFIX)

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
