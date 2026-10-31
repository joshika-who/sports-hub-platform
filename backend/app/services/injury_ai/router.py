import json
import logging
from fastapi import APIRouter, HTTPException, Response, status

from app.schemas import InjuryQueryRequest
from services.injury_ai_service.rag_engine import (
    check_ollama_and_chroma_health,
    query_injury_assistant,
)

logger = logging.getLogger("sportshub.injury_ai")

router = APIRouter(prefix="/api/v1/injury", tags=["Injury AI Assistant"])


@router.post("/query")
async def query_injury_endpoint(payload: InjuryQueryRequest):
    """
    Accepts a JSON body with the athlete's question (`question`, `query`, or `user_query`),
    retrieves relevant ChromaDB safety/recovery chunks, queries local Ollama (`gemma3:1b`),
    and returns the AI assistant's guidance.
    """
    user_q = payload.resolved_query()
    if not user_q or len(user_q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide a non-empty 'question' or 'query' in the request body.",
        )

    result = query_injury_assistant(user_q)
    response_body = {
        "question": payload.question or payload.query or payload.user_query or user_q,
        "query": user_q,
        "model": result["model"],
        "mode": result["mode"],
        "response": result["response"],
        "answer": result["answer"],
        "token": result["response"],
        "done": True,
        "sources": result["sources"],
    }
    # Returning single-line JSON + newline satisfies both standard `resp.json()` callers
    # and line-by-line NDJSON streaming readers (`aiter_lines()`).
    return Response(
        content=json.dumps(response_body) + "\n",
        media_type="application/json",
    )


@router.get("/health")
async def injury_health():
    return check_ollama_and_chroma_health()
