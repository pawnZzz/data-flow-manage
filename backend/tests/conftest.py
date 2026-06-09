import os

import pytest
from fastapi.testclient import TestClient
from neo4j import GraphDatabase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.mysql import MySqlContainer
from testcontainers.neo4j import Neo4jContainer

from app.db.mysql import Base, get_session
from app.db.neo4j_constraints import init_constraints
from app.deps import get_graph_repo
from app.main import create_app
from app.models import MemberRole, Project, ProjectMember, ProjectStatus, User  # noqa: F401  注册到 metadata
from app.repositories.graph_repo import GraphRepo
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


@pytest.fixture(scope="session")
def neo4j_driver():
    with Neo4jContainer("neo4j:5-community") as neo4j:
        driver = GraphDatabase.driver(
            neo4j.get_connection_url(),
            auth=(neo4j.username, neo4j.password),
        )
        init_constraints(driver)
        yield driver
        driver.close()


@pytest.fixture
def graph(neo4j_driver):
    # 每个测试前清空图数据，保证隔离
    with neo4j_driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    return GraphRepo(neo4j_driver)


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
def client(mysql_engine, neo4j_driver):
    # 本应用是 MySQL+Neo4j 双库，client 同时连两库；Neo4j 容器 session 级只起一次。
    TestingSession = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)

    def _override_get_session():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    # 每个测试前清空图数据
    with neo4j_driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_graph_repo] = lambda: GraphRepo(neo4j_driver)
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

        def set_status(self, project, status):
            from app.models import ProjectStatus
            obj = s.get(Project, project.id)
            obj.status = ProjectStatus(status)
            s.commit()

        def token(self, user):
            return create_access_token(subject=str(user.id))

    try:
        yield Seed()
    finally:
        s.close()
