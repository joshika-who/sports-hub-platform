import glob
import hashlib
import logging
import math
import os
import re
from typing import Any, Dict, List
import requests

logger = logging.getLogger("sportshub.injury_ai_service")

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(SERVICE_DIR, "..", ".."))
KB_FILE_PATH = os.path.join(SERVICE_DIR, "sports_safety_kb.txt")
CORPUS_DIR = os.path.join(BACKEND_DIR, "app", "services", "injury_ai", "corpus")
CHROMA_PERSIST_DIR = os.environ.get(
    "CHROMA_PERSIST_DIR", os.path.join(BACKEND_DIR, "chroma_data")
)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "20"))
COLLECTION_NAME = "sports_safety_kb_v1"
EMBED_DIM = 128

_chroma_collection = None
_fallback_records: List[Dict[str, Any]] = []


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _compute_embedding(text: str) -> List[float]:
    """
    Deterministic feature-hashing + n-gram embedding vector for ChromaDB.
    Works 100% offline with zero external model downloads on startup.
    """
    vec = [0.0] * EMBED_DIM
    tokens = _tokenize(text)
    if not tokens:
        vec[0] = 1.0
        return vec

    features = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i + 1]}")

    for feat in features:
        digest = hashlib.md5(feat.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "little") % EMBED_DIM
        sign = 1.0 if (digest[2] & 1) == 0 else -1.0
        weight = 2.0 if len(feat) > 5 else 1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """Splits knowledge base text into overlapping ~500-character chunks."""
    clean = text.strip()
    if len(clean) <= chunk_size:
        return [clean] if clean else []

    chunks: List[str] = []
    start = 0
    length = len(clean)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            nl = clean.rfind("\n", start + chunk_size // 2, end)
            period = clean.rfind(". ", start + chunk_size // 2, end)
            break_pt = max(nl, period + 1 if period != -1 else -1)
            if break_pt > start:
                end = break_pt
        piece = clean[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(start + 1, end - overlap)
    return chunks


def _collect_kb_records() -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []

    # 1. Load primary sports_safety_kb.txt
    if os.path.exists(KB_FILE_PATH):
        with open(KB_FILE_PATH, "r", encoding="utf-8") as f:
            kb_text = f.read()
        for idx, piece in enumerate(chunk_text(kb_text, chunk_size=500, overlap=80)):
            records.append(
                {
                    "id": f"sports_safety_kb.txt#chunk-{idx}",
                    "source": "sports_safety_kb.txt",
                    "title": "Sports Safety & RICE First-Aid Guidelines",
                    "content": piece,
                }
            )

    # 2. Load additional specialized markdown corpus files if present
    if os.path.isdir(CORPUS_DIR):
        for md_path in sorted(glob.glob(os.path.join(CORPUS_DIR, "*.md"))):
            fname = os.path.basename(md_path)
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()
            first_line = (
                md_text.splitlines()[0].lstrip("# ").strip()
                if md_text.splitlines()
                else fname
            )
            for idx, piece in enumerate(chunk_text(md_text, chunk_size=500, overlap=80)):
                records.append(
                    {
                        "id": f"{fname}#chunk-{idx}",
                        "source": fname,
                        "title": first_line,
                        "content": f"[{first_line}] {piece}",
                    }
                )

    return records


def index_knowledge_base() -> int:
    """
    Loads `sports_safety_kb.txt` (and corpus files), chunks the text, and indexes
    all chunks into a local persistent ChromaDB collection.
    """
    global _chroma_collection, _fallback_records

    records = _collect_kb_records()
    _fallback_records = records

    try:
        import chromadb  # type: ignore

        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        if collection.count() < len(records) and records:
            collection.upsert(
                ids=[r["id"] for r in records],
                documents=[r["content"] for r in records],
                embeddings=[_compute_embedding(r["content"]) for r in records],
                metadatas=[
                    {"source": r["source"], "title": r["title"]} for r in records
                ],
            )
            logger.info("Indexed %d chunks into ChromaDB collection '%s'.", len(records), COLLECTION_NAME)
        _chroma_collection = collection
        return collection.count()
    except Exception as exc:
        logger.warning("ChromaDB fallback to in-memory index (%s).", exc)
        return len(records)


def retrieve_relevant_context(user_query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Searches ChromaDB for the top_k most relevant safety/recovery chunks."""
    if not _fallback_records and _chroma_collection is None:
        index_knowledge_base()

    q_vec = _compute_embedding(user_query)
    q_tokens = set(_tokenize(user_query))
    scored: List[Dict[str, Any]] = []

    if _chroma_collection is not None:
        try:
            total = max(1, _chroma_collection.count())
            res = _chroma_collection.query(
                query_embeddings=[q_vec],
                n_results=min(top_k * 2, total),
            )
            ids = (res.get("ids") or [[]])[0]
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]

            for cid, doc, meta, dist in zip(ids, docs, metas, dists):
                overlap = len(q_tokens & set(_tokenize(doc)))
                vec_sim = max(0.0, 1.0 - float(dist or 0.0))
                scored.append(
                    {
                        "id": cid,
                        "source": (meta or {}).get("source", "sports_safety_kb.txt"),
                        "title": (meta or {}).get("title", "Sports Safety Guidelines"),
                        "content": doc,
                        "score": vec_sim + 0.25 * overlap,
                    }
                )
            scored.sort(key=lambda item: item["score"], reverse=True)
            return scored[:top_k]
        except Exception as exc:
            logger.warning("ChromaDB query fallback: %s", exc)

    for rec in _fallback_records:
        d_vec = _compute_embedding(rec["content"])
        cosine = sum(a * b for a, b in zip(q_vec, d_vec))
        overlap = len(q_tokens & set(_tokenize(rec["content"])))
        scored.append(
            {
                "id": rec["id"],
                "source": rec["source"],
                "title": rec["title"],
                "content": rec["content"],
                "score": cosine + 0.25 * overlap,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def query_injury_assistant(user_query: str) -> Dict[str, Any]:
    """
    1. Searches ChromaDB for the most relevant safety/recovery context based on `user_query`.
    2. Formulates a safety-first prompt combining the retrieved context and `user_query`.
    3. Sends a POST request to local Ollama (`http://localhost:11434/api/generate`) using `gemma3:1b`.
    4. Returns the generated response dict (with automatic retrieval-only fallback if Ollama is offline).
    """
    chunks = retrieve_relevant_context(user_query, top_k=4)
    sources = [
        {"id": c["id"], "source": c["source"], "title": c["title"]}
        for c in chunks
    ]
    context_block = "\n\n---\n\n".join(
        f"Source ({c['source']} - {c['title']}):\n{c['content']}" for c in chunks
    )

    prompt = (
        "You are the Sports Hub AI Injury Prevention & Recovery Assistant.\n"
        "Use the retrieved sports medicine and first-aid context below to answer the athlete's question.\n"
        "Always prioritize athlete safety, state that this is educational guidance (not a medical diagnosis), "
        "and advise consulting a physician for severe symptoms, suspected fractures, or concussion red flags.\n\n"
        f"Retrieved Context:\n{context_block}\n\n"
        f"Athlete Question: {user_query}\n\n"
        "Assistant Guidance:"
    )

    generated_text = ""
    mode = "retrieval_only"

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            generated_text = (data.get("response") or "").strip()
            if generated_text:
                mode = "ollama_rag"
    except Exception as exc:
        logger.info("Local Ollama (%s) unreachable (%s); using ChromaDB retrieval fallback.", OLLAMA_URL, exc)

    if not generated_text:
        bullets = "\n\n".join(
            f"{i}. **{c['title']}** (`{c['source']}`)\n   {c['content']}"
            for i, c in enumerate(chunks, start=1)
        )
        generated_text = (
            f"### [Retrieval-Only Guidance — Local Ollama ({OLLAMA_MODEL}) Unreachable]\n"
            "> **Medical Safety Disclaimer:** This educational guidance is retrieved directly from the Sports Hub "
            "Safety Knowledge Base (`sports_safety_kb.txt`) and is **not a medical diagnosis**. Consult a licensed "
            "physician for severe pain, inability to bear weight, or concussion symptoms.\n\n"
            f"#### Relevant Safety & Recovery Guidelines:\n{bullets}"
        )

    return {
        "query": user_query,
        "model": OLLAMA_MODEL,
        "mode": mode,
        "response": generated_text,
        "answer": generated_text,
        "sources": sources,
    }


def check_ollama_and_chroma_health() -> Dict[str, Any]:
    count = index_knowledge_base()
    ollama_reachable = False
    models: List[str] = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2.5)
        if r.status_code == 200:
            ollama_reachable = True
            models = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        ollama_reachable = False

    return {
        "status": "ok",
        "ollama_url": OLLAMA_URL,
        "ollama_model": OLLAMA_MODEL,
        "ollama_reachable": ollama_reachable,
        "available_models": models,
        "chromadb_reachable": True,
        "indexed_chunks": count,
        "fallback_mode": "active (retrieval-only)" if not ollama_reachable else "standby",
    }

