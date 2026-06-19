import hashlib
import secrets
import string
from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Primary: direct database URL (standard DATABASE_URL or Zeabur's POSTGRES_URI)
    database_url: str = ""

    # Zeabur provides these as individual env vars
    postgres_connection_string: str = ""
    postgres_uri: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "focuspulse"
    postgres_username: str = "postgres"
    postgres_password: str = ""

    sync_secret_key: str = "change-me-in-production"
    device_code_length: int = 6
    daily_summary_hour: int = 2

    model_config = {"env_prefix": "", "case_sensitive": False, "env_file": ".env"}

    @model_validator(mode="after")
    def _resolve_database_url(self):
        # Priority: explicit database_url > POSTGRES_CONNECTION_STRING > POSTGRES_URI > individual vars
        url = self.database_url or self.postgres_connection_string or self.postgres_uri or ""
        if url:
            # Ensure asyncpg driver prefix
            if "+asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            # Build from individual POSTGRES_* env vars (Zeabur style)
            url = (
                f"postgresql+asyncpg://{quote(self.postgres_username, safe='')}:{quote(self.postgres_password, safe='')}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
            )
        self.database_url = url
        return self


settings = Settings()


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(f"{settings.sync_secret_key}:{raw}".encode()).hexdigest()


def generate_api_key() -> str:
    return "fp_" + secrets.token_hex(24)


def generate_device_code() -> str:
    alphabet = string.ascii_uppercase.replace("O", "").replace("I", "").replace("L", "") + string.digits
    alphabet = alphabet.replace("0", "")
    return "".join(secrets.choice(alphabet) for _ in range(settings.device_code_length))
