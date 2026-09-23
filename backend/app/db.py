"""Подключение к PostgreSQL и управление сессиями.

`python -m app.db create` — создать базу (если нет) и таблицы.
"""
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)


def configure(url: str) -> Engine:
    """Переключить приложение на другую БД (используется тестами)."""
    global engine
    engine.dispose()
    engine = create_engine(url, pool_pre_ping=True)
    return engine


def init_db() -> None:
    from app import models  # noqa: F401 — регистрирует таблицы в metadata

    SQLModel.metadata.create_all(engine)


def new_session() -> Session:
    return Session(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI-зависимость."""
    with new_session() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with new_session() as session:
        yield session


def ensure_database(url: str) -> bool:
    """Создать базу данных, если её нет. Возвращает True, если создана."""
    parsed = make_url(url)
    name = parsed.database
    conninfo = dict(
        host=parsed.host or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        dbname="postgres",
        autocommit=True,
    )
    if parsed.password:
        conninfo["password"] = parsed.password
    with psycopg.connect(**conninfo) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists:
            return False
        conn.execute(f'CREATE DATABASE "{name}"')
        return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "create":
        created = ensure_database(settings.database_url)
        init_db()
        print(("База создана" if created else "База уже существует") + ", таблицы готовы.")
    else:
        print("Использование: python -m app.db create")
