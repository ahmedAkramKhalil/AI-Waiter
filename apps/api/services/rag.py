from __future__ import annotations

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from apps.api.config import settings

# Module-level singletons — loaded once at startup
_embedder: SentenceTransformer | None = None
_qdrant: QdrantClient | None = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        # Force CPU — GPU is reserved for the LLM (vLLM)
        _embedder = SentenceTransformer(settings.embedding_model, device="cpu")
    return _embedder


def get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        if settings.qdrant_path:
            _qdrant = QdrantClient(path=settings.qdrant_path)
        else:
            _qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _qdrant


def search_menu(query: str, top_k: int | None = None) -> list[dict]:
    """
    Embed the Arabic query and search Qdrant for the most relevant meals.
    Compatible with both old (.search) and new (.query_points) qdrant-client APIs.
    """
    k = top_k or settings.rag_top_k
    vector = get_embedder().encode(query, normalize_embeddings=True).tolist()
    client = get_qdrant()

    # Try new API first (qdrant-client >= 1.7.4), fall back to old API
    try:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=k,
            with_payload=True,
        )
        points = response.points
    except AttributeError:
        points = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=vector,
            limit=k,
            with_payload=True,
        )

    return [{"score": round(p.score, 3), **p.payload} for p in points]
