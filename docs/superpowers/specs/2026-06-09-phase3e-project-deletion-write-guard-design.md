# 任务血缘工具 Phase 3E：删项目跨库清理 + 归档写守卫 — 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§3.2 跨库规则、§5.2 项目 API、§8 错误处理/跨库一致性兜底）
**前置子项目：** Phase 2（项目/成员/RBAC）、3A-3C（节点/边/图查询/SQL 导入）
**落地待办：** `[[phase3-archived-project-write-guard]]`（Phase 2 留下的归档写守卫）

## 目标

补齐删项目跨库一致性闭环 + 归档项目写守卫，是后端最后一环：
- 项目生命周期状态机 active / archived / deleting。
- 永久删除（purge）：同步清 Neo4j 图数据 + 删 MySQL 记录，失败可重跑。
- 归档/删除中项目禁止写入。

## 范围

**做：**
- 状态机迁移：archive（已有）、unarchive（新）、purge（新，含 deleting 中转）。
- purge 同步编排：set deleting → 清 Neo4j 节点/边/schema → 删 MySQL 记录（级联成员）。失败停在 deleting，重跑 purge 幂等。
- 写守卫：`require_role` 加 `require_active`，archived/deleting 项目写操作 → 409 `PROJECT_NOT_ACTIVE`。

**不做（YAGNI / 留后续）：**
- 异步任务队列 / 后台 worker（项目无队列基建，采用同步 + 可重跑端点）。
- `rebuild-graph` 管理命令（master §8 提及的极端不一致重建，本期不做）。
- 前端二次确认 UI（前端阶段做）。

## 决策（已与用户确认）

- **归档与删除分开**：archive 软可逆（保留图数据）；purge 永久不可逆。
- **purge 机制**：同步删除，幂等可重跑，无单独重跑端点（重新 POST purge 即重试）。
- **purge 前置**：必须先 archived；对 active 项目 purge → 409 `PROJECT_NOT_ARCHIVED`。
- **写守卫落地**：`require_role(min_role, require_active=False)` 加参数，写端点传 `require_active=True`。
- **守卫范围**：节点/边/schema/SQL 导入写 + 项目改名 + 成员管理；读端点与 lifecycle 动作（archive/unarchive/purge）不拦。
- **权限**：archive / unarchive / purge 均 owner-only。

## 状态机

```
active    ──DELETE /projects/:pid───────→ archived
archived  ──POST  /projects/:pid/unarchive→ active
archived  ──POST  /projects/:pid/purge───→ deleting ──(清 Neo4j + 删 MySQL)──→ ∅
deleting  ──POST  /projects/:pid/purge───→ deleting ─────────────────────────→ ∅   (幂等重跑)
active    ──POST  /projects/:pid/purge───→ 409 PROJECT_NOT_ARCHIVED
```

## 1. 文件结构

| 文件 | 新建/改 | 职责 |
|------|--------|------|
| `app/deps.py` | 改 | `require_role(min_role, require_active=False)` + 409 守卫 |
| `app/cypher/projects.py` | 新建 | `PURGE_NODES`（DETACH DELETE + 计数）、`PURGE_SCHEMAS` |
| `app/schemas/project.py` | 改 | 加 `PurgeResponse{deleted_nodes, deleted_schemas}` |
| `app/services/project_service.py` | 改 | 加 `unarchive_project`、`purge_project` |
| `app/routers/projects.py` | 改 | 加 `POST /unarchive`、`POST /purge`；PATCH（改名）加 require_active |
| `app/routers/nodes.py` | 改 | 写端点 `require_active=True` |
| `app/routers/edges.py` | 改 | 写端点 `require_active=True` |
| `app/routers/schemas.py` | 改 | 写端点 `require_active=True` |
| `app/routers/members.py` | 改 | 写端点 `require_active=True` |
| `app/routers/sql_import.py` | 改 | preview/commit 加 require_active=True |
| `tests/test_project_lifecycle.py` | 新建 | 状态机往返、purge 清理、重跑幂等 |
| `tests/test_archived_write_guard.py` | 新建 | 各类写在 archived 项目 409、读 200 |

## 2. require_role 改造（`deps.py`）

```python
def require_role(min_role: MemberRole, require_active: bool = False) -> Callable[..., "ProjectContext"]:
    def dep(pid, user, db) -> ProjectContext:
        project = db.get(Project, pid)
        if project is None:
            raise NotFoundError("项目不存在")
        membership = db.scalar(select(ProjectMember).where(
            ProjectMember.project_id == pid, ProjectMember.user_id == user.id))
        if membership is None:
            raise PermissionDenied("非项目成员")
        if membership.role.level < min_role.level:
            raise PermissionDenied("权限不足")
        if require_active and project.status != ProjectStatus.active:
            raise ConflictError("项目非活动状态，禁止写入", {"code": "PROJECT_NOT_ACTIVE"})
        return ProjectContext(project=project, membership=membership, user=user)
    return dep
```
默认 `require_active=False` → 向后兼容；现有读端点与 lifecycle 动作不受影响。需在 deps.py 顶部 import 已有的 `ConflictError`、`ProjectStatus`。

