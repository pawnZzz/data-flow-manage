# 任务血缘工具 Phase 1：后端基础 + 认证 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建后端工程骨架（FastAPI + MySQL + Neo4j 连接），并实现完整的用户认证（注册、登录、JWT、当前用户、改密码）。

**Architecture:** 分层结构 routers → services → repositories/models。Phase 1 的认证只依赖 MySQL（SQLAlchemy 2.0 + Alembic）；Neo4j 连接在本阶段仅建立连接与健康检查，图相关功能留到后续阶段。统一异常处理把业务异常映射为结构化 JSON。鉴权用无状态 JWT（Bearer Token）。

**Tech Stack:** Python 3.10+、FastAPI、Uvicorn、SQLAlchemy 2.0、Alembic、PyMySQL、neo4j（官方 driver）、pydantic-settings、bcrypt、PyJWT、pytest、testcontainers[mysql]、httpx。

参考 spec：`docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§2 技术栈、§4.1 MySQL users 表、§5.1 鉴权接口、§8 错误处理、§12 安全要点）。

---

## File Structure

本阶段创建/修改的文件及职责：

- `backend/pyproject.toml` — 依赖与工具配置（pytest、ruff）。
- `backend/.env.example` — 配置模板。
- `backend/app/__init__.py` — 包标记。
- `backend/app/config.py` — `Settings`（pydantic-settings），集中读环境变量。
- `backend/app/db/__init__.py`
- `backend/app/db/mysql.py` — SQLAlchemy `engine`、`SessionLocal`、`Base`。
- `backend/app/db/neo4j.py` — Neo4j driver 单例 + ping。
- `backend/app/exceptions.py` — 业务异常类 + FastAPI 异常处理器。
- `backend/app/security.py` — 密码哈希（bcrypt）+ JWT 编解码。
- `backend/app/models/__init__.py`
- `backend/app/models/user.py` — `User` ORM 模型（对应 spec §4.1 users 表）。
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/auth.py` — Pydantic 请求/响应模型。
- `backend/app/deps.py` — `get_db`、`get_current_user` 依赖。
- `backend/app/services/__init__.py`
- `backend/app/services/auth_service.py` — 注册/认证/改密的业务逻辑。
- `backend/app/routers/__init__.py`
- `backend/app/routers/auth.py` — `/auth/*` 路由。
- `backend/app/main.py` — FastAPI app 装配（路由、异常处理、CORS、限流、健康检查）。
- `backend/app/rate_limit.py` — slowapi limiter 单例。
- `backend/migrations/` — Alembic 目录（env.py、versions/）。
- `backend/alembic.ini` — Alembic 配置。
- `backend/tests/conftest.py` — testcontainers MySQL fixture + 测试用 app/client。
- `backend/tests/test_health.py`、`test_security.py`、`test_auth_service.py`、`test_auth_api.py`、`test_rate_limit.py` — 测试。
- `docker-compose.yml` — MySQL + Neo4j 依赖（Phase 1 用到这两个）。
- `backend/README.md` — 启动与测试说明。

## Task 1: 项目脚手架与依赖

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: 创建 `backend/pyproject.toml`**

```toml
[project]
name = "lineage-backend"
version = "0.1.0"
description = "任务血缘管理工具后端"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pymysql>=1.1",
    "neo4j>=5.18",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "bcrypt>=4.1",
    "pyjwt>=2.8",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "testcontainers[mysql]>=4.0",
    "ruff>=0.3",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"

[tool.ruff]
line-length = 100
target-version = "py310"
```

- [ ] **Step 2: 创建 `backend/.env.example`**

```bash
# MySQL
MYSQL_DSN=mysql+pymysql://lineage:lineage@localhost:3306/lineage
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jpassword
# JWT
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=720
# CORS（逗号分隔）
CORS_ORIGINS=http://localhost:5173
# 图遍历路径深度上限
MAX_TRAVERSAL_DEPTH=15
# 是否允许注册
ALLOW_REGISTRATION=true
```

- [ ] **Step 3: 创建空包标记文件**

