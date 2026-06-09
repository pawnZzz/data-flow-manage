# 任务血缘工具 Phase 3E：删项目跨库清理 + 归档写守卫 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐删项目跨库一致性闭环（archive/unarchive/purge 状态机 + 同步 Neo4j 清理）与归档项目写守卫。

**Architecture:** `require_role` 加 `require_active` 参数统一拦截非活动项目的写操作；purge 同步编排（标 deleting → DETACH DELETE Neo4j → 删 MySQL），失败停在 deleting 可重跑。沿用既有 routers→services→cypher 分层。

**Tech Stack:** Python 3.10+、FastAPI、SQLAlchemy、Pydantic v2、neo4j、pytest、testcontainers。

参考 spec：`docs/superpowers/specs/2026-06-09-phase3e-project-deletion-write-guard-design.md`。

---

## File Structure

- `backend/app/deps.py` — 改：`require_role(min_role, require_active=False)` + 409 守卫；import ConflictError、ProjectStatus。
- `backend/app/routers/{nodes,edges,schemas,members,sql_import,projects}.py` — 改：写端点加 `require_active=True`。
- `backend/app/cypher/projects.py` — 新建：`PURGE_NODES`、`PURGE_SCHEMAS`。
- `backend/app/schemas/project.py` — 改：加 `PurgeResponse`。
- `backend/app/services/project_service.py` — 改：加 `unarchive_project`、`purge_project`；`list_my_projects` 默认只显示 active。
- `backend/app/routers/projects.py` — 改：加 `POST /unarchive`、`POST /purge`。
- `backend/tests/test_archived_write_guard.py` — 新建。
- `backend/tests/test_project_lifecycle.py` — 新建。

约定：命令在 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/backend && . .venv/bin/activate` 下跑；commit 在仓库根，message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## Task 1: 归档写守卫（require_active）

**Files:**
- Modify: `backend/app/deps.py`
- Modify: `backend/app/routers/nodes.py`, `edges.py`, `schemas.py`, `members.py`, `sql_import.py`, `projects.py`
- Test: `backend/tests/test_archived_write_guard.py`

- [ ] **Step 1: 改 `backend/app/deps.py` 顶部 import**

把 `from app.exceptions import AuthError, NotFoundError, PermissionDenied` 改为：
```python
from app.exceptions import AuthError, ConflictError, NotFoundError, PermissionDenied
```
把 `from app.models import MemberRole, Project, ProjectMember, User` 改为：
```python
from app.models import MemberRole, Project, ProjectMember, ProjectStatus, User
```

- [ ] **Step 2: 改 `require_role` 加 require_active 参数**

把现有 `require_role` 整个函数替换为：
```python
def require_role(
    min_role: MemberRole, require_active: bool = False
) -> Callable[..., "ProjectContext"]:
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
        if require_active and project.status != ProjectStatus.active:
            raise ConflictError("项目非活动状态，禁止写入", {"code": "PROJECT_NOT_ACTIVE"})
        return ProjectContext(project=project, membership=membership, user=user)

    return dep
```

- [ ] **Step 3: 写失败测试 `backend/tests/test_archived_write_guard.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _archived_project_with_schema(client, seed):
    """建项目 + schema + 两节点（趁 active），再归档，返回 (owner, p, a, b)。"""
    owner = seed.user("owner")
    p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    a = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    b = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "b", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))  # → archived
    return owner, p, a, b


def test_archived_blocks_node_create(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "c", "type": "t"},
                    headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ACTIVE"


