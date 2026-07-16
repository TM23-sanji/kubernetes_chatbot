from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_fallback_api_key: str = ""

    qdrant_api_key: str = ""
    qdrant_cluster_endpoint: str = ""

    gemini_api_key: str = ""

    openai_api_key: str = ""

    portkey_api_key: str = ""
    portkey_primary_slug: str = "marathon-api"
    portkey_fallback_slug: str = "anthropic-fallback"
    portkey_primary_config_id: str = ""

    jina_api_key: str = ""

    neon_db_url: str = ""
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    redis_user_key: str = ""

    rag_api_key: str = ""
    rate_limit_per_minute: int = 20

    logfire_token: str = ""
    logfire_base_url: str = ""

    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = "kubernetes_chatbot"

    backend_url: str = "http://localhost:8000"
    judge_openai_api_key: str = ""

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
