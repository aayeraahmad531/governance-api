from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LLM_PROVIDER: str = "gemini"
    FALLBACK_PROVIDER: Optional[str] = None

    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    ALLOWED_ORIGINS: str = "http://localhost:8080"
    CACHE_TTL_SECONDS: int = 86400
    CACHE_MAX_ENTRIES: int = 500

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins(self) -> List[str]:
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        for origin in origins:
            if "*" in origin:
                raise ValueError(f"Wildcards are not allowed in ALLOWED_ORIGINS: {origin}")
        return origins


settings = Settings()
