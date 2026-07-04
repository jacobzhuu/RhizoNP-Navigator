from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_api_base: str = "https://api.deepseek.com"
    llm_max_tokens: int = 4096

    embedding_model: str = "yangjhchs/acge_text_embedding"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    vector_db_path: Path = PROJECT_ROOT / "data" / "faiss_all_acge"

    database_url: str = ""
    postgres_db: str = "postgres"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    top_k_embedding_docs: int = 50
    top_k_rerank_docs: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Legacy constant names retained for existing modules and user scripts.
DEEPSEEK_API = settings.deepseek_api_key
QWEN_API = settings.qwen_api_key
EMBEDDING_BGE_LARGE = "BAAI/bge-large-zh-v1.5"
EMBEDDING_ACGE = settings.embedding_model
RERANK_MODEL_PATH = settings.reranker_model
VECTOR_DB_PATH = str(settings.vector_db_path)
top_k_embedding_docs = settings.top_k_embedding_docs
top_k_rerank_docs = settings.top_k_rerank_docs
