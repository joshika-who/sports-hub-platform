import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.cache import cache
from app.config import settings
from app.db import ACTIVE_DB_BACKEND, Base, SessionLocal, engine
from app.middleware import RequestLoggingAndRateLimitMiddleware
from app.seed import seed_database
from app.services.auth_vault.router import auth_router, vault_router
from app.services.bookings.router import router as bookings_router
from app.services.events.router import router as events_router
from app.services.injury_ai.rag import rag_store
from app.services.injury_ai.router import router as injury_router
from app.services.live.router import router as live_router
from app.services.notifications.dispatcher import match_reminder_background_task
from app.services.notifications.router import router as notifications_router
from app.services.payments.router import router as payments_router
from app.services.scheduler.router import router as scheduler_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("sportshub.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create database tables automatically
    Base.metadata.create_all(bind=engine)
    # 2. Seed initial demo data idempotently
    with SessionLocal() as db:
        seed_database(db)
    # 3. Initialize ChromaDB / Injury RAG corpus
    rag_store.initialize()
    # 4. Start background task for 1-hour match reminders
    reminder_task = asyncio.create_task(match_reminder_background_task())
    logger.info(
        "Sports Hub Platform started (DB=%s, Cache=%s, PaymentMode=%s, NotifyMode=%s)",
        ACTIVE_DB_BACKEND,
        cache.backend_name,
        settings.PAYMENT_MODE,
        settings.NOTIFY_MODE,
    )
    yield
    reminder_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await reminder_task


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description=(
            "Sports Hub Platform MVP — Event Discovery, Document Vault, Eligibility Engine, "
            "Court Bookings, Multi-Gateway Payments, Push Notifications, RAG Injury AI, "
            "OR-Tools CP-SAT Tournament Scheduler, and Live WebSocket Scoreboard."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingAndRateLimitMiddleware, max_requests_per_minute=600)

    # Mount static uploads directory for viewing uploaded document references
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    # Mount all service routers
    app.include_router(auth_router)
    app.include_router(vault_router)
    app.include_router(events_router)
    app.include_router(bookings_router)
    app.include_router(payments_router)
    app.include_router(notifications_router)
    app.include_router(injury_router)
    app.include_router(scheduler_router)
    app.include_router(live_router)

    @app.get("/health", tags=["System"])
    @app.get("/api/v1/health", tags=["System"])
    def health_check():
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "database_backend": ACTIVE_DB_BACKEND,
            "cache_backend": cache.backend_name,
            "payment_mode": settings.PAYMENT_MODE,
            "notify_mode": settings.NOTIFY_MODE,
            "rag_chunks_indexed": rag_store.indexed_count,
        }

    return app


app = create_app()

