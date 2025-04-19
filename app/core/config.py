from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # API key for MWS GPT API - ** Loaded from .env file **
    MWS_API_KEY: str
    MWS_BASE_URL: str = "https://api.gpt.mws.ru"  # Base URL from .env

    @property
    def MWS_CHAT_COMPLETION_URL(self) -> str:
        return f"{self.MWS_BASE_URL}/v1/chat/completions"

    @property
    def MWS_EMBEDDING_URL(self) -> str:
        return f"{self.MWS_BASE_URL}/v1/embeddings"

    # Vector DB Connection Info (Qdrant as default)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    KNOWLEDGE_COLLECTION_NAME: str = "knowledge_base_mws"
    EMBEDDING_MODEL: str = "bge-m3"

    # Agent-specific LLM model settings (support for Russian language)
    INTENT_MODEL: str = "mws-gpt-alpha"
    EMOTION_MODEL: str = "mws-gpt-alpha"
    KNOWLEDGE_MODEL: str = "mws-gpt-alpha"
    ACTION_MODEL: str = "mws-gpt-alpha"
    SUMMARY_MODEL: str = "mws-gpt-alpha"
    QA_MODEL: str = "mws-gpt-alpha"

    # Miscellaneous settings
    LOG_LEVEL: str = "INFO"
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: float = 30.0

    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_file_encoding='utf-8')

@lru_cache()
def get_settings() -> Settings:
    return Settings()
