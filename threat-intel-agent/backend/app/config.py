import json
import secrets
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    LLM_API_KEY: str = "sk-your-api-key-here"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL_NAME: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096

    DATABASE_URL: str = "sqlite+aiosqlite:///./threat_intel.db"

    CHROMA_PERSIST_DIR: str = "./chroma_data"

    LOG_LEVEL: str = "INFO"

    CORS_ORIGINS: str = '["http://localhost:5173"]'

    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    RATE_LIMIT_PER_MINUTE: int = 60
    MAX_CONCURRENT_TASKS: int = 3
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    TELEGRAM_BOT_TOKEN: str = ""
    ALIENVAULT_OTX_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""
    ABUSEIPDB_API_KEY: str = ""

    @property
    def secret_key_resolved(self) -> str:
        if self.SECRET_KEY and self.SECRET_KEY != "change-me-in-production-use-a-strong-random-key":
            return self.SECRET_KEY
        key_file = Path(__file__).resolve().parent.parent / ".secret_key"
        if key_file.exists():
            return key_file.read_text().strip()
        generated = secrets.token_urlsafe(48)
        key_file.write_text(generated)
        return generated

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5173"]


settings = Settings()
