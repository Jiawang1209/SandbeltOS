from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


# Resolves to the `backend/` directory regardless of uvicorn's CWD — needed
# because chromadb opens its SQLite file relative to `chroma_persist_dir` and
# will fail with SQLITE_CANTOPEN (code 14) when the path is relative and the
# process was launched from a different working directory.
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _resolve_backend_path(value: str) -> str:
    """Anchor relative RAG paths to BACKEND_DIR.

    Both `.env` overrides and the defaults use `backend/rag/...`. If the
    process CWD is already `backend/` (as uvicorn --app-dir does), a plain
    relative path produces `backend/backend/rag/...`. Strip a leading
    `backend/` and resolve against BACKEND_DIR to make the behavior
    independent of where the process was launched from.
    """
    p = Path(value)
    if p.is_absolute():
        return str(p)
    parts = p.parts
    if parts and parts[0] == "backend":
        parts = parts[1:]
    return str(BACKEND_DIR.joinpath(*parts))


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://sandbelt:sandbelt@localhost:5432/sandbelt_db"
    database_url_sync: str = "postgresql://sandbelt:sandbelt@localhost:5432/sandbelt_db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"

    # GEE
    gee_project: str = "ee-yueliu19921209"
    gee_service_account: str = ""
    gee_key_file: str = "secrets/gee-key.json"

    # CDS API
    cds_url: str = "https://cds.climate.copernicus.eu/api"
    cds_key: str = ""

    # LLM (OpenAI-compatible: CSTCloud uni-api, Claude proxy, vLLM, etc.)
    llm_base_url: str = "https://uni-api.cstcloud.cn/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen3:235b"
    llm_max_tokens: int = 2048

    # Legacy / alt-provider keys (kept so old .env files don't break)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- RAG ---

    rag_embedder: str = "BAAI/bge-m3"
    rag_reranker: str = "BAAI/bge-reranker-v2-m3"
    rag_top_k_retrieve: int = 20
    rag_top_k_rerank: int = 5
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100

    chroma_persist_dir: str = str(BACKEND_DIR / "rag" / "chroma_store")
    rag_docs_dir: str = str(BACKEND_DIR / "rag" / "docs")

    @field_validator("chroma_persist_dir", "rag_docs_dir", mode="after")
    @classmethod
    def _anchor_rag_paths(cls, v: str) -> str:
        return _resolve_backend_path(v)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
