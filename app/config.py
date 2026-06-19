import hashlib
import secrets
import string
from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    sync_secret_key: str = "change-me-in-production"
    device_code_length: int = 6
    daily_summary_hour: int = 2  # UTC hour to run daily aggregation

    # Zeabur individual PostgreSQL env vars (fallback when database_url not set)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "focuspulse"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    model_config = {"env_prefix": "", "case_sensitive": False, "env_file": ".env"}

    @model_validator(mode="after")
    def _resolve_database_url(self):
        """Resolve the effective database URL from either DATABASE_URL or POSTGRES_* vars."""
        if self.database_url:
            # Ensure asyncpg driver prefix
            if "+asyncpg" not in self.database_url:
                self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            # Build from individual POSTGRES_* env vars (Zeabur style)
            self.database_url = (
                f"postgresql+asyncpg://{quote(self.postgres_user, safe='')}:{quote(self.postgres_password, safe='')}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
            )
        return self


settings = Settings()


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(f"{settings.sync_secret_key}:{raw}".encode()).hexdigest()


def generate_api_key() -> str:
    return "fp_" + secrets.token_hex(24)


def generate_device_code() -> str:
    alphabet = string.ascii_uppercase.replace("O", "").replace("I", "").replace("L", "") + string.digits
    # Remove 0 from digits
    alphabet = alphabet.replace("0", "")
    return "".join(secrets.choice(alphabet) for _ in range(settings.device_code_length))
