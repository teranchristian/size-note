from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Size Note"
    database_url: str = "sqlite:///./data/size-note.db"
    api_base_url: str = "http://127.0.0.1:3010"
    auto_create_schema: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SIZE_NOTE_",
        extra="ignore",
    )

    @property
    def package_dir(self) -> Path:
        return Path(__file__).resolve().parent


@lru_cache
def get_settings() -> Settings:
    return Settings()
