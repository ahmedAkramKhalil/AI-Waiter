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

    # Qdrant
    # qdrant_path: use embedded mode (no server needed, good for Docker-in-Docker)
    # leave empty "" to use host/port server mode
    qdrant_path: str = "qdrant_storage"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "menu_ar"

    # Embedding
    embedding_model: str = "BAAI/bge-m3"

    # Paths
    menu_json_path: str = "data/menu.json"
    images_dir: str = "data/images"

    # Chat
    max_history_messages: int = 4
    rag_top_k: int = 3
    max_tool_iterations: int = 5


settings = Settings()
