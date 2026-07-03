import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_dev_database_url = os.environ["DATABASE_URL"]
_test_db_name = "medlens_test_db"
_test_database_url = _dev_database_url.rsplit("/", 1)[0] + f"/{_test_db_name}"

assert _test_db_name in _test_database_url

os.environ["DATABASE_URL"] = _test_database_url

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402,F401


def _ensure_test_database_exists() -> None:
    maintenance_url = _test_database_url.rsplit("/", 1)[0] + "/postgres"

    conn = psycopg2.connect(maintenance_url)
    conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (_test_db_name,)
            )

            if cursor.fetchone() is None:
                cursor.execute(f'CREATE DATABASE "{_test_db_name}"')
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    assert settings.database_url == _test_database_url
    assert _test_db_name in settings.database_url

    _ensure_test_database_exists()

    Base.metadata.create_all(bind=engine)

    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    assert _test_db_name in str(engine.url)

    yield

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture
def client():
    return TestClient(app)
