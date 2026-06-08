# 任务血缘工具 Phase 2：项目 + 成员 + RBAC — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 1 认证之上实现项目工作区与成员管理（项目 CRUD、成员增删改、基于角色的访问控制），纯 MySQL，写操作打 logging。

**Architecture:** 分层 routers → services → models，沿用 Phase 1 结构。权限校验集中在 `require_role(min_role)` FastAPI 依赖工厂，返回 `ProjectContext`（project+membership+user）注入路由，业务代码零权限判断。项目删除为软归档（status→archived）。

**Tech Stack:** Python 3.10+、FastAPI、SQLAlchemy 2.0、Alembic、PyMySQL、pytest、testcontainers[mysql]。

参考 spec：`docs/superpowers/specs/2026-06-08-phase2-projects-members-rbac-design.md`。

---

## File Structure

本阶段创建/修改的文件及职责：

- `backend/app/models/project.py` — 新建。`ProjectStatus`/`MemberRole` 枚举（MemberRole 带 `level`）、`Project`、`ProjectMember` ORM 模型。
- `backend/app/models/__init__.py` — 修改。导出新模型。
- `backend/migrations/versions/0002_create_projects_members.py` — 新建。建两表。
- `backend/migrations/env.py` — 修改。导入新模型注册到 metadata。
- `backend/app/schemas/project.py` — 新建。请求/响应 Pydantic 模型。
- `backend/app/deps.py` — 修改。新增 `ProjectContext`、`require_role(min_role)`。
- `backend/app/services/project_service.py` — 新建。项目业务逻辑 + logging。
- `backend/app/services/member_service.py` — 新建。成员业务逻辑 + 边界规则 + logging。
- `backend/app/routers/projects.py` — 新建。`/projects` 路由。
- `backend/app/routers/members.py` — 新建。`/projects/:pid/members` 路由。
- `backend/app/main.py` — 修改。注册两个新路由。
- `backend/tests/conftest.py` — 修改。新增建用户/项目/成员的 helper fixture 与表清理。
- `backend/tests/test_deps.py` — 新建。`require_role` 单元测试。
- `backend/tests/test_project_api.py` — 新建。项目 API 集成测试。
- `backend/tests/test_member_api.py` — 新建。成员 API 集成测试。
- `backend/tests/test_permission_matrix.py` — 新建。角色 × 端点参数化权限测试。

## Task 1: ORM 模型（projects + project_members）

**Files:**
- Create: `backend/app/models/project.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_project.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_models_project.py`**

```python
from app.models import MemberRole, Project, ProjectMember, ProjectStatus


def test_member_role_levels_ordered():
    assert MemberRole.viewer.level < MemberRole.editor.level
    assert MemberRole.editor.level < MemberRole.admin.level
    assert MemberRole.admin.level < MemberRole.owner.level


def test_project_status_values():
    assert ProjectStatus.active.value == "active"
    assert {s.value for s in ProjectStatus} == {"active", "archived", "deleting"}


def test_tablenames():
    assert Project.__tablename__ == "projects"
    assert ProjectMember.__tablename__ == "project_members"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_models_project.py -v`
Expected: FAIL（`ImportError: cannot import name 'MemberRole'`）

- [ ] **Step 3: 创建 `backend/app/models/project.py`**

```python
import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mysql import Base


class ProjectStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deleting = "deleting"


class MemberRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    editor = "editor"
    viewer = "viewer"

    @property
    def level(self) -> int:
        return _ROLE_LEVELS[self]


_ROLE_LEVELS = {
    MemberRole.viewer: 0,
    MemberRole.editor: 1,
    MemberRole.admin: 2,
    MemberRole.owner: 3,
}


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.active, nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[MemberRole] = mapped_column(Enum(MemberRole), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: 修改 `backend/app/models/__init__.py`**

```python
from app.models.project import MemberRole, Project, ProjectMember, ProjectStatus
from app.models.user import User, UserStatus

