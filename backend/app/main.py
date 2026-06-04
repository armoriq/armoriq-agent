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
from app.api.routes import iap, dashboard, api_keys, agents, policies, product_auth
from app.models import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    print(f"Starting {settings.app_name}...")

    # Initialize database (create tables if needed)
    if settings.is_development:
        await init_db()

    yield

    # Shutdown
    print(f"Shutting down {settings.app_name}...")
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

    # CORS — allow all origins (required for browser access from localhost:5174 and plugin)
    # allow_credentials must be False when allow_origins=["*"] (CORS spec requirement)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(status="ok", version="0.1.0")

    # Existing chatbot API (namespaced under /api/v1)
    app.include_router(api_router, prefix=APIRoutes.PREFIX)

    # Product API — bare paths consumed by tools-frontend and armorClaude plugin
    # These intentionally have NO /api/v1 prefix so the frontend hits them directly.
    app.include_router(product_auth.router)   # /auth/*
    app.include_router(iap.router)            # /iap/*
    app.include_router(dashboard.router)      # /dashboard/*
    app.include_router(api_keys.router)       # /api-keys/*
    app.include_router(agents.router)         # /agent/*
    app.include_router(policies.router)       # /policies/*

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