## 3. Cypher（`app/cypher/projects.py`）

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
`DETACH DELETE` 连带删 `:DEPENDS_ON`/`:CHILD_OF` 边，无需单独删边。

## 4. 服务编排（`project_service.py`）

```python
from app.cypher import projects as pq
from app.exceptions import ConflictError
from app.repositories.graph_repo import GraphRepo


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
    # 标记 deleting 并提交：崩溃也停在 deleting，可重跑
    project.status = ProjectStatus.deleting
    db.add(project)
    db.commit()
    pid = project.id
    deleted_nodes = repo.run_write(pq.PURGE_NODES, pid=pid)[0]["deleted_nodes"]
    deleted_schemas = repo.run_write(pq.PURGE_SCHEMAS, pid=pid)[0]["deleted_schemas"]
    # 删 MySQL：先成员（FK），再项目
    db.query(ProjectMember).filter(ProjectMember.project_id == pid).delete()
    db.delete(project)
    db.commit()
    logger.info("project.purge user=%s project=%s nodes=%s schemas=%s",
                actor.id, pid, deleted_nodes, deleted_schemas)
    return {"deleted_nodes": deleted_nodes, "deleted_schemas": deleted_schemas}
```

> purge 接受 archived 或 deleting（deleting=重跑）。Neo4j 删除幂等（重跑时已无节点→0）。删 MySQL 后该 project 行消失，后续 require_role 找不到 → 404，符合"已删除"语义。

## 5. 路由（`projects.py`）

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
PATCH /projects/:pid（改名）改为 `require_role(MemberRole.admin, require_active=True)`。
（archive/unarchive/purge 三个 lifecycle 端点**不**加 require_active。）

`schemas/project.py` 加：
```python
class PurgeResponse(BaseModel):
    deleted_nodes: int
    deleted_schemas: int
```

## 6. 写端点加守卫（各 router）

把以下写端点的 `require_role(X)` 改为 `require_role(X, require_active=True)`：
- `nodes.py`：create/update/delete node、set/clear parent（POST/PATCH/DELETE，含 `/{nid}/parent`）。
- `edges.py`：create/update/delete edge。
- `schemas.py`：create/update/delete schema。
- `members.py`：add/change-role/remove member。
- `sql_import.py`：preview、commit。
- 读端点（GET、图查询、遍历、impact、cycles、critical-paths）保持不变。

## 7. 错误处理（§8 信封）

| 场景 | 处理 |
|------|------|
| 对 archived/deleting 项目写（节点/边/schema/SQL导入/改名/成员） | 409 `PROJECT_NOT_ACTIVE` |
| active 项目直接 purge | 409 `PROJECT_NOT_ARCHIVED` |
| unarchive 非 archived 项目 | 409 `PROJECT_NOT_ARCHIVED` |
| purge/unarchive 非 owner | 403 |
| 对已 purge（不存在）项目任何操作 | 404 |

## 8. 测试

- `test_project_lifecycle.py`：
  - archive → unarchive → 回 active；unarchive 后可正常写。
  - archive → purge：先建 schema+节点+边，purge 后返回 `deleted_nodes>0`/`deleted_schemas>0`，GET 项目 404，节点/边端点 404，成员表清空（同名 owner 可重新建项目不冲突）。
  - active 直接 purge → 409 PROJECT_NOT_ARCHIVED。
  - unarchive 非归档 → 409。
  - purge/unarchive 非 owner（editor/admin）→ 403。
  - 重跑/deleting 入口：用 `seed` 直接把项目置为 `deleting`（模拟上次清理中断），并建好 Neo4j 节点，再 POST purge → 成功清理并删除（验证 purge 接受 deleting 状态、可重跑）。
- `test_archived_write_guard.py`（参数化各写端点）：
  - 归档项目上：建节点、建边、建 schema、SQL preview/commit、改名、加成员 → 全 409 `PROJECT_NOT_ACTIVE`。
  - 归档项目上读端点（GET 节点/边/图/schema）→ 仍 200。
  - 对照：归档前同样写操作 2xx。

## Definition of Done

- 全量 `pytest` 绿（Phase 1+2+3A+3B+3C+3E，无回归）。
- 状态机往返正确（active↔archived、archived→deleting→删除）。
- purge 真清 Neo4j（DETACH DELETE 节点/边 + schema）+ 删 MySQL（项目+成员），失败可重跑。
- 写守卫覆盖全部写端点（节点/边/schema/SQL导入/改名/成员），读不受影响。
- 错误符合 §8 信封（409 PROJECT_NOT_ACTIVE / PROJECT_NOT_ARCHIVED、403、404）。
- 落地 `[[phase3-archived-project-write-guard]]` 待办（实现后更新该记忆为已完成）。
- **后端跨库一致性闭环完成。**

## 下一阶段预告（不在本计划内）

- 前端：Vue3 + Pinia + AntV X6 画布、属性面板、影响分析视图、SQL 导入入口、项目/成员管理。
- 后端 3D（文件 JSON/CSV 导入导出）若仍需要可补。

