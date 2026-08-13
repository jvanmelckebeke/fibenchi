from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fibenchi:fibenchi@db:5432/fibenchi"
    refresh_cron: str = "0 23 * * *"
    price_provider: str = "yahoo"
    log_level: str = "INFO"

    model_config = {"env_prefix": ""}


settings = Settings()
