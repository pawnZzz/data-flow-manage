# 任务血缘工具 Phase 2：项目 + 成员 + RBAC — 设计文档

**日期：** 2026-06-08
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§3 架构、§4.1 数据模型、§5.2 项目和成员、§5.11 权限矩阵、§8 错误处理、§9 测试）

## 目标

在 Phase 1（认证）之上实现项目工作区与成员管理：项目的增删改查（删=软归档）、成员的增删改与角色管理，以及统一的基于角色的访问控制（RBAC）。本阶段纯 MySQL，不触及 Neo4j 图数据（节点/边留到 Phase 3）。

## 范围

**做：**
- `projects`、`project_members` 两张 MySQL 表 + Alembic 迁移。
- 项目 CRUD：列表（我加入的）、创建（创建者自动 owner）、详情、修改、归档。
- 成员管理：列表、添加（按 username/email）、改角色、移除。
- `require_role(min_role)` 依赖工厂，统一 RBAC 强制点（spec §5.11"不散落到业务代码"）。
- 写操作用 Python `logging` 打结构化操作日志。

**不做（YAGNI / 留待后续阶段）：**
- 审计日志落库（`audit_logs` 表、读接口）——本阶段仅 `logging` 打印。
- 删项目的 `deleting` 状态机与 Neo4j 后台清理——本阶段 DELETE 仅软归档为 `archived`，Neo4j 清理留到 Phase 3 有图数据后。
- 节点 / 边 / schema / 图查询（Phase 3+）。
- 用户搜索接口、X-Forwarded-For 真实 IP 解析（部署阶段）。

## 复用 Phase 1

- `AppError` 体系（`NotFoundError` / `ConflictError` / `PermissionDenied` / `AuthError`）与 §8 错误信封。
- `get_current_user` / `CurrentUser` / `DbSession` 依赖（`app/deps.py`）。
- 分层结构 routers → services → models；ORM ENUM 写法（`UserStatus`）。
- testcontainers MySQL fixture（`tests/conftest.py`）。

## 架构决策

采用**依赖注入式 RBAC + 服务层操作日志**（方案 A）：

- 权限校验集中在 `require_role(min_role)` FastAPI 依赖工厂里，路由通过 `Depends` 声明所需最小角色，业务代码零权限判断。
- 写操作在 service 层成功后用 `logging` 记一行结构化日志。
- 备选方案 B（中间件 RBAC + 装饰器日志）因难以表达按端点差异化的 min_role、且中间件内开 db session 不自然而否决；方案 C（业务代码内手动检查）因与 §5.11"统一、不散落"冲突而否决。

---

## 1. 数据模型

新增两张 MySQL 表，对应 spec §4.1，迁移文件 `migrations/versions/0002_create_projects_members.py`。

### projects

| 列 | 类型 | 约束 |
|---|---|---|
| id | BIGINT | PK, AUTO_INCREMENT |
| name | VARCHAR(128) | NOT NULL |
| description | TEXT | 可空 |
| status | ENUM(active, archived, deleting) | NOT NULL, 默认 active |
| created_by | BIGINT | NOT NULL, FK→users.id |
| created_at | DATETIME | server_default now() |
| updated_at | DATETIME | server_default now(), onupdate now() |

索引：`INDEX idx_status (status)`。

> `deleting` 状态值在本阶段建出但不使用（DELETE 只置 `archived`），为 Phase 3 的跨库清理状态机预留。

### project_members

| 列 | 类型 | 约束 |
|---|---|---|
| project_id | BIGINT | NOT NULL, FK→projects.id ON DELETE CASCADE |
| user_id | BIGINT | NOT NULL, FK→users.id ON DELETE CASCADE |
| role | ENUM(owner, admin, editor, viewer) | NOT NULL |
| joined_at | DATETIME | server_default now() |

主键：复合 `(project_id, user_id)`（保证一个用户在同项目内只有一个角色）。索引：`INDEX idx_user (user_id)`。

### ORM 落地细节

