from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/focuspulse"
    sync_secret_key: str = "change-me-in-production"
    device_code_length: int = 6
    daily_summary_hour: int = 2  # UTC hour to run daily aggregation

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
