import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel

from app import db
from app.config import settings


def _test_url() -> str:
    if settings.test_database_url:
        return settings.test_database_url
    url = make_url(settings.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


@pytest.fixture(scope="session", autouse=True)
def _database(tmp_path_factory):
    url = _test_url()
    db.ensure_database(url)
    db.configure(url)
    from app import models  # noqa: F401

    SQLModel.metadata.drop_all(db.engine)
    SQLModel.metadata.create_all(db.engine)
    settings.upload_dir = tmp_path_factory.mktemp("uploads")
    yield
    db.engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    tables = ", ".join(f'"{t.name}"' for t in SQLModel.metadata.sorted_tables)
    with db.engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def session():
    with db.new_session() as s:
        yield s
