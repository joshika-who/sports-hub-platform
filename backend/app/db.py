import logging
import os
import tempfile
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import settings

logger = logging.getLogger("sportshub.db")


def _get_writable_sqlite_url() -> str:
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = os.path.join(tempfile.gettempdir(), "sportshub.db").replace("\\", "/")
        return f"sqlite:///{tmp_db}"
    return "sqlite:///./sportshub.db"


SQLITE_FALLBACK_URL = _get_writable_sqlite_url()
ACTIVE_DB_BACKEND = "sqlite"


def _build_engine():
    global ACTIVE_DB_BACKEND
    db_url = (settings.DATABASE_URL or "").strip()
    if not db_url:
        db_url = SQLITE_FALLBACK_URL

    # On Vercel/serverless, if someone left "./sportshub.db" in env, redirect to writable /tmp
    if (os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")) and db_url == "sqlite:///./sportshub.db":
        db_url = SQLITE_FALLBACK_URL

    if db_url.startswith("sqlite"):
        ACTIVE_DB_BACKEND = "sqlite"
        try:
            eng = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            return eng
        except Exception:
            return create_engine(
                SQLITE_FALLBACK_URL,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )

    # Attempt PostgreSQL (or custom DB URL) connection with automatic fallback to SQLite
    try:
        connect_args = {"connect_timeout": 3} if "postgresql" in db_url else {}
        eng = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        ACTIVE_DB_BACKEND = "postgresql"
        logger.info("Connected to primary database: %s", db_url.split("@")[-1])
        return eng
    except Exception as exc:
        logger.warning(
            "Primary DATABASE_URL unreachable (%s). Automatically falling back to SQLite (%s).",
            exc,
            SQLITE_FALLBACK_URL,
        )
        ACTIVE_DB_BACKEND = "sqlite"
        return create_engine(
            SQLITE_FALLBACK_URL,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
