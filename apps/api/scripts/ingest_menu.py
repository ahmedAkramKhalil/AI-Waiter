"""
Ingestion script — run once before starting the API.
Re-runnable: deletes and recreates the Qdrant collection each time.

Usage (from the repo root):
    python -m apps.api.scripts.ingest_menu
"""

import json
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# BGE-M3 dense vector dimension
VECTOR_SIZE = 1024


def build_searchable_text(meal: dict) -> str:
    """
    Combine relevant fields into a single Arabic string for embedding.
    name_ar is repeated twice to give it higher weight in retrieval.
    """
    return (
        f"{meal['name_ar']} {meal['name_ar']} "
        f"{meal['description_ar']} "
        f"{' '.join(meal['ingredients'])} "
        f"{' '.join(meal['tags'])} "
        f"{meal['category']}"
    )


def main() -> None:
    # Resolve paths relative to repo root (two levels up from this file)
    repo_root = Path(__file__).resolve().parents[3]
    menu_path = repo_root / "data" / "menu.json"

    # Allow override via config if available
    qdrant_path = "/workspace/qdrant_storage"
    try:
        from apps.api.config import settings  # noqa: PLC0415
        qdrant_path = settings.qdrant_path
        qdrant_host = settings.qdrant_host
        qdrant_port = settings.qdrant_port
        collection = settings.qdrant_collection
        embedding_model = settings.embedding_model
        menu_path = Path(settings.menu_json_path)
        if not menu_path.is_absolute():
            menu_path = repo_root / settings.menu_json_path
    except Exception:
        qdrant_host = "localhost"
        qdrant_port = 6333
        collection = "menu_ar"
        embedding_model = "BAAI/bge-m3"

    print(f"Loading menu from: {menu_path}")
    with open(menu_path, encoding="utf-8") as f:
        meals: list[dict] = json.load(f)
    print(f"  → {len(meals)} meals loaded")

    print(f"Loading embedding model: {embedding_model} (CPU)")
    model = SentenceTransformer(embedding_model, device="cpu")

    if qdrant_path:
        print(f"Using Qdrant embedded mode at: {qdrant_path}")
        client = QdrantClient(path=qdrant_path)
    else:
        print(f"Connecting to Qdrant server at {qdrant_host}:{qdrant_port}")
        client = QdrantClient(host=qdrant_host, port=qdrant_port)

    print(f"Recreating collection '{collection}' (vector size={VECTOR_SIZE})")
    client.recreate_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    print("Embedding meals…")
    texts = [build_searchable_text(m) for m in meals]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

    points = [
        PointStruct(
            id=idx,
            vector=vectors[idx].tolist(),
            payload=meals[idx],
        )
        for idx in range(len(meals))
    ]

    print("Uploading to Qdrant…")
    client.upsert(collection_name=collection, points=points)
    print(f"Done — {len(points)} meals ingested into '{collection}'.")


if __name__ == "__main__":
    main()
