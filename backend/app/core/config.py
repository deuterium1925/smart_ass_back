from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    Manages API keys, URLs, model names, and operational parameters for the multi-agent system.
    """
    MWS_API_KEY: str
    MWS_BASE_URL: str

    @property
    def MWS_CHAT_COMPLETION_URL(self) -> str:
        return f"{self.MWS_BASE_URL}/v1/chat/completions"

    @property
    def MWS_EMBEDDING_URL(self) -> str:
        return f"{self.MWS_BASE_URL}/v1/embeddings"

    QDRANT_URL: str
    QDRANT_API_KEY: Optional[str] = None
    KNOWLEDGE_COLLECTION_NAME: str
    EMBEDDING_MODEL: str

    INTENT_MODEL: str
    EMOTION_MODEL: str
    KNOWLEDGE_MODEL: str
    ACTION_MODEL: str
    SUMMARY_MODEL: str
    QA_MODEL: str

    LOG_LEVEL: str = "DEBUG"
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: float = 60.0  # Increased from 30.0 to 60.0 to handle rate limiting and retries

    model_config = SettingsConfigDict(env_file='.env', extra='ignore', env_file_encoding='utf-8')

@lru_cache()
def get_settings() -> Settings:
    """
    Retrieve cached application settings for efficient access.
    Uses LRU cache to avoid reloading environment variables repeatedly.
    """
    return Settings()
