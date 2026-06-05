import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.mysql import MySqlContainer

from app.db.mysql import Base, get_session
from app.main import create_app
from app.models import User  # noqa: F401  注册到 metadata

# Docker Desktop on macOS uses a non-default socket path
_DOCKER_SOCK = os.path.expanduser("~/.docker/run/docker.sock")
if os.path.exists(_DOCKER_SOCK) and not os.environ.get("DOCKER_HOST"):
    os.environ["DOCKER_HOST"] = f"unix://{_DOCKER_SOCK}"

# Ryuk (the testcontainers reaper) tries to bind-mount the docker socket into a
# container, which fails on macOS Docker Desktop when the socket lives under
# ~/. Disable Ryuk entirely — the `with MySqlContainer(...)` context manager
# still stops the container on exit.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


@pytest.fixture(scope="session")
def mysql_engine():
    # Pass dialect="pymysql" so get_connection_url() emits mysql+pymysql://...
    # instead of the bare mysql:// that defaults to the unavailable mysqldb driver.
    with MySqlContainer("mysql:8.0", dialect="pymysql") as mysql:
        engine = create_engine(mysql.get_connection_url(), future=True)
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()


@pytest.fixture
def db_session(mysql_engine):
    TestingSession = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    # 每个测试前清空 users，保证隔离
    session.query(User).delete()
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(mysql_engine):
    TestingSession = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)

    def _override_get_session():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
