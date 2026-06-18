import hashlib
import secrets
import string

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/focuspulse"
    sync_secret_key: str = "change-me-in-production"
    device_code_length: int = 6
    daily_summary_hour: int = 2  # UTC hour to run daily aggregation

    model_config = {"env_prefix": "", "case_sensitive": False}


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
