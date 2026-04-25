from __future__ import annotations

import time
from typing import Any

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from apps.api.config import settings

# Module-level singletons — loaded once at startup
_embedder: SentenceTransformer | None = None
_reranker: Any | None = None
_reranker_load_failed = False
_qdrant: QdrantClient | None = None


def get_embedder() -> SentenceTransformer:
    """bge-m3 by default — 1024-dim, strong multilingual incl. Arabic."""
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.embedding_model, device="cpu")
    return _embedder


def get_reranker():
    """
    Cross-encoder reranker (bge-reranker-v2-m3). Lazy-loaded, cached singleton.
    Returns None if disabled in config or if loading fails — the caller falls
    back to embedder ranking in that case, so the system degrades gracefully.
    """
    global _reranker, _reranker_load_failed
    if not settings.rag_rerank_enabled or _reranker_load_failed:
        return None
    if _reranker is None:
        try:
            # CrossEncoder is the sentence-transformers wrapper around
            # transformers AutoModelForSequenceClassification — correct class
            # for bge-reranker-v2-m3.
            from sentence_transformers import CrossEncoder

            _reranker = CrossEncoder(settings.reranker_model, device="cpu")
        except Exception as exc:  # noqa: BLE001
            print(f"[RAG]   reranker load failed ({exc!r}) — falling back to embedder", flush=True)
            _reranker_load_failed = True
            return None
    return _reranker


def get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        if settings.qdrant_path:
            _qdrant = QdrantClient(path=settings.qdrant_path)
        else:
            _qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _qdrant


def _build_rerank_text(payload: dict) -> str:
    """
    Text passed to the cross-encoder for each candidate. Concise — cross-encoders
    are slower per-pair, so we don't want to feed them full menu blobs. Name
    (repeated for emphasis) + category + description + tags covers what matters
    for relevance scoring.
    """
    name = payload.get("name_ar", "")
    tags = payload.get("tags") or []
    tag_str = " ".join(tags) if isinstance(tags, list) else str(tags)
    return (
        f"{name} {name}. "
        f"{payload.get('category', '')}. "
        f"{payload.get('description_ar', '')} "
        f"{tag_str}"
    ).strip()


def search_menu(
    query: str,
    top_k: int | None = None,
    *,
    metrics: dict[str, Any] | None = None,
) -> list[dict]:
    """
    Two-stage retrieval:
      1. Dense retrieval via bge-m3 + Qdrant cosine on an oversample window.
      2. Cross-encoder rerank with bge-reranker-v2-m3 → cut to top_k.
    Floors out anything below settings.rag_min_score on the embedder side so
    off-domain queries return [] and the orchestrator can degrade safely.
    """
    final_k = top_k or settings.rag_top_k
    oversample = max(settings.rag_oversample, final_k)

    # ---- Stage 1: embed + dense search -----------------------------------
    t0 = time.perf_counter()
    vector = get_embedder().encode(query, normalize_embeddings=True).tolist()
    t_embed = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    client = get_qdrant()
    try:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=oversample,
            with_payload=True,
        )
        points = response.points
    except AttributeError:
        points = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=vector,
            limit=oversample,
            with_payload=True,
        )
    t_qdrant = (time.perf_counter() - t1) * 1000

    raw_hits = [{"score": round(p.score, 3), **p.payload} for p in points]
    floor = settings.rag_min_score
    dense_kept = [h for h in raw_hits if h["score"] >= floor]
    top_score = raw_hits[0]["score"] if raw_hits else 0.0

    print(
        f"[TIMING]   ├─ embed.encode        = {t_embed:7.1f} ms  (dim={len(vector)})",
        flush=True,
    )
    print(
        f"[TIMING]   ├─ qdrant.query        = {t_qdrant:7.1f} ms  "
        f"(oversample={oversample}, kept={len(dense_kept)}/{len(raw_hits)}, "
        f"top={top_score:.3f}, floor={floor})",
        flush=True,
    )

    # ---- Stage 2: cross-encoder rerank -----------------------------------
    reranker = get_reranker()
    t_rerank = 0.0
    reranked = dense_kept
    if reranker is not None and len(dense_kept) > 1:
        t2 = time.perf_counter()
        pairs = [(query, _build_rerank_text(h)) for h in dense_kept]
        try:
            rr_scores = reranker.predict(pairs)
            # Attach rerank score and sort. Keep dense score too for telemetry.
            for h, s in zip(dense_kept, rr_scores):
                h["dense_score"] = h.get("score")
                h["rerank_score"] = float(s)
                h["score"] = float(s)
            reranked = sorted(dense_kept, key=lambda h: h["rerank_score"], reverse=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[RAG]   rerank failed ({exc!r}) — keeping dense order", flush=True)
        t_rerank = (time.perf_counter() - t2) * 1000
        print(
            f"[TIMING]   └─ rerank (cross-enc)  = {t_rerank:7.1f} ms  "
            f"(pairs={len(pairs)}, top_rerank={reranked[0].get('rerank_score', 0.0):.3f})",
            flush=True,
        )
    else:
        print(
            "[TIMING]   └─ rerank              =  SKIPPED  "
            f"({'disabled' if reranker is None else 'too few candidates'})",
            flush=True,
        )

    final = reranked[:final_k]

    if metrics is not None:
        metrics["embed_ms"] = round(t_embed, 1)
        metrics["qdrant_ms"] = round(t_qdrant, 1)
        metrics["rerank_ms"] = round(t_rerank, 1)
        metrics["rag_oversample"] = oversample
        metrics["rag_top_k"] = final_k
        metrics["rag_top_score"] = top_score
        metrics["rag_kept"] = len(dense_kept)
        metrics["rag_raw"] = len(raw_hits)
        metrics["rag_reranked"] = reranker is not None

    return final
