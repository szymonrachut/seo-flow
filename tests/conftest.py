from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.api.main import app
from app.db.base import Base


@pytest.fixture
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "stage2.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture
def db_session(sqlite_session_factory) -> Generator[Session, None, None]:
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client(sqlite_session_factory) -> Generator[TestClient, None, None]:
    def override_get_db():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
