from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.config import settings
from apps.api.routers import cart, chat, menu, order, session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up: load menu + embedding model + verify Qdrant connection
    from apps.api.services.menu_loader import load_menu  # noqa: PLC0415
    from apps.api.services.rag import get_embedder, get_qdrant  # noqa: PLC0415

    print("AI Waiter API starting up…")
    load_menu()
    print(f"  ✓ Menu loaded ({len(load_menu().meals)} meals)")
    embedder = get_embedder()
    # Warm encode — first call is slow (CUDA graph / tokenizer init)
    embedder.encode("تجربة", normalize_embeddings=True)
    print(f"  ✓ Embedding model ready ({settings.embedding_model})")
    get_qdrant()
    print(f"  ✓ Qdrant connected ({settings.qdrant_host}:{settings.qdrant_port})")
    print("  Ready to serve! 🍽️")
    yield
    print("AI Waiter API shutting down.")


app = FastAPI(
    title="AI Waiter API",
    description="نادل ذكي عربي — Arabic AI Restaurant Waiter",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for PoC (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve meal images as static files
images_path = Path(settings.images_dir)
if images_path.exists():
    app.mount("/images", StaticFiles(directory=str(images_path)), name="images")

# Register routers
app.include_router(session.router)
app.include_router(chat.router)
app.include_router(menu.router)
app.include_router(cart.router)
app.include_router(order.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ai-waiter-api"}
