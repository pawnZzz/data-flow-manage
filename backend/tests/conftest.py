import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.mysql import MySqlContainer

from app.db.mysql import Base, get_session
from app.main import create_app
from app.models import MemberRole, Project, ProjectMember, ProjectStatus, User  # noqa: F401  注册到 metadata
from app.security import create_access_token, hash_password

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
    # 每个测试前按外键顺序清空，保证隔离
    session.query(ProjectMember).delete()
    session.query(Project).delete()
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


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.rate_limit import limiter
    limiter.reset()
    yield


@pytest.fixture
def seed(mysql_engine):
    """建用户/项目/成员的 helper，并在测试前清空相关表。"""
    Session = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)
    s = Session()
    # 按外键顺序清空
    s.query(ProjectMember).delete()
    s.query(Project).delete()
    s.query(User).delete()
    s.commit()

    class Seed:
        def user(self, username, email=None, password="secret"):
            u = User(
                username=username,
                email=email or f"{username}@x.com",
                password_hash=hash_password(password),
            )
            s.add(u)
            s.commit()
            s.refresh(u)
            return u

        def project(self, owner, name="proj", status="active"):
            p = Project(name=name, created_by=owner.id, status=ProjectStatus(status))
            s.add(p)
            s.commit()
            s.refresh(p)
            s.add(ProjectMember(project_id=p.id, user_id=owner.id, role=MemberRole.owner))
            s.commit()
            return p

        def member(self, project, user, role):
            s.add(
                ProjectMember(project_id=project.id, user_id=user.id, role=MemberRole(role))
            )
            s.commit()

        def token(self, user):
            return create_access_token(subject=str(user.id))

    try:
        yield Seed()
    finally:
        s.close()
