from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://admin:secret@timescaledb:5432/metrics"
    sqlite_path: str = "/app/data/audit.db"
    secret_key: str = "dev-secret"
    # debug=True включает echo всех SQL-запросов SQLAlchemy — только для отладки
    debug: bool = False
    entropy_threshold: float = 7.2
    # Bearer-токен для аутентификации машина-машина (агент/borg → backend).
    # Пусто — проверка отключена (демо без секретов).
    rg_token: str = ""
    # URL control-сервера агента (форвардинг сброса lockdown владельцу FS)
    agent_url: str = "http://agent:9101"


settings = Settings()