__all__ = [
    "User",
    "UserStatus",
    "Project",
    "ProjectMember",
    "ProjectStatus",
    "MemberRole",
]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_models_project.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/project.py backend/app/models/__init__.py backend/tests/test_models_project.py
git commit -m "feat: Project/ProjectMember ORM 模型与角色等级"
```

## Task 2: Alembic 迁移（建两表）

**Files:**
- Create: `backend/migrations/versions/0002_create_projects_members.py`
- Modify: `backend/migrations/env.py`

- [ ] **Step 1: 修改 `backend/migrations/env.py` 第 8 行，导入新模型**

把：
```python
from app.models import User  # noqa: F401  确保模型被导入注册到 metadata
```
改为：
```python
from app.models import (  # noqa: F401  确保模型被导入注册到 metadata
    Project,
    ProjectMember,
    User,
)
```

- [ ] **Step 2: 创建 `backend/migrations/versions/0002_create_projects_members.py`**

```python
"""create projects and project_members

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "archived", "deleting", name="projectstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_by",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_status", "projects", ["status"])

    op.create_table(
        "project_members",
        sa.Column(
            "project_id",
            sa.BigInteger,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "editor", "viewer", name="memberrole"),
            nullable=False,
        ),
        sa.Column("joined_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_user", "project_members", ["user_id"])


def downgrade() -> None:
    op.drop_table("project_members")
    op.drop_table("projects")
```

- [ ] **Step 3: 对真实 MySQL 跑迁移验证（需 docker compose 起 mysql）**

Run:
```bash
docker compose up -d mysql
cd backend && . .venv/bin/activate && alembic upgrade head
```
Expected: 无报错；`alembic current` 显示 `0002 (head)`。

- [ ] **Step 4: 确认表已建出**

Run: `docker compose exec mysql mysql -ulineage -plineage lineage -e "SHOW TABLES; DESCRIBE projects; DESCRIBE project_members;"`
Expected: 列出 `projects`、`project_members`、`users`、`alembic_version`，两表列定义与上面一致。

> 注：`tests/conftest.py` 用 `Base.metadata.create_all` 建表，不走迁移；本 Task 的迁移正确性靠这里手动验证，不写成自动化测试。

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0002_create_projects_members.py backend/migrations/env.py
git commit -m "feat: Alembic 迁移创建 projects 与 project_members 表"
```

## Task 3: 请求/响应 Pydantic schemas

**Files:**
- Create: `backend/app/schemas/project.py`
- Test: `backend/tests/test_schemas_project.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_schemas_project.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.project import AddMemberRequest, CreateProjectRequest


def test_create_project_rejects_empty_name():
    with pytest.raises(ValidationError):
        CreateProjectRequest(name="")


def test_create_project_ok():
    r = CreateProjectRequest(name="数仓血缘", description=None)
    assert r.name == "数仓血缘"


def test_add_member_requires_username_or_email():
    with pytest.raises(ValidationError):
        AddMemberRequest(role="viewer")


def test_add_member_with_username_ok():
    r = AddMemberRequest(username="bob", role="editor")
    assert r.username == "bob"
    assert r.role == "editor"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_schemas_project.py -v`
Expected: FAIL（`ModuleNotFoundError: app.schemas.project`）

- [ ] **Step 3: 创建 `backend/app/schemas/project.py`**

```python
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    my_role: str


class AddMemberRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    role: str = Field(pattern="^(owner|admin|editor|viewer)$")

    @model_validator(mode="after")
    def _need_identifier(self) -> "AddMemberRequest":
        if not self.username and not self.email:
            raise ValueError("username 或 email 至少提供一个")
        return self


class ChangeRoleRequest(BaseModel):
    role: str = Field(pattern="^(owner|admin|editor|viewer)$")


class MemberResponse(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    role: str
    joined_at: datetime
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_schemas_project.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/project.py backend/tests/test_schemas_project.py
git commit -m "feat: 项目/成员请求响应 Pydantic schemas"
```

## Task 4: 测试 helper（conftest 建用户/项目/成员）

**Files:**
- Modify: `backend/tests/conftest.py`

说明：`client` fixture 用独立 `TestingSession`，但与建数据用的 session 绑定同一 `mysql_engine`，commit 后数据互相可见。新增一个 `seed` fixture，提供建用户、建项目（含 owner 成员）、加成员、登录取 token 的 helper，并在每个测试前按外键顺序清空三张表。

- [ ] **Step 1: 在 `backend/tests/conftest.py` 顶部调整 import 并修复 `db_session` 清理顺序**

把顶部 `from app.models import User` 改为：
```python
from app.models import MemberRole, Project, ProjectMember, User
```
并新增 `from app.security import create_access_token, hash_password`（与其他 import 同组）。

然后修改既有 `db_session` fixture 的清理段——原来只删 users，现按外键顺序删三张表（否则 project_members 的外键会让删 users 失败）：

把：
```python
    # 每个测试前清空 users，保证隔离
    session.query(User).delete()
    session.commit()
```
改为：
```python
    # 每个测试前按外键顺序清空，保证隔离
    session.query(ProjectMember).delete()
    session.query(Project).delete()
    session.query(User).delete()
    session.commit()
```

- [ ] **Step 2: 在 `backend/tests/conftest.py` 末尾追加 `seed` fixture**

```python
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
            from app.models import ProjectStatus

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

    yield Seed()
    s.close()
```

- [ ] **Step 3: 修复 `backend/tests/test_auth_api.py` 的 `_clear_users` 清理顺序**

该文件顶部 autouse fixture `_clear_users` 只删 users，全量跑时若残留 project_members 会触发外键违约。

把顶部 `from app.models import User` 改为：
```python
from app.models import Project, ProjectMember, User
```
把 `_clear_users` 里：
```python
    s.query(User).delete()
    s.commit()
```
改为：
```python
    s.query(ProjectMember).delete()
    s.query(Project).delete()
    s.query(User).delete()
    s.commit()
```

- [ ] **Step 4: 运行既有测试确认无回归**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_auth_api.py -v`
Expected: PASS（Phase 1 集成测试不受影响）

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_auth_api.py
git commit -m "test: conftest seed helper 与外键安全的表清理"
```

## Task 5: RBAC 依赖（ProjectContext + require_role）

**Files:**
- Modify: `backend/app/deps.py`
- Test: `backend/tests/test_deps.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_deps.py`**

测试通过一个临时挂载 `require_role` 的端点验证放行/拒绝。

```python
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from typing_extensions import Annotated

from app.db.mysql import get_session
from app.deps import ProjectContext, require_role
from app.exceptions import register_exception_handlers
from app.models import MemberRole


@pytest.fixture
def role_app(mysql_engine):
    from sqlalchemy.orm import sessionmaker

    TestingSession = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/p/{pid}/admin")
    def _admin(ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))]):
        return {"role": ctx.membership.role.value}

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_admin_allows_owner(role_app, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = role_app.get(f"/p/{p.id}/admin", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["role"] == "owner"


def test_admin_rejects_viewer(role_app, seed):
    owner = seed.user("owner")
    viewer = seed.user("viewer")
    p = seed.project(owner)
    seed.member(p, viewer, "viewer")
    r = role_app.get(f"/p/{p.id}/admin", headers=_auth(seed, viewer))
    assert r.status_code == 403


def test_rejects_non_member(role_app, seed):
    owner = seed.user("owner")
    stranger = seed.user("stranger")
    p = seed.project(owner)
    r = role_app.get(f"/p/{p.id}/admin", headers=_auth(seed, stranger))
    assert r.status_code == 403


def test_404_when_project_missing(role_app, seed):
    owner = seed.user("owner")
    r = role_app.get("/p/999999/admin", headers=_auth(seed, owner))
    assert r.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_deps.py -v`
Expected: FAIL（`ImportError: cannot import name 'ProjectContext'`）

- [ ] **Step 3: 在 `backend/app/deps.py` 末尾追加**

文件顶部 import 区补充：
```python
from dataclasses import dataclass

from fastapi import Path

from app.exceptions import NotFoundError, PermissionDenied
from app.models import MemberRole, Project, ProjectMember
```
（`AuthError`、`User`、`select`、`Annotated`、`Depends` 已在 Phase 1 文件中存在，不重复加。）

末尾追加：
```python
@dataclass
class ProjectContext:
    project: Project
    membership: ProjectMember
    user: User


def require_role(min_role: MemberRole):
    def dep(
        pid: Annotated[int, Path()],
        user: CurrentUser,
        db: DbSession,
    ) -> ProjectContext:
        project = db.get(Project, pid)
        if project is None:
            raise NotFoundError("项目不存在")
        membership = db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == pid,
                ProjectMember.user_id == user.id,
            )
        )
        if membership is None:
            raise PermissionDenied("非项目成员")
        if membership.role.level < min_role.level:
            raise PermissionDenied("权限不足")
        return ProjectContext(project=project, membership=membership, user=user)

    return dep
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_deps.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/deps.py backend/tests/test_deps.py
git commit -m "feat: require_role 依赖工厂与 ProjectContext"
```

## Task 6: 项目服务层（project_service）

**Files:**
- Create: `backend/app/services/project_service.py`
- Test: `backend/tests/test_project_service.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_project_service.py`**

```python
from sqlalchemy import select

from app.models import MemberRole, ProjectMember, ProjectStatus
from app.services import project_service


def test_create_project_makes_owner(db_session, seed):
    user = seed.user("alice")
    p = project_service.create_project(db_session, user, "数仓", None)
    assert p.id is not None
    assert p.status == ProjectStatus.active
    members = db_session.scalars(
        select(ProjectMember).where(ProjectMember.project_id == p.id)
    ).all()
    assert len(members) == 1
    assert members[0].role == MemberRole.owner
    assert members[0].user_id == user.id


def test_list_my_projects_excludes_archived_by_default(db_session, seed):
    user = seed.user("alice")
    active = project_service.create_project(db_session, user, "active-proj", None)
    archived = project_service.create_project(db_session, user, "archived-proj", None)
    project_service.archive_project(db_session, archived)
    rows = project_service.list_my_projects(db_session, user, include_archived=False)
    ids = {p.id for p, _role in rows}
    assert active.id in ids
    assert archived.id not in ids


def test_list_my_projects_includes_archived_when_asked(db_session, seed):
    user = seed.user("alice")
    archived = project_service.create_project(db_session, user, "a", None)
    project_service.archive_project(db_session, archived)
    rows = project_service.list_my_projects(db_session, user, include_archived=True)
    assert archived.id in {p.id for p, _ in rows}


def test_update_project_changes_name(db_session, seed):
    user = seed.user("alice")
    p = project_service.create_project(db_session, user, "old", None)
    project_service.update_project(db_session, user, p, name="new", description="d")
    assert p.name == "new"
    assert p.description == "d"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_project_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.project_service`）

- [ ] **Step 3: 创建 `backend/app/services/project_service.py`**

```python
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MemberRole, Project, ProjectMember, ProjectStatus, User

logger = logging.getLogger("app.audit")


def create_project(db: Session, user: User, name: str, description: str | None) -> Project:
    project = Project(name=name, description=description, created_by=user.id)
    db.add(project)
    db.flush()  # 取自增 id
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=MemberRole.owner))
    db.commit()
    db.refresh(project)
    logger.info("project.create user=%s project=%s name=%s", user.id, project.id, name)
    return project


def list_my_projects(
    db: Session, user: User, include_archived: bool = False
) -> list[tuple[Project, MemberRole]]:
    stmt = (
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
    )
    if not include_archived:
        stmt = stmt.where(Project.status != ProjectStatus.archived)
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def update_project(
    db: Session,
    actor: User,
    project: Project,
    name: str | None = None,
    description: str | None = None,
) -> Project:
    changed: dict[str, list] = {}
    if name is not None and name != project.name:
        changed["name"] = [project.name, name]
        project.name = name
    if description is not None and description != project.description:
        changed["description"] = [project.description, description]
        project.description = description
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("project.update user=%s project=%s changed=%s", actor.id, project.id, changed)
    return project


def archive_project(db: Session, actor: User, project: Project) -> Project:
    project.status = ProjectStatus.archived
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("project.archive user=%s project=%s", actor.id, project.id)
    return project
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_project_service.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/project_service.py backend/tests/test_project_service.py
git commit -m "feat: 项目服务层（创建/列表/改/归档）"
```

## Task 7: 成员服务层（member_service，含边界规则）

**Files:**
- Create: `backend/app/services/member_service.py`
- Test: `backend/tests/test_member_service.py`

边界规则（spec §5.11 + 设计文档第 2 节）：
- 加成员：按 username/email 查 user（无→404）；已是成员→409；目标角色为 owner 时要求 actor 是 owner。
- 改角色：涉及 owner（目标当前是 owner，或要改成 owner）时要求 actor 是 owner；降级唯一 owner→409。
- 移除：目标是 owner→403（不能踢 owner）。

- [ ] **Step 1: 写失败测试 `backend/tests/test_member_service.py`**

```python
import pytest

from app.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.models import MemberRole
from app.services import member_service


def test_add_member_by_username(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    m = member_service.add_member(
        db_session, actor_role=MemberRole.owner, actor=owner,
        project=p, username="bob", email=None, role="editor",
    )
    assert m.user_id == bob.id
    assert m.role == MemberRole.editor


def test_add_member_unknown_user_404(db_session, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    with pytest.raises(NotFoundError):
        member_service.add_member(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, username="ghost", email=None, role="viewer",
        )


def test_add_member_duplicate_409(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    with pytest.raises(ConflictError):
        member_service.add_member(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, username="bob", email=None, role="editor",
        )


def test_admin_cannot_add_owner(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    with pytest.raises(PermissionDenied):
        member_service.add_member(
            db_session, actor_role=MemberRole.admin, actor=owner,
            project=p, username="bob", email=None, role="owner",
        )


def test_remove_owner_forbidden(db_session, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    with pytest.raises(PermissionDenied):
        member_service.remove_member(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, target_user_id=owner.id,
        )


def test_change_last_owner_conflict(db_session, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    # 仅一个 owner，降级它应 409
    with pytest.raises(ConflictError):
        member_service.change_role(
            db_session, actor_role=MemberRole.owner, actor=owner,
            project=p, target_user_id=owner.id, new_role="admin",
        )


def test_admin_cannot_change_to_owner(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "editor")
    with pytest.raises(PermissionDenied):
        member_service.change_role(
            db_session, actor_role=MemberRole.admin, actor=owner,
            project=p, target_user_id=bob.id, new_role="owner",
        )


def test_change_role_ok(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    m = member_service.change_role(
        db_session, actor_role=MemberRole.admin, actor=owner,
        project=p, target_user_id=bob.id, new_role="editor",
    )
    assert m.role == MemberRole.editor


def test_remove_member_ok(db_session, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    member_service.remove_member(
        db_session, actor_role=MemberRole.admin, actor=owner,
        project=p, target_user_id=bob.id,
    )
    remaining = {m.user_id for m in member_service.list_members(db_session, p.id)}
    assert bob.id not in remaining
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_member_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.member_service`）

- [ ] **Step 3: 创建 `backend/app/services/member_service.py`**

```python
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.models import MemberRole, Project, ProjectMember, User

logger = logging.getLogger("app.audit")


def list_members(db: Session, project_id: int) -> list[ProjectMember]:
    return list(
        db.scalars(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        ).all()
    )


def _get_membership(db: Session, project_id: int, user_id: int) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )


def _count_owners(db: Session, project_id: int) -> int:
    return len(
        [
            m
            for m in list_members(db, project_id)
            if m.role == MemberRole.owner
        ]
    )


def add_member(
    db: Session,
    *,
    actor_role: MemberRole,
    actor: User,
    project: Project,
    username: str | None,
    email: str | None,
    role: str,
) -> ProjectMember:
    new_role = MemberRole(role)
    if new_role == MemberRole.owner and actor_role != MemberRole.owner:
        raise PermissionDenied("只有 owner 能添加 owner 角色")

    stmt = select(User)
    if username:
        stmt = stmt.where(User.username == username)
    else:
        stmt = stmt.where(User.email == email)
    target = db.scalar(stmt)
    if target is None:
        raise NotFoundError("用户不存在")

    if _get_membership(db, project.id, target.id) is not None:
        raise ConflictError("该用户已是项目成员", {"user_id": target.id})

    membership = ProjectMember(project_id=project.id, user_id=target.id, role=new_role)
    db.add(membership)
    db.commit()
    db.refresh(membership)  # 取 server_default 的 joined_at
    logger.info(
        "member.add actor=%s project=%s target_user=%s role=%s",
        actor.id, project.id, target.id, new_role.value,
    )
    return membership


def change_role(
    db: Session,
    *,
    actor_role: MemberRole,
    actor: User,
    project: Project,
    target_user_id: int,
    new_role: str,
) -> ProjectMember:
    role = MemberRole(new_role)
    membership = _get_membership(db, project.id, target_user_id)
    if membership is None:
        raise NotFoundError("成员不存在")

    involves_owner = membership.role == MemberRole.owner or role == MemberRole.owner
    if involves_owner and actor_role != MemberRole.owner:
        raise PermissionDenied("只有 owner 能变更 owner 角色")

    if (
        membership.role == MemberRole.owner
        and role != MemberRole.owner
        and _count_owners(db, project.id) <= 1
    ):
        raise ConflictError("不能降级项目唯一的 owner")

    old = membership.role.value
    membership.role = role
    db.add(membership)
    db.commit()
    logger.info(
        "member.update_role actor=%s project=%s target_user=%s role=%s->%s",
        actor.id, project.id, target_user_id, old, role.value,
    )
    return membership


def remove_member(
    db: Session,
    *,
    actor_role: MemberRole,
    actor: User,
    project: Project,
    target_user_id: int,
) -> None:
    membership = _get_membership(db, project.id, target_user_id)
    if membership is None:
        raise NotFoundError("成员不存在")
    if membership.role == MemberRole.owner:
        raise PermissionDenied("不能移除 owner")
    db.delete(membership)
    db.commit()
    logger.info(
        "member.remove actor=%s project=%s target_user=%s",
        actor.id, project.id, target_user_id,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_member_service.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/member_service.py backend/tests/test_member_service.py
git commit -m "feat: 成员服务层（增删改 + owner 边界规则）"
```

## Task 8: 项目路由 + 集成测试

**Files:**
- Create: `backend/app/routers/projects.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_project_api.py`

- [ ] **Step 1: 创建 `backend/app/routers/projects.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.deps import CurrentUser, DbSession, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.project import (
    CreateProjectRequest,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.services import project_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _to_response(project, role: MemberRole) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        my_role=role.value,
    )


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    user: CurrentUser,
    db: DbSession,
    include_archived: Annotated[bool, Query()] = False,
) -> list[ProjectResponse]:
    rows = project_service.list_my_projects(db, user, include_archived=include_archived)
    return [_to_response(p, role) for p, role in rows]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: CreateProjectRequest, user: CurrentUser, db: DbSession) -> ProjectResponse:
    project = project_service.create_project(db, user, payload.name, payload.description)
    return _to_response(project, MemberRole.owner)


@router.get("/{pid}", response_model=ProjectResponse)
def get_project(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
) -> ProjectResponse:
    return _to_response(ctx.project, ctx.membership.role)


@router.patch("/{pid}", response_model=ProjectResponse)
def update_project(
    payload: UpdateProjectRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    db: DbSession,
) -> ProjectResponse:
    project = project_service.update_project(
        db, ctx.user, ctx.project, name=payload.name, description=payload.description
    )
    return _to_response(project, ctx.membership.role)


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def archive_project(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.owner))],
    db: DbSession,
) -> None:
    project_service.archive_project(db, ctx.user, ctx.project)
    return None
```

- [ ] **Step 2: 修改 `backend/app/main.py` 注册路由**

在 `from app.routers import auth as auth_router` 之后、`app.include_router(auth_router.router)` 之后追加：
```python
    from app.routers import projects as projects_router

    app.include_router(projects_router.router)
```

- [ ] **Step 3: 写集成测试 `backend/tests/test_project_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_create_project_makes_owner(client, seed):
    alice = seed.user("alice")
    r = client.post("/api/v1/projects", json={"name": "数仓"}, headers=_auth(seed, alice))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "数仓"
    assert body["my_role"] == "owner"
    assert body["status"] == "active"


def test_list_only_my_projects(client, seed):
    alice = seed.user("alice")
    bob = seed.user("bob")
    seed.project(alice, name="a-proj")
    seed.project(bob, name="b-proj")
    r = client.get("/api/v1/projects", headers=_auth(seed, alice))
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert names == {"a-proj"}


def test_list_excludes_archived(client, seed):
    alice = seed.user("alice")
    p = seed.project(alice, name="archived", status="archived")
    r = client.get("/api/v1/projects", headers=_auth(seed, alice))
    assert all(item["id"] != p.id for item in r.json())
    r2 = client.get("/api/v1/projects?include_archived=true", headers=_auth(seed, alice))
    assert any(item["id"] == p.id for item in r2.json())


def test_update_project_requires_admin(client, seed):
    alice = seed.user("alice")
    viewer = seed.user("viewer")
    p = seed.project(alice)
    seed.member(p, viewer, "viewer")
    r = client.patch(
        f"/api/v1/projects/{p.id}", json={"name": "new"}, headers=_auth(seed, viewer)
    )
    assert r.status_code == 403


def test_archive_owner_only(client, seed):
    alice = seed.user("alice")
    admin = seed.user("admin")
    p = seed.project(alice)
    seed.member(p, admin, "admin")
    r = client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, admin))
    assert r.status_code == 403
    r2 = client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, alice))
    assert r2.status_code == 204


def test_non_member_403(client, seed):
    alice = seed.user("alice")
    stranger = seed.user("stranger")
    p = seed.project(alice)
    r = client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, stranger))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PERMISSION_DENIED"


def test_get_missing_project_404(client, seed):
    alice = seed.user("alice")
    r = client.get("/api/v1/projects/999999", headers=_auth(seed, alice))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_project_api.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/projects.py backend/app/main.py backend/tests/test_project_api.py
git commit -m "feat: 项目路由 CRUD 与集成测试"
```

## Task 9: 成员路由 + 集成测试

**Files:**
- Create: `backend/app/routers/members.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_member_api.py`

- [ ] **Step 1: 创建 `backend/app/routers/members.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.deps import DbSession, ProjectContext, require_role
from app.models import MemberRole, User
from app.schemas.project import AddMemberRequest, ChangeRoleRequest, MemberResponse
from app.services import member_service

router = APIRouter(prefix="/api/v1/projects/{pid}/members", tags=["members"])


def _to_member_response(db, membership) -> MemberResponse:
    user = db.scalar(select(User).where(User.id == membership.user_id))
    return MemberResponse(
        user_id=membership.user_id,
        username=user.username,
        display_name=user.display_name,
        role=membership.role.value,
        joined_at=membership.joined_at,
    )


@router.get("", response_model=list[MemberResponse])
def list_members(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    db: DbSession,
) -> list[MemberResponse]:
    members = member_service.list_members(db, ctx.project.id)
    return [_to_member_response(db, m) for m in members]


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: AddMemberRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    db: DbSession,
) -> MemberResponse:
    membership = member_service.add_member(
        db,
        actor_role=ctx.membership.role,
        actor=ctx.user,
        project=ctx.project,
        username=payload.username,
        email=payload.email,
        role=payload.role,
    )
    return _to_member_response(db, membership)


@router.patch("/{uid}", response_model=MemberResponse)
def change_role(
    uid: int,
    payload: ChangeRoleRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    db: DbSession,
) -> MemberResponse:
    membership = member_service.change_role(
        db,
        actor_role=ctx.membership.role,
        actor=ctx.user,
        project=ctx.project,
        target_user_id=uid,
        new_role=payload.role,
    )
    return _to_member_response(db, membership)


@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    uid: int,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    db: DbSession,
) -> None:
    member_service.remove_member(
        db,
        actor_role=ctx.membership.role,
        actor=ctx.user,
        project=ctx.project,
        target_user_id=uid,
    )
    return None
```

> 注：路径前缀含 `{pid}`，`require_role` 依赖通过 `Path()` 读取同名 `pid`，与 projects 路由一致。

- [ ] **Step 2: 修改 `backend/app/main.py` 注册成员路由**

在 Task 8 的 `app.include_router(projects_router.router)` 之后追加：
```python
    from app.routers import members as members_router

    app.include_router(members_router.router)
```

- [ ] **Step 3: 写集成测试 `backend/tests/test_member_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_add_member_by_username(client, seed):
    owner = seed.user("owner")
    seed.user("bob")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "bob", "role": "editor"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 201
    assert r.json()["username"] == "bob"
    assert r.json()["role"] == "editor"


def test_add_member_by_email(client, seed):
    owner = seed.user("owner")
    seed.user("bob", email="bob@corp.com")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"email": "bob@corp.com", "role": "viewer"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 201
    assert r.json()["user_id"] is not None


def test_add_member_unknown_404(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "ghost", "role": "viewer"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 404


def test_add_member_duplicate_409(client, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "bob", "role": "editor"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 409


def test_change_role(client, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    r = client.patch(
        f"/api/v1/projects/{p.id}/members/{bob.id}",
        json={"role": "editor"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 200
    assert r.json()["role"] == "editor"


def test_cannot_demote_last_owner(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.patch(
        f"/api/v1/projects/{p.id}/members/{owner.id}",
        json={"role": "admin"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 409


def test_admin_cannot_promote_to_owner(client, seed):
    owner = seed.user("owner")
    admin = seed.user("admin")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, admin, "admin")
    seed.member(p, bob, "editor")
    r = client.patch(
        f"/api/v1/projects/{p.id}/members/{bob.id}",
        json={"role": "owner"},
        headers=_auth(seed, admin),
    )
    assert r.status_code == 403


def test_cannot_remove_owner(client, seed):
    owner = seed.user("owner")
    admin = seed.user("admin")
    p = seed.project(owner)
    seed.member(p, admin, "admin")
    r = client.delete(
        f"/api/v1/projects/{p.id}/members/{owner.id}",
        headers=_auth(seed, admin),
    )
    assert r.status_code == 403


def test_remove_member_ok(client, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    r = client.delete(
        f"/api/v1/projects/{p.id}/members/{bob.id}",
        headers=_auth(seed, owner),
    )
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/projects/{p.id}/members", headers=_auth(seed, owner))
    assert all(m["user_id"] != bob.id for m in r2.json())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_member_api.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/members.py backend/app/main.py backend/tests/test_member_api.py
git commit -m "feat: 成员路由 CRUD 与集成测试"
```

## Task 10: 权限矩阵参数化测试 + 全量回归

**Files:**
- Create: `backend/tests/test_permission_matrix.py`

覆盖 spec §5.11：每个角色对每个写端点的允许/拒绝。

- [ ] **Step 1: 写 `backend/tests/test_permission_matrix.py`**

```python
import pytest


def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


# (角色, 改项目 PATCH, 管成员 POST, 删项目 DELETE) 期望状态码
# 改项目/管成员需 admin+；删项目需 owner
MATRIX = [
    ("owner", 200, 201, 204),
    ("admin", 200, 201, 403),
    ("editor", 403, 403, 403),
    ("viewer", 403, 403, 403),
]


@pytest.mark.parametrize("role,patch_code,member_code,delete_code", MATRIX)
def test_write_endpoints_by_role(client, seed, role, patch_code, member_code, delete_code):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    seed.user("newbie")
    p = seed.project(owner)
    if role != "owner":
        seed.member(p, actor, role)
        caller = actor
    else:
        caller = owner

    # 改项目
    r = client.patch(
        f"/api/v1/projects/{p.id}", json={"name": "x"}, headers=_auth(seed, caller)
    )
    assert r.status_code == patch_code

    # 管成员（添加 newbie）
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "newbie", "role": "viewer"},
        headers=_auth(seed, caller),
    )
    assert r.status_code == member_code

    # 删项目
    r = client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, caller))
    assert r.status_code == delete_code


@pytest.mark.parametrize("role", ["owner", "admin", "editor", "viewer"])
def test_read_endpoints_allow_all_members(client, seed, role):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    if role != "owner":
        seed.member(p, actor, role)
        caller = actor
    else:
        caller = owner
    r = client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, caller))
    assert r.status_code == 200
    r = client.get(f"/api/v1/projects/{p.id}/members", headers=_auth(seed, caller))
    assert r.status_code == 200
```

- [ ] **Step 2: 运行该测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_permission_matrix.py -v`
Expected: PASS（4 + 4 = 8 passed）

- [ ] **Step 3: 运行全量测试确认无回归**

Run: `cd backend && . .venv/bin/activate && pytest -v`
Expected: 全绿（Phase 1 + Phase 2 所有测试）。

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_permission_matrix.py
git commit -m "test: 权限矩阵参数化覆盖（角色 × 端点）"
```

## Phase 2 完成标准（Definition of Done）

- [ ] `pytest -v` 全绿（Phase 1 既有 + Phase 2 新增，无回归）。
- [ ] `alembic upgrade head` 在真实 MySQL 上建出 `projects` + `project_members` 表（Task 2 已手动验证）。
- [ ] 完整流程可走通：登录 → `POST /projects`（自动 owner）→ `POST /members` 加成员 → `PATCH /members/:uid` 改角色 → `GET /projects` 列出 → `DELETE /projects/:pid` 归档。
- [ ] 各端点权限符合 spec §5.11 权限矩阵（`test_permission_matrix.py` 覆盖）。
- [ ] 错误响应符合 spec §8 信封（404/403/409/422）。
- [ ] owner 边界：不能踢 owner、不能降级唯一 owner、admin 不能动 owner 角色。

## 下一阶段预告（不在本计划内）

Phase 3：Neo4j 图数据模型、节点/边 CRUD、节点类型 schema，以及删项目的 `deleting` 状态机 + 后台清理。将复用本阶段的 `require_role`、`ProjectContext`。