def test_archived_blocks_edge_create(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b}, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_schema_create(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": "t2", "display_name": "T2", "fields": []},
                    headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_sql_import(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                    json={"tables": [], "dependencies": []}, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_rename(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.patch(f"/api/v1/projects/{p.id}", json={"name": "new"},
                     headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_add_member(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    other = seed.user("other")
    r = client.post(f"/api/v1/projects/{p.id}/members",
                    json={"username": "other", "role": "viewer"}, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_still_allows_reads(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    assert client.get(f"/api/v1/projects/{p.id}/nodes",
                      headers=_auth(seed, owner)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/edges",
                      headers=_auth(seed, owner)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/schemas",
                      headers=_auth(seed, owner)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/graph",
                      headers=_auth(seed, owner)).status_code == 200
```

> 注：`AddMemberRequest` 的字段名以现有 `app/schemas/project.py` 为准（应为 `username`+`role`）。实现时如字段名不同，按实际调整测试 body。

- [ ] **Step 4: 运行确认失败**

Run: `pytest tests/test_archived_write_guard.py -q`
Expected: 写守卫测试 FAIL（目前归档项目仍可写，返回 2xx 而非 409）；读测试已 PASS。

- [ ] **Step 5: 给写端点加 require_active=True**

逐文件把指定行的 `require_role(MemberRole.X)` 改为 `require_role(MemberRole.X, require_active=True)`：

- `nodes.py`：第 43、62、73、84、94 行（create_node、update_node、delete_node、set_parent、clear_parent —— 全是 `MemberRole.editor`）。**不改** list/get/children/descendants/upstream/downstream/impact（viewer 读）。
- `edges.py`：第 33、52、63 行（create/update/delete edge，`editor`）。不改 list/get。
- `schemas.py`：第 24、46、58 行（create=editor、update=editor、delete=admin）。不改第 15、36（viewer 读）。
- `members.py`：第 40、59、76 行（add/change/remove，`admin`）。不改第 30（viewer 读）。
- `sql_import.py`：第 21、30 行（preview、commit，`editor`）。
- `projects.py`：把 PATCH `update_project` 的 `require_role(MemberRole.admin)` 改为 `require_role(MemberRole.admin, require_active=True)`。**不改** DELETE（archive，lifecycle）。

> 行号以当前代码为准；若已偏移，按函数名定位对应 `require_role(...)`。

- [ ] **Step 6: 运行确认通过**

Run: `pytest tests/test_archived_write_guard.py -q`
Expected: 全 PASS（7 个）。

- [ ] **Step 7: 全量回归（确认未拦到正常 active 写）**

Run: `pytest -q 2>&1 | tail -3`
Expected: 全绿（既有节点/边/schema/SQL/成员测试都在 active 项目上操作，不受影响）。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/deps.py backend/app/routers/nodes.py backend/app/routers/edges.py backend/app/routers/schemas.py backend/app/routers/members.py backend/app/routers/sql_import.py backend/app/routers/projects.py backend/tests/test_archived_write_guard.py
git commit -m "feat: 归档/删除中项目写守卫（require_role require_active → 409 PROJECT_NOT_ACTIVE）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 2: 生命周期（unarchive / purge）+ 列表过滤

**Files:**
- Create: `backend/app/cypher/projects.py`
- Modify: `backend/app/schemas/project.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/routers/projects.py`
- Test: `backend/tests/test_project_lifecycle.py`

- [ ] **Step 1: 创建 `backend/app/cypher/projects.py`**

```python
PURGE_NODES = """
MATCH (n:LineageNode {project_id: $pid})
DETACH DELETE n
RETURN count(n) AS deleted_nodes
"""

PURGE_SCHEMAS = """
MATCH (s:NodeTypeSchema {project_id: $pid})
DELETE s
RETURN count(s) AS deleted_schemas
"""
```

- [ ] **Step 2: 加 `PurgeResponse` 到 `backend/app/schemas/project.py`**

在文件末尾追加：
```python
class PurgeResponse(BaseModel):
    deleted_nodes: int
    deleted_schemas: int
```

- [ ] **Step 3: 改 `backend/app/services/project_service.py`**

顶部 import 区加：
```python
from app.cypher import projects as pq
from app.exceptions import ConflictError
from app.repositories.graph_repo import GraphRepo
```
（`ProjectMember` 已在现有 `from app.models import ...` 中；确认包含，否则补上。）

把 `list_my_projects` 的过滤段：
```python
    if not include_archived:
        stmt = stmt.where(Project.status != ProjectStatus.archived)
```
改为：
```python
    if include_archived:
        stmt = stmt.where(Project.status != ProjectStatus.deleting)  # 归档可见，删除中永不列出
    else:
        stmt = stmt.where(Project.status == ProjectStatus.active)
```

在文件末尾追加两个函数：
```python
def unarchive_project(db: Session, actor: User, project: Project) -> Project:
    if project.status != ProjectStatus.archived:
        raise ConflictError("仅归档项目可恢复", {"code": "PROJECT_NOT_ARCHIVED"})
    project.status = ProjectStatus.active
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("project.unarchive user=%s project=%s", actor.id, project.id)
    return project


def purge_project(db: Session, repo: GraphRepo, actor: User, project: Project) -> dict:
    if project.status == ProjectStatus.active:
        raise ConflictError("项目须先归档才能永久删除", {"code": "PROJECT_NOT_ARCHIVED"})
    project.status = ProjectStatus.deleting
    db.add(project)
    db.commit()  # 崩溃也停在 deleting，可重跑
    pid = project.id
    deleted_nodes = repo.run_write(pq.PURGE_NODES, pid=pid)[0]["deleted_nodes"]
    deleted_schemas = repo.run_write(pq.PURGE_SCHEMAS, pid=pid)[0]["deleted_schemas"]
    db.query(ProjectMember).filter(ProjectMember.project_id == pid).delete()
    db.delete(project)
    db.commit()
    logger.info("project.purge user=%s project=%s nodes=%s schemas=%s",
                actor.id, pid, deleted_nodes, deleted_schemas)
    return {"deleted_nodes": deleted_nodes, "deleted_schemas": deleted_schemas}
```

- [ ] **Step 4: 改 `backend/app/routers/projects.py`**

顶部 import：把 `from app.deps import CurrentUser, DbSession, ProjectContext, require_role` 改为加 `GraphRepoDep`：
```python
from app.deps import CurrentUser, DbSession, GraphRepoDep, ProjectContext, require_role
```
`from app.schemas.project import (...)` 块里加 `PurgeResponse`。

在 archive 端点（DELETE）之后追加：
```python
@router.post("/{pid}/unarchive", response_model=ProjectResponse)
def unarchive_project(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.owner))],
    db: DbSession,
) -> ProjectResponse:
    project = project_service.unarchive_project(db, ctx.user, ctx.project)
    return _to_response(project, ctx.membership.role)


@router.post("/{pid}/purge", response_model=PurgeResponse)
def purge_project(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.owner))],
    db: DbSession,
    repo: GraphRepoDep,
) -> PurgeResponse:
    return project_service.purge_project(db, repo, ctx.user, ctx.project)
```

- [ ] **Step 5: 写测试 `backend/tests/test_project_lifecycle.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_archive_then_unarchive_roundtrip(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    assert client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner)).status_code == 204
    r = client.post(f"/api/v1/projects/{p.id}/unarchive", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    # 恢复后可正常写
    assert client.post(f"/api/v1/projects/{p.id}/schemas",
                       json={"type_key": "t", "display_name": "T", "fields": []},
                       headers=_auth(seed, owner)).status_code == 201


def test_unarchive_non_archived_409(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)  # active
    r = client.post(f"/api/v1/projects/{p.id}/unarchive", headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ARCHIVED"


def test_purge_active_requires_archived_first(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)  # active
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ARCHIVED"


def test_purge_cleans_neo4j_and_mysql(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    a = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    b = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "b", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": a, "target_id": b}, headers=_auth(seed, owner))
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))  # archive
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_nodes"] == 2
    assert body["deleted_schemas"] == 1
    # MySQL 记录已删 → 404
    assert client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner)).status_code == 404