- ENUM 用 Python `enum.Enum`，沿用 Phase 1 `UserStatus` 写法：`ProjectStatus`（active/archived/deleting）、`MemberRole`（owner/admin/editor/viewer）。
- `MemberRole` 附带等级映射用于权限比较，**不入库**（库里只存字符串值）：

  ```
  viewer=0 < editor=1 < admin=2 < owner=3
  ```

  实现为枚举上的 `level` 属性（按固定 dict 映射），供 `require_role` 比较。
- 模型放 `app/models/project.py`（`Project`、`ProjectMember`），在 `app/models/__init__.py` 导出以注册到 metadata。
- 软归档：归档只改 `status`，行不删；`ON DELETE CASCADE` 为将来真正硬删时服务。

---

## 2. RBAC 强制点

在 `app/deps.py` 扩展。核心是 `require_role(min_role)` 依赖工厂。

### ProjectContext

轻量 dataclass，把鉴权结果打包注入路由，避免业务代码重复查库：

```python
@dataclass
class ProjectContext:
    project: Project
    membership: ProjectMember
    user: User
```

### require_role(min_role)

```python
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
        return ProjectContext(project, membership, user)
    return dep
```

路由用法：`ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))]`。

### 边界规则

- **读项目**（GET 详情 / 成员列表）：`require_role(viewer)`——任何成员可读，非成员 403。
- **改项目 / 管成员**：`require_role(admin)`。
- **归档项目**：`require_role(owner)`。
- **涉及 owner 角色的变更必须由 owner 执行**：admin 只能在 editor/viewer 之间改；把成员提升到 owner、或改动现有 owner 的角色，需调用者本人是 owner。
- **最后一个 owner 保护**：不能移除或降级项目中唯一的 owner（否则项目失去管理者）→ 409。
- **不能踢 owner**（spec §5.2 明示）：DELETE 成员目标为 owner 直接拒 403。
- **`GET /projects`、`POST /projects` 不经过 `require_role`**：前者按 membership 过滤当前用户加入的项目；后者只需登录，创建后调用者自动成为 owner。

---

## 3. API 端点与权限映射

路由文件：`app/routers/projects.py`、`app/routers/members.py`，全部 `/api/v1` 前缀。

| 方法 路径 | 权限 | 服务 | 日志 action / target |
|---|---|---|---|
| `GET /projects` | 仅登录 | `list_my_projects(user, include_archived=False)` | — |
| `POST /projects` | 仅登录 | `create_project(user, name, desc)` | `project.create` / project |
| `GET /projects/:pid` | `require_role(viewer)` | ctx.project | — |
| `PATCH /projects/:pid` | `require_role(admin)` | `update_project(...)` | `project.update` / project |
| `DELETE /projects/:pid` | `require_role(owner)` | `archive_project(...)` | `project.archive` / project |
| `GET /projects/:pid/members` | `require_role(viewer)` | `list_members(pid)` | — |
| `POST /projects/:pid/members` | `require_role(admin)` | `add_member(pid, username/email, role)` | `member.add` / member |
| `PATCH /projects/:pid/members/:uid` | `require_role(admin)` | `change_role(...)` | `member.update_role` / member |
| `DELETE /projects/:pid/members/:uid` | `require_role(admin)` | `remove_member(...)` | `member.remove` / member |

### 关键流程

- **列出我的项目**：`GET /projects` 默认只返回 `status != archived` 的项目（`include_archived=False`）；带 `?include_archived=true` 时一并返回归档项目，供前端"归档"视图使用。
- **创建项目**：一个事务内插 `projects` 行 → `flush()` 取 id → 插 `project_members(role=owner)` → `commit()` → 打 `project.create` 日志。
- **添加成员**：按 `username` 或 `email` 查 `User`（无则 404）；已是成员则 409；涉及 owner 角色时校验调用者是否 owner；插 membership → commit → 打日志。
- **改成员角色 / 移除成员**：套用第 2 节边界（唯一 owner 保护、不能踢 owner、涉 owner 需 owner）。移除是真删 membership 行。
- **归档项目**：`status` 置 `archived`，commit，打 `project.archive` 日志。

