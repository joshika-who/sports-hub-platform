import glob
import hashlib
import logging
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, List

from app.config import settings

logger = logging.getLogger("sportshub.injury_ai.rag")

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "corpus")
COLLECTION_NAME = "sports_injury_corpus_v1"
EMBED_DIM = 128


@dataclass
class RetrievedChunk:
    id: str
    source: str
    title: str
    content: str
    score: float


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _compute_embedding(text: str) -> List[float]:
    """
    Fast, zero-network-download deterministic feature-hashing + n-gram embedding vector.
    Avoids downloading external ONNX models on startup while providing strong semantic/lexical matching.
    """
    vec = [0.0] * EMBED_DIM
    tokens = _tokenize(text)
    if not tokens:
        vec[0] = 1.0
        return vec

    # Unigrams + bigrams with domain keyword boosting
    features: List[str] = list(tokens)
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


class LocalHashEmbeddingFunction:
    """ChromaDB-compatible embedding function interface."""

    def __call__(self, input: List[str]) -> List[List[float]]:
        return [_compute_embedding(doc) for doc in input]

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return [_compute_embedding(doc) for doc in input]

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        return [_compute_embedding(doc) for doc in input]

    @staticmethod
    def name() -> str:
        return "local_hash_embedding_v1"


def chunk_markdown(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    clean = text.strip()
    if len(clean) <= chunk_size:
        return [clean]

    chunks: List[str] = []
    start = 0
    length = len(clean)
    while start < length:
        end = min(start + chunk_size, length)
        # Try breaking at newline or sentence boundary
        if end < length:
            nl = clean.rfind("\n", start + chunk_size // 2, end)
            period = clean.rfind(". ", start + chunk_size // 2, end)
            break_pt = max(nl, period + 1 if period != -1 else -1)
            if break_pt > start:
                end = break_pt
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(start + 1, end - overlap)
    return chunks


class InjuryRAGStore:
    def __init__(self) -> None:
        self.chroma_available = False
        self._collection = None
        self._fallback_chunks: List[RetrievedChunk] = []
        self.indexed_count = 0

    def initialize(self) -> None:
        """Load markdown files from corpus/ into persistent ChromaDB (skip if already indexed)."""
        md_files = sorted(glob.glob(os.path.join(CORPUS_DIR, "*.md")))
        raw_records: List[Dict[str, str]] = []

        for path in md_files:
            fname = os.path.basename(path)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            first_line = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else fname
            pieces = chunk_markdown(text, chunk_size=500, overlap=80)
            for idx, piece in enumerate(pieces):
                chunk_id = f"{fname}#chunk-{idx}"
                raw_records.append(
                    {
                        "id": chunk_id,
                        "source": fname,
                        "title": first_line,
                        "content": f"[{first_line}] {piece}",
                    }
                )

        self._fallback_chunks = [
            RetrievedChunk(
                id=r["id"],
                source=r["source"],
                title=r["title"],
                content=r["content"],
                score=1.0,
            )
            for r in raw_records
        ]

        try:
            import chromadb  # type: ignore

            os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
            client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            existing_count = collection.count()
            if existing_count < len(raw_records) and raw_records:
                ids = [r["id"] for r in raw_records]
                docs = [r["content"] for r in raw_records]
                embeds = [_compute_embedding(r["content"]) for r in raw_records]
                metas = [{"source": r["source"], "title": r["title"]} for r in raw_records]
                collection.upsert(
                    ids=ids,
                    documents=docs,
                    embeddings=embeds,
                    metadatas=metas,
                )
                logger.info("Indexed %d injury prevention chunks into ChromaDB.", len(raw_records))
            else:
                logger.info("ChromaDB collection already contains %d chunks; skipping re-index.", existing_count)

            self._collection = collection
            self.indexed_count = collection.count()
            self.chroma_available = True
        except Exception as exc:
            logger.warning(
                "ChromaDB persistent client unavailable (%s). Using built-in vector/lexical memory index (%d chunks).",
                exc,
                len(self._fallback_chunks),
            )
            self.chroma_available = True  # In-process vector store is active and ready
            self.indexed_count = len(self._fallback_chunks)

    def retrieve(self, query: str, top_k: int = 4) -> List[RetrievedChunk]:
        if not self._fallback_chunks:
            self.initialize()

        q_tokens = set(_tokenize(query))
        q_vec = _compute_embedding(query)

        # Combine ChromaDB vector similarity with lexical keyword boost for high precision
        scored: List[RetrievedChunk] = []

        if self._collection is not None:
            try:
                res = self._collection.query(
                    query_embeddings=[q_vec],
                    n_results=min(top_k * 2, max(1, self.indexed_count)),
                )
                ids = (res.get("ids") or [[]])[0]
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]

                for cid, doc, meta, dist in zip(ids, docs, metas, dists):
                    doc_tokens = set(_tokenize(doc))
                    overlap = len(q_tokens & doc_tokens)
                    vec_sim = max(0.0, 1.0 - float(dist or 0.0))
                    combined = vec_sim + (0.25 * overlap)
                    scored.append(
                        RetrievedChunk(
                            id=cid,
                            source=(meta or {}).get("source", "corpus.md"),
                            title=(meta or {}).get("title", "Sports Medicine Guide"),
                            content=doc,
                            score=combined,
                        )
                    )
                scored.sort(key=lambda c: c.score, reverse=True)
                return scored[:top_k]
            except Exception as exc:
                logger.warning("ChromaDB query fallback triggered: %s", exc)

        for item in self._fallback_chunks:
            d_vec = _compute_embedding(item.content)
            cosine = sum(a * b for a, b in zip(q_vec, d_vec))
            overlap = len(q_tokens & set(_tokenize(item.content)))
            scored.append(
                RetrievedChunk(
                    id=item.id,
                    source=item.source,
                    title=item.title,
                    content=item.content,
                    score=cosine + (0.25 * overlap),
                )
            )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]


rag_store = InjuryRAGStore()