def test_purge_requires_owner(client, seed):
    owner = seed.user("owner"); admin = seed.user("admin")
    p = seed.project(owner); seed.member(p, admin, "admin")
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))  # archive
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, admin))
    assert r.status_code == 403


def test_purge_retries_from_deleting(client, seed):
    # 模拟上次清理中断：项目处于 deleting + Neo4j 还有节点
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                headers=_auth(seed, owner))
    seed.set_status(p, "deleting")  # 直接置 deleting（见 conftest seed 扩展）
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["deleted_nodes"] == 1
    assert client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner)).status_code == 404


def test_deleting_hidden_from_list(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    seed.set_status(p, "deleting")
    r = client.get("/api/v1/projects?include_archived=true", headers=_auth(seed, owner))
    assert all(row["id"] != p.id for row in r.json())
```

- [ ] **Step 6: 扩展 `backend/tests/conftest.py` 的 `seed` helper 加 `set_status`**

在 `seed` fixture 的 `Seed` 类里（与 `member`/`token` 并列）加方法：
```python
        def set_status(self, project, status):
            from app.models import ProjectStatus
            obj = s.get(Project, project.id)
            obj.status = ProjectStatus(status)
            s.commit()
```

- [ ] **Step 7: 运行确认通过**

Run: `pytest tests/test_project_lifecycle.py -q`
Expected: 7 passed。

- [ ] **Step 8: 全量回归**

Run: `pytest -q 2>&1 | tail -3`
Expected: 全绿（Phase 1+2+3A+3B+3C+3E）。

- [ ] **Step 9: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher/projects.py backend/app/schemas/project.py backend/app/services/project_service.py backend/app/routers/projects.py backend/tests/test_project_lifecycle.py backend/tests/conftest.py
git commit -m "feat: 项目 unarchive/purge 生命周期与跨库同步清理

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Phase 3E 完成标准（Definition of Done）

- [ ] 全量 `pytest` 绿（Phase 1+2+3A+3B+3C+3E，无回归）。
- [ ] 状态机往返：active↔archived（archive/unarchive）、archived→deleting→删除（purge）。
- [ ] purge 真清 Neo4j（DETACH DELETE 节点/边 + schema）+ 删 MySQL（项目+成员），deleting 入口可重跑。
- [ ] 写守卫覆盖全部写端点（节点/边/schema/SQL导入/改名/成员），读端点 + lifecycle 动作不受影响。
- [ ] 错误符合 §8（409 PROJECT_NOT_ACTIVE / PROJECT_NOT_ARCHIVED、403、404）。
- [ ] deleting 项目不出现在项目列表。
- [ ] 实现后更新记忆 `phase3-archived-project-write-guard` 为已完成。

## 下一阶段预告（不在本计划内）

- 前端：Vue3 + Pinia + AntV X6 画布、属性面板、影响分析、SQL 导入入口、项目/成员管理。
- 后端 3D（文件 JSON/CSV 导入导出）若仍需要可补。


