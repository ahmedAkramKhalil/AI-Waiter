from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to this file (apps/api/.env)
_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # LLM backend: "ollama" (local Mac) or "vllm" (RunPod)
    llm_backend: str = "ollama"
    llm_api_base: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model_name: str = "qwen2.5:7b"
    llm_simple_model_name: str = ""
    llm_temperature: float = 0.15
    llm_top_p: float = 0.85
    llm_num_ctx: int = 1536
    llm_max_tokens: int = 80
    llm_num_thread: int = 0
    llm_keep_alive: str = "24h"
    llm_warmup_enabled: bool = True
    llm_connect_timeout_s: float = 10.0
    llm_request_retries: int = 1
    llm_retry_backoff_ms: int = 250

    # Qdrant
    # qdrant_path: use embedded mode (no server needed, good for Docker-in-Docker)
    # leave empty "" to use host/port server mode
    qdrant_path: str = "qdrant_storage"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "menu_ar"

    # Embedding + re-ranking
    embedding_model: str = "BAAI/bge-m3"
    # Cross-encoder reranker — runs on Qdrant's top-N and reorders by
    # query-document interaction scoring. Best single-step quality boost after
    # a strong embedder. Set rag_rerank_enabled=false to fall back to
    # embedder-only ranking.
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rag_rerank_enabled: bool = True
    # How many candidates to pull from Qdrant before re-ranking. Typical
    # rule of thumb: 4-5x final top_k.
    rag_oversample: int = 15

    # Paths
    menu_json_path: str = "data/menu.json"
    images_dir: str = "data/images"

    # Chat
    max_history_messages: int = 4
    chat_history_char_budget: int = 320
    rag_top_k: int = 3
    rag_min_score: float = 0.35
    max_tool_iterations: int = 5


settings = Settings()