`backend/app/__init__.py` 和 `backend/tests/__init__.py` 均为空文件。

- [ ] **Step 4: 安装依赖验证**

Run: `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: 安装成功，无依赖冲突。

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/app/__init__.py backend/tests/__init__.py
git commit -m "chore: backend 脚手架与依赖"
```

## Task 2: 配置模块

**Files:**
- Create: `backend/app/config.py`

- [ ] **Step 1: 创建 `backend/app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mysql_dsn: str = "mysql+pymysql://lineage:lineage@localhost:3306/lineage"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4jpassword"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    cors_origins: str = "http://localhost:5173"
    max_traversal_depth: int = 15
    allow_registration: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: 手动验证配置加载**

Run: `cd backend && python -c "from app.config import get_settings; print(get_settings().jwt_algorithm)"`
Expected: 打印 `HS256`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: 配置模块 Settings"
```

## Task 3: 数据库连接（MySQL + Neo4j）

**Files:**
- Create: `backend/app/db/__init__.py` (空)
- Create: `backend/app/db/mysql.py`
- Create: `backend/app/db/neo4j.py`

- [ ] **Step 1: 创建 `backend/app/db/mysql.py`**

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
engine = create_engine(_settings.mysql_dsn, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: 创建 `backend/app/db/neo4j.py`**

```python
from neo4j import Driver, GraphDatabase

from app.config import get_settings

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        s = get_settings()
        _driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    return _driver


def ping() -> bool:
    """验证 Neo4j 可连通；连不上抛异常。"""
    get_driver().verify_connectivity()
    return True


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
```

- [ ] **Step 3: 创建 `backend/app/db/__init__.py`（空文件）**

- [ ] **Step 4: 手动验证导入无误**

Run: `cd backend && python -c "from app.db.mysql import Base, engine; from app.db.neo4j import get_driver; print('ok')"`
Expected: 打印 `ok`（不实际连库）

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/
git commit -m "feat: MySQL 与 Neo4j 连接模块"
```

## Task 4: 业务异常与统一异常处理

**Files:**
- Create: `backend/app/exceptions.py`

实现 spec §8 的统一错误响应：`{"error": {"code", "message", "details"}}`。

- [ ] **Step 1: 创建 `backend/app/exceptions.py`**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常基类。"""

    status_code: int = 400
    code: str = "APP_ERROR"

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class PermissionDenied(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"


class AuthError(AppError):
    status_code = 401
    code = "AUTH_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
```

- [ ] **Step 2: 手动验证导入**

Run: `cd backend && python -c "from app.exceptions import AppError, ConflictError; print(ConflictError('x').code)"`
Expected: 打印 `CONFLICT`

- [ ] **Step 3: Commit**

```bash
git add backend/app/exceptions.py
git commit -m "feat: 业务异常类与统一异常处理器"
```

## Task 5: FastAPI app 骨架 + 健康检查

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/routers/__init__.py` (空)
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

健康检查不依赖外部库连通性（避免测试需要真库）；Neo4j/MySQL 的真实连通在集成测试单独覆盖。

- [ ] **Step 1: 写失败测试 `backend/tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: 创建最小 `backend/tests/conftest.py`**

```python
# Phase 1 健康检查测试不需要数据库 fixture；
# 数据库 fixture 在 Task 9 引入。
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL（`app.main` 或 `create_app` 不存在 / ImportError）

- [ ] **Step 4: 创建 `backend/app/routers/__init__.py`（空）**

- [ ] **Step 5: 实现 `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="任务血缘管理工具", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/routers/__init__.py backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat: FastAPI app 骨架与健康检查"
```

## Task 6: User ORM 模型

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`

对应 spec §4.1 `users` 表。

- [ ] **Step 1: 创建 `backend/app/models/user.py`**

```python
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.active, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: 创建 `backend/app/models/__init__.py`**

```python
from app.models.user import User, UserStatus

__all__ = ["User", "UserStatus"]
```

- [ ] **Step 3: 手动验证模型映射**

Run: `cd backend && python -c "from app.models import User; print(User.__tablename__, [c.name for c in User.__table__.columns])"`
Expected: 打印 `users ['id', 'username', 'email', 'password_hash', 'display_name', 'status', 'created_at', 'updated_at']`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/
git commit -m "feat: User ORM 模型"
```

## Task 7: 安全模块（密码哈希 + JWT）

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_security.py`**

```python
import pytest

from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = create_access_token(subject="42")
    assert decode_access_token(token) == "42"


def test_jwt_invalid_returns_none():
    assert decode_access_token("not-a-token") is None
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: FAIL（ImportError：`app.security` 不存在）

- [ ] **Step 3: 实现 `backend/app/security.py`**

```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/security.py backend/tests/test_security.py
git commit -m "feat: 密码哈希与 JWT 安全模块"
```

## Task 8: Alembic 迁移（users 表）

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_create_users.py`

- [ ] **Step 1: 创建 `backend/alembic.ini`**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 2: 创建 `backend/migrations/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: 创建 `backend/migrations/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db.mysql import Base
from app.models import User  # noqa: F401  确保模型被导入注册到 metadata

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().mysql_dsn)
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 创建 `backend/migrations/versions/0001_create_users.py`**

```python
"""create users

Revision ID: 0001
Revises:
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "disabled", name="userstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("users")
```

- [ ] **Step 5: 验证迁移可离线生成 SQL（不需真库）**

Run: `cd backend && alembic upgrade head --sql`
Expected: 打印 `CREATE TABLE users (...)`，无报错。

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/migrations/
git commit -m "feat: Alembic 迁移创建 users 表"
```

## Task 9: 测试基础设施（testcontainers MySQL fixture）

**Files:**
- Modify: `backend/tests/conftest.py`

提供一个真实 MySQL（testcontainers）做集成测试，并覆盖 `get_session` 依赖。建表用 `Base.metadata.create_all`（测试场景，不跑 Alembic）。

- [ ] **Step 1: 重写 `backend/tests/conftest.py`（前 40 行）**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.mysql import MySqlContainer

from app.db.mysql import Base, get_session
from app.main import create_app
from app.models import User  # noqa: F401  注册到 metadata


@pytest.fixture(scope="session")
def mysql_engine():
    with MySqlContainer("mysql:8.0") as mysql:
        engine = create_engine(mysql.get_connection_url(), future=True)
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()
```

- [ ] **Step 2: 追加 fixture（client + db session 覆盖）到 `conftest.py`**

```python
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
```

- [ ] **Step 3: 运行已有健康检查测试，确认仍通过（conftest 改动不破坏）**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS（health 测试不使用 db fixture，仍通过）

> 注：本任务引入的 MySQL fixture 需要本机 Docker 可用。若 Docker 不可用，集成测试会在收集阶段跳过容器启动而失败 —— 这是预期，实现时需确保 Docker 已启动。

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: testcontainers MySQL fixture 与 client 覆盖"
```

## Task 10: 认证 Pydantic schemas

**Files:**
- Create: `backend/app/schemas/__init__.py` (空)
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 1: 创建 `backend/app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str | None
    status: str

    class Config:
        from_attributes = True


class UpdateMeRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)
```

- [ ] **Step 2: 创建 `backend/app/schemas/__init__.py`（空）**

- [ ] **Step 3: 手动验证（EmailStr 依赖 email-validator）**

Run: `cd backend && pip install email-validator && python -c "from app.schemas.auth import RegisterRequest; print(RegisterRequest(username='abc', email='a@b.com', password='secret').email)"`
Expected: 打印 `a@b.com`

> 实现注意：把 `email-validator` 加入 `pyproject.toml` 的 dependencies（与 pydantic[email] 等效），并重新 `pip install -e ".[dev]"`。

- [ ] **Step 4: 把 `email-validator>=2.0` 加入 `backend/pyproject.toml` 的 `dependencies` 列表**

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/ backend/pyproject.toml
git commit -m "feat: 认证请求/响应 Pydantic schemas"
```

## Task 11: 认证服务层

**Files:**
- Create: `backend/app/services/__init__.py` (空)
- Create: `backend/app/services/auth_service.py`
- Test: `backend/tests/test_auth_service.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_auth_service.py`**

```python
import pytest

from app.exceptions import AuthError, ConflictError
from app.models import User
from app.security import verify_password
from app.services import auth_service


def test_register_creates_user(db_session):
    user = auth_service.register(db_session, "alice", "alice@x.com", "secret", "Alice")
    assert user.id is not None
    assert user.username == "alice"
    assert verify_password("secret", user.password_hash)


def test_register_duplicate_username_conflicts(db_session):
    auth_service.register(db_session, "bob", "bob@x.com", "secret", None)
    with pytest.raises(ConflictError):
        auth_service.register(db_session, "bob", "bob2@x.com", "secret", None)


def test_authenticate_success(db_session):
    auth_service.register(db_session, "carol", "carol@x.com", "secret", None)
    user = auth_service.authenticate(db_session, "carol", "secret")
    assert user.username == "carol"


def test_authenticate_wrong_password_raises(db_session):
    auth_service.register(db_session, "dave", "dave@x.com", "secret", None)
    with pytest.raises(AuthError):
        auth_service.authenticate(db_session, "dave", "wrong")


def test_change_password(db_session):
    user = auth_service.register(db_session, "eve", "eve@x.com", "secret", None)
    auth_service.change_password(db_session, user, "secret", "newpass")
    assert auth_service.authenticate(db_session, "eve", "newpass").id == user.id
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_auth_service.py -v`
Expected: FAIL（ImportError：`auth_service` 不存在）

- [ ] **Step 3: 实现 `backend/app/services/auth_service.py`**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import AuthError, ConflictError
from app.models import User, UserStatus
from app.security import hash_password, verify_password


def register(
    db: Session, username: str, email: str, password: str, display_name: str | None
) -> User:
    exists = db.scalar(
        select(User).where((User.username == username) | (User.email == email))
    )
    if exists:
        field = "username" if exists.username == username else "email"
        raise ConflictError("用户名或邮箱已存在", {"field": field})

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("用户名或密码错误")
    if user.status == UserStatus.disabled:
        raise AuthError("账号已禁用")
    return user


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise AuthError("原密码错误")
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()


def update_profile(db: Session, user: User, display_name: str | None) -> User:
    if display_name is not None:
        user.display_name = display_name
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

- [ ] **Step 4: 创建 `backend/app/services/__init__.py`（空）**

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_auth_service.py -v`
Expected: PASS（5 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ backend/tests/test_auth_service.py
git commit -m "feat: 认证服务层（注册/认证/改密/改资料）"
```

## Task 12: 依赖注入（get_current_user）

**Files:**
- Create: `backend/app/deps.py`

- [ ] **Step 1: 创建 `backend/app/deps.py`**

```python
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.mysql import get_session
from app.exceptions import AuthError
from app.models import User
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_session)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None:
        raise AuthError("缺少认证凭证")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AuthError("无效或过期的 token")
    user = db.scalar(select(User).where(User.id == int(user_id)))
    if user is None:
        raise AuthError("用户不存在")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

- [ ] **Step 2: 手动验证导入**

Run: `cd backend && python -c "from app.deps import get_current_user, CurrentUser, DbSession; print('ok')"`
Expected: 打印 `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/deps.py
git commit -m "feat: get_current_user 依赖与类型别名"
```

## Task 13: 认证路由

**Files:**
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`（注册路由）

实现 spec §5.1：register / login / logout / me(GET,PATCH) / password。

- [ ] **Step 1: 创建 `backend/app/routers/auth.py`（前 45 行）**

```python
from fastapi import APIRouter, status

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.exceptions import PermissionDenied
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
)
from app.security import create_access_token
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> UserResponse:
    if not get_settings().allow_registration:
        raise PermissionDenied("当前不允许注册")
    user = auth_service.register(
        db, payload.username, payload.email, payload.password, payload.display_name
    )
    return UserResponse.model_validate(user)
```

- [ ] **Step 2: 追加其余路由到 `backend/app/routers/auth.py`**

```python
@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = auth_service.authenticate(db, payload.username, payload.password)
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: CurrentUser) -> None:
    # 无状态 JWT：前端丢弃 token 即可。此处仅作为受保护端点占位（后续接审计）。
    return None


@router.get("/me", response_model=UserResponse)
def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(payload: UpdateMeRequest, current_user: CurrentUser, db: DbSession) -> UserResponse:
    user = auth_service.update_profile(db, current_user, payload.display_name)
    return UserResponse.model_validate(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest, current_user: CurrentUser, db: DbSession
) -> None:
    auth_service.change_password(db, current_user, payload.old_password, payload.new_password)
    return None
```

- [ ] **Step 3: 在 `backend/app/main.py` 注册路由**

在 `create_app()` 中 `register_exception_handlers(app)` 之后、health 定义之前，加入：

```python
    from app.routers import auth as auth_router

    app.include_router(auth_router.router)
```

- [ ] **Step 4: 手动验证 app 可启动（路由已挂载）**

Run: `cd backend && python -c "from app.main import create_app; app=create_app(); print([r.path for r in app.routes if 'auth' in r.path])"`
Expected: 打印包含 `/api/v1/auth/register`、`/api/v1/auth/login`、`/api/v1/auth/me`、`/api/v1/auth/password` 等路径的列表。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py backend/app/main.py
git commit -m "feat: 认证路由 register/login/logout/me/password"
```

## Task 14: 认证 API 集成测试

**Files:**
- Test: `backend/tests/test_auth_api.py`

端到端验证 spec §5.1 全部认证接口 + §8 错误响应结构。

- [ ] **Step 1: 写测试 `backend/tests/test_auth_api.py`（前 45 行）**

```python
def _register(client, username="alice", email="alice@x.com", password="secret"):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def test_register_then_login(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.json()["username"] == "alice"

    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_register_duplicate_returns_409_structured(client):
    _register(client)
    r = _register(client)
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "CONFLICT"
    assert "message" in body["error"]
```

- [ ] **Step 2: 追加受保护端点与错误用例到 `test_auth_api.py`**

```python
def _token(client, username="alice", password="secret"):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_ERROR"


def test_me_with_token(client):
    _register(client)
    token = _token(client)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_login_wrong_password_401(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "nope"})
    assert r.status_code == 401


def test_update_me(client):
    _register(client)
    token = _token(client)
    r = client.patch(
        "/api/v1/auth/me",
        json={"display_name": "Alice L"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Alice L"


def test_change_password_then_login(client):
    _register(client)
    token = _token(client)
    r = client.post(
        "/api/v1/auth/password",
        json={"old_password": "secret", "new_password": "brandnew"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "brandnew"})
    assert r.status_code == 200
```

- [ ] **Step 3: 运行全部测试，确认通过**

Run: `cd backend && pytest -v`
Expected: PASS（test_health + test_security + test_auth_service + test_auth_api 全绿）

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_auth_api.py
git commit -m "test: 认证 API 端到端集成测试"
```

## Task 15: README 与 docker-compose（数据库依赖）

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/README.md`

让开发者能一键起 MySQL + Neo4j 并跑通后端。

- [ ] **Step 1: 创建 `docker-compose.yml`**

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: lineage
      MYSQL_USER: lineage
      MYSQL_PASSWORD: lineage
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-prootpass"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - mysql_data:/var/lib/mysql

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/neo4jpassword
    ports:
      - "7474:7474"
      - "7687:7687"
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "neo4jpassword", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 10
    volumes:
      - neo4j_data:/data

volumes:
  mysql_data:
  neo4j_data:
```

- [ ] **Step 2: 创建 `backend/README.md`**

````markdown
# 后端（Phase 1：认证）

## 启动依赖

```bash
docker compose up -d mysql neo4j
```

## 安装与初始化

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
```

## 运行

```bash
uvicorn app.main:app --reload
# 健康检查
curl http://localhost:8000/api/v1/health
```

## 测试

需要本机 Docker（testcontainers 会拉起临时 MySQL）：

```bash
pytest -v
```
````

- [ ] **Step 3: 验证 compose 文件语法**

Run: `docker compose config -q`
Expected: 无输出（语法合法）。

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml backend/README.md
git commit -m "docs: docker-compose 数据库依赖与后端 README"
```

## Task 16: 登录接口限流（spec §12）

**Files:**
- Modify: `backend/pyproject.toml`（加 `slowapi`）
- Modify: `backend/app/main.py`（装配 limiter）
- Modify: `backend/app/routers/auth.py`（给 login 加限流）
- Test: `backend/tests/test_rate_limit.py`

用 slowapi 做进程内简单限流，防登录爆破。单实例工具用内存存储即可。

- [ ] **Step 1: 把 `slowapi>=0.1.9` 加入 `backend/pyproject.toml` 的 `dependencies`，并 `pip install -e ".[dev]"`**

- [ ] **Step 2: 写失败测试 `backend/tests/test_rate_limit.py`**

```python
def test_login_rate_limited(client):
    # 默认限流 5/分钟；第 6 次应返回 429
    payloads = {"username": "ghost", "password": "x"}
    codes = [client.post("/api/v1/auth/login", json=payloads).status_code for _ in range(6)]
    assert codes[-1] == 429
    assert all(c in (401, 429) for c in codes)
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_rate_limit.py -v`
Expected: FAIL（第 6 次仍是 401，而非 429）

- [ ] **Step 4: 在 `backend/app/main.py` 装配 limiter**

在 imports 区加入：

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
```

在 `create_app()` 内，创建 app 之后、`include_router` 之前加入：

```python
    limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [ ] **Step 5: 给 `backend/app/routers/auth.py` 的 login 加限流装饰器**

在 imports 区加入：

```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

把 `login` 改为（注意 slowapi 要求形参里有 `request: Request`）：

```python
@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = auth_service.authenticate(db, payload.username, payload.password)
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))
```

> 注意：slowapi 的 limiter 需要与 `app.state.limiter` 是同一实例才能共享计数。实现时把 limiter 抽到独立模块 `backend/app/rate_limit.py`（`limiter = Limiter(key_func=get_remote_address)`），main.py 和 auth.py 都从该模块导入同一个 `limiter`，避免双实例。

- [ ] **Step 6: 把 limiter 抽到 `backend/app/rate_limit.py`**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

main.py 改为 `from app.rate_limit import limiter`；auth.py 改为 `from app.rate_limit import limiter`，删除各自的局部 `Limiter(...)` 定义。

- [ ] **Step 7: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_rate_limit.py -v`
Expected: PASS（第 6 次返回 429）

- [ ] **Step 8: 运行全部测试，确认无回归**

Run: `cd backend && pytest -v`
Expected: 全绿。

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/app/main.py backend/app/routers/auth.py backend/app/rate_limit.py backend/tests/test_rate_limit.py
git commit -m "feat: 登录接口限流防爆破"
```

## Phase 1 完成标准（Definition of Done）

- [ ] `pytest -v` 全绿（health / security / auth_service / auth_api）。
- [ ] `alembic upgrade head` 在真实 MySQL 上成功建出 `users` 表。
- [ ] `uvicorn app.main:app` 可启动，`/api/v1/health` 返回 `{"status":"ok"}`。
- [ ] 可完成注册 → 登录拿 token → 带 token 访问 `/auth/me` 的完整流程。
- [ ] 错误响应符合 spec §8 结构（`{"error":{"code","message","details"}}`）。
- [ ] 登录接口超过阈值返回 429（spec §12 限流）。

## 下一阶段预告（不在本计划内）

Phase 2：项目 + 成员 + RBAC + 审计日志基础设施。将复用本阶段的 `AppError` 体系、`get_current_user`、testcontainers fixture，并新增 `require_role` 依赖。









