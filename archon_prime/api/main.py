"""
ARCHON PRIME API - Main Application Entry Point

FastAPI backend for the commercial multi-tenant trading platform.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from archon_prime.api.config import settings
from archon_prime.api.db.session import init_db, close_db
from archon_prime.api.services.mt5_pool import init_mt5_pool, close_mt5_pool
from archon_prime.api.services.background_tasks import init_background_workers, close_background_workers
from archon_prime.api.websocket.manager import init_websocket_manager, close_websocket_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    await init_mt5_pool()
    await init_websocket_manager()
    await init_background_workers()
    yield
    # Shutdown
    await close_background_workers()
    await close_websocket_manager()
    await close_mt5_pool()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="ARCHON PRIME - Institutional-grade AI Trading Platform API",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    from archon_prime.api.auth.routes import router as auth_router
    from archon_prime.api.users.routes import router as users_router
    from archon_prime.api.profiles.routes import router as profiles_router
    from archon_prime.api.trading.routes import router as trading_router
    from archon_prime.api.websocket.routes import router as websocket_router
    from archon_prime.api.admin.routes import router as admin_router
    from archon_prime.api.signals.routes import router as signals_router

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(profiles_router, prefix="/api/v1/profiles", tags=["MT5 Profiles"])
    app.include_router(trading_router, prefix="/api/v1/trading", tags=["Trading"])
    app.include_router(signals_router, prefix="/api/v1/signals", tags=["Signal Gate"])
    app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])

    # Health check endpoint
    @app.get("/api/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "service": settings.APP_NAME,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "archon_prime.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
