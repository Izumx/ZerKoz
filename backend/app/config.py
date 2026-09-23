from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/zherkoz"
    test_database_url: str = ""
    bot_token: str = ""
    upload_dir: Path = BACKEND_DIR / "uploads"
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
