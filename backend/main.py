"""
Main FastAPI entrypoint for the Sports Hub Platform backend (`backend/main.py`).
Integrates all platform routers including the Local AI Injury Prevention Assistant
(`POST /api/v1/injury/query` backed by `backend/services/injury_ai_service/rag_engine.py`).
"""
from app.main import app, create_app
from services.injury_ai_service.rag_engine import (
    index_knowledge_base,
    query_injury_assistant,
)

__all__ = [
    "app",
    "create_app",
    "index_knowledge_base",
    "query_injury_assistant",
]
