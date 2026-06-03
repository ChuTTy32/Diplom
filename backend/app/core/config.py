from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://admin:secret@timescaledb:5432/metrics"
    sqlite_path: str = "/app/data/audit.db"
    secret_key: str = "dev-secret"
    debug: bool = True
    entropy_threshold: float = 7.2

    class Config:
        env_file = ".env"


settings = Settings()
