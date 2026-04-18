from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # vLLM — localhost when everything runs on the same pod
    runpod_api_base: str = "http://localhost:8001/v1"
    runpod_api_key: str = "local"
    llm_model_name: str = "tiiuae/Falcon-H1-7B-Instruct"

    # Qdrant
    # qdrant_path: use embedded mode (no server needed, good for Docker-in-Docker)
    # leave empty "" to use host/port server mode
    qdrant_path: str = "/workspace/qdrant_storage"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "menu_ar"

    # Embedding
    embedding_model: str = "BAAI/bge-m3"

    # Paths
    menu_json_path: str = "data/menu.json"
    images_dir: str = "data/images"

    # Chat
    max_history_messages: int = 6
    rag_top_k: int = 5
    max_tool_iterations: int = 5


settings = Settings()
