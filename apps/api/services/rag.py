from __future__ import annotations

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint

from apps.api.config import settings

# Module-level singletons — loaded once at startup
_embedder: SentenceTransformer | None = None
_qdrant: QdrantClient | None = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        if settings.qdrant_path:
            # Embedded mode — runs in-process, no Docker needed
            _qdrant = QdrantClient(path=settings.qdrant_path)
        else:
            # Server mode — requires a running Qdrant server
            _qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _qdrant


def search_menu(query: str, top_k: int | None = None) -> list[dict]:
    """
    Embed the Arabic query and search Qdrant for the most relevant meals.
    Returns a list of meal payload dicts sorted by relevance (best first).
    """
    k = top_k or settings.rag_top_k
    vector = get_embedder().encode(query, normalize_embeddings=True).tolist()

    results: list[ScoredPoint] = get_qdrant().search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        limit=k,
        with_payload=True,
    )

    return [{"score": round(r.score, 3), **r.payload} for r in results]