### 请求 / 响应 schema（`app/schemas/project.py`）

- `CreateProjectRequest`：`name`（1–128 非空）、`description`（可空）。
- `UpdateProjectRequest`：`name?`、`description?`。
- `ProjectResponse`：id, name, description, status, created_by, created_at, updated_at, my_role（当前用户在该项目的角色，便于前端控件显隐）。
- `AddMemberRequest`：`username` 或 `email`（二选一，至少一个）、`role`（owner/admin/editor/viewer）。
- `ChangeRoleRequest`：`role`。
- `MemberResponse`：user_id, username, display_name, role, joined_at。

---

## 4. 操作日志

写操作不落库，用标准库 `logging`：

- 模块级 logger：`logger = logging.getLogger("app.audit")`，便于将来单独配 handler / 升级为落库。
- 每个写操作成功后（commit 之后）打一行结构化日志：

  ```python
  logger.info("project.create user=%s project=%s name=%s", user.id, project.id, name)
  logger.info("project.update user=%s project=%s changed=%s", user.id, pid, changed)
  logger.info("project.archive user=%s project=%s", user.id, pid)
  logger.info("member.add actor=%s project=%s target_user=%s role=%s", actor.id, pid, uid, role)
  logger.info("member.update_role actor=%s project=%s target_user=%s role=%s->%s", ...)
  logger.info("member.remove actor=%s project=%s target_user=%s", actor.id, pid, uid)
  ```

- 不碰事务、不加表、不加读接口。日志走 stdout（uvicorn 默认捕获），契合内网单实例部署。

---

## 5. 错误处理与测试

### 错误处理（复用 Phase 1 `AppError` + §8 信封）

| 场景 | 异常 → HTTP |
|---|---|
| 项目不存在 | `NotFoundError` → 404 |
| 非项目成员访问 | `PermissionDenied` → 403 |
| 角色不足 | `PermissionDenied` → 403 |
| 加成员时用户不存在 | `NotFoundError` → 404 |
| 重复加成员 | `ConflictError` → 409 |
| 移除 / 降级唯一 owner | `ConflictError` → 409 |
| 踢 owner | `PermissionDenied` → 403 |
| 非 owner 操作 owner 角色 | `PermissionDenied` → 403 |
| 请求体校验失败 | Pydantic → 422（Phase 1 信封已覆盖）|

### 测试（testcontainers MySQL，沿用 Phase 1 conftest）

- `tests/test_deps.py`：`require_role` 单元——各角色对各 min_role 的放行 / 拒绝、非成员、项目不存在。
- `tests/test_project_api.py`：建项目→自动 owner、列表只见自己加入的、改项目 admin+、归档 owner-only、非成员 403、改 / 归档不存在项目 404。
- `tests/test_member_api.py`：加成员（用 username）、用 email 加、重复 409、用户不存在 404、改角色、唯一 owner 保护 409、踢 owner 403、admin 不能动 owner 角色、移除成员。
- 权限矩阵覆盖：参数化测每个角色 × 每个写端点的允许 / 拒绝（spec §9）。
- conftest 补充：建多用户 helper、给项目造不同角色成员的 fixture。

## Definition of Done

- `pytest -v` 全绿（含 Phase 1 既有测试，无回归）。
- `alembic upgrade head` 在真实 MySQL 上建出 `projects` + `project_members` 表。
- 可完成：登录 → 建项目（自动 owner）→ 加成员 → 改角色 → 列出我的项目 → 归档项目 的完整流程。
- 各端点权限符合 spec §5.11 权限矩阵。
- 错误响应符合 spec §8 信封结构。

## 下一阶段预告（不在本计划内）

Phase 3：Neo4j 图数据模型、节点 / 边 CRUD、节点类型 schema，以及删项目的 `deleting` 状态机 + 后台清理。将复用本阶段的 `require_role`、`ProjectContext`。

