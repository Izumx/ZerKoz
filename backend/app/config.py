from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/zherkoz"
    test_database_url: str = ""
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"
    host: str = "0.0.0.0"
    port: int = 8000

    # доступ к панели инспектора: пусто — панель открыта (локальная разработка)
    inspector_password: str = ""
    secret_key: str = ""
    # кнопка «Демо: сигнал жителя» и POST /api/demo/signal
    demo_mode: bool = True
    # при пустой БД сгенерировать демо-данные на старте (удобно для облачного деплоя)
    seed_on_start: bool = False

    # Telegram
    bot_token: str = ""
    # публичный https-адрес сервиса: если задан, бот работает через webhook, иначе polling
    public_url: str = ""
    redis_url: str = ""
    signals_per_hour: int = 5
    signals_per_day: int = 20

    # опциональные интеграции
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"
    copernicus_client_id: str = ""
    copernicus_client_secret: str = ""

    # точка старта маршрута выезда (управление земельных отношений, Тараз)
    office_lat: float = 42.8995
    office_lon: float = 71.3780


settings = Settings()
