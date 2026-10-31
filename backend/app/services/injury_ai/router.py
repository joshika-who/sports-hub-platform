import json
import logging
from typing import AsyncGenerator, List
import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import settings
from app.schemas import InjuryQueryRequest
from app.services.injury_ai.rag import RetrievedChunk, rag_store

logger = logging.getLogger("sportshub.injury_ai")

router = APIRouter(prefix="/api/v1/injury", tags=["Injury AI Assistant"])

SYSTEM_PROMPT = (
    "You are the Sports Hub Injury-Prevention & Recovery AI Assistant. "
    "Prioritize athlete safety above all else. Provide evidence-based sports physiotherapy "
    "guidance grounded strictly in the retrieved clinical reference chunks. "
    "IMPORTANT: State clearly that your guidance is educational and NOT a formal medical diagnosis. "
    "For severe pain, suspected fractures, joint locking, head trauma/concussion symptoms, or heat stroke, "
    "always advise seeing a licensed physician or emergency medical professional immediately."
)


def _build_retrieval_fallback_text(
    payload: InjuryQueryRequest,
    chunks: List[RetrievedChunk],
) -> str:
    sport_ctx = f" for **{payload.sport}**" if payload.sport else ""
    lines = [
        f"### [Retrieval-Only Guidance — Local Ollama ({settings.OLLAMA_MODEL}) Unreachable]\n",
        f"> **Medical Safety Disclaimer:** This educational summary{sport_ctx} is generated directly from our verified sports-medicine knowledge base and is **not a medical diagnosis**. For severe symptoms, inability to bear weight, joint instability, or head trauma, please consult a licensed sports physician immediately.\n",
        "\n#### Key Evidence-Based Recommendations:\n",
    ]
    for idx, ch in enumerate(chunks, start=1):
        cleaned = ch.content
        if cleaned.startswith("[") and "]" in cleaned:
            cleaned = cleaned.split("]", 1)[1].strip()
        lines.append(f"{idx}. **{ch.title}** (`{ch.source}`)\n   {cleaned}\n\n")

    lines.append(
        "**When to See a Doctor:** If pain exceeds 4/10, swelling worsens rapidly, or you experience numbness, dizziness, or red-flag symptoms, stop athletic activity and seek clinical evaluation."
    )
    return "".join(lines)


async def _stream_injury_response(
    payload: InjuryQueryRequest,
    chunks: List[RetrievedChunk],
) -> AsyncGenerator[str, None]:
    sources = [
        {"id": c.id, "source": c.source, "title": c.title}
        for c in chunks
    ]
    context_text = "\n\n---\n\n".join(
        f"Source ({c.source} - {c.title}):\n{c.content}" for c in chunks
    )
    user_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Retrieved Sports Medicine Context:\n{context_text}\n\n"
        f"Athlete Sport: {payload.sport or 'General Athletics'}\n"
        f"Athlete History: {payload.history or 'None provided'}\n"
        f"Athlete Question: {payload.question}\n\n"
        "Provide a clear, structured, safety-first answer:"
    )

    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=float(settings.OLLAMA_TIMEOUT_SECONDS)) as client:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_URL.rstrip('/')}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": user_prompt,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code == 200:
                    ollama_ok = True
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield json.dumps({"token": token}) + "\n"
                        if data.get("done"):
                            break
    except Exception as exc:
        logger.info("Ollama unreachable (%s); serving retrieval-only RAG answer.", exc)

    if not ollama_ok:
        fallback_text = _build_retrieval_fallback_text(payload, chunks)
        # Stream in readable chunks so the frontend token streamer renders smoothly
        words = fallback_text.split(" ")
        step = 6
        for i in range(0, len(words), step):
            piece = " ".join(words[i : i + step])
            if i + step < len(words):
                piece += " "
            yield json.dumps({"token": piece}) + "\n"

    yield json.dumps(
        {
            "done": True,
            "mode": "ollama_rag" if ollama_ok else "retrieval_only",
            "sources": sources,
        }
    ) + "\n"


@router.post("/query")
async def query_injury_assistant(payload: InjuryQueryRequest):
    query_str = f"{payload.sport or ''} {payload.question} {payload.history or ''}".strip()
    top_chunks = rag_store.retrieve(query_str, top_k=4)
    return StreamingResponse(
        _stream_injury_response(payload, top_chunks),
        media_type="application/x-ndjson",
    )


@router.get("/health")
async def injury_health():
    ollama_reachable = False
    available_models: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(f"{settings.OLLAMA_URL.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                ollama_reachable = True
                data = resp.json()
                available_models = [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        ollama_reachable = False

    return {
        "status": "ok",
        "ollama_url": settings.OLLAMA_URL,
        "ollama_model": settings.OLLAMA_MODEL,
        "ollama_reachable": ollama_reachable,
        "available_models": available_models,
        "chromadb_reachable": rag_store.chroma_available,
        "indexed_chunks": rag_store.indexed_count,
        "fallback_mode": "active (retrieval-only)" if not ollama_reachable else "standby",
    }

