# 任务血缘工具 Phase 3B：依赖边 + 图查询/算法 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 3A 之上加依赖边 `:DEPENDS_ON` CRUD 与全部图查询/算法（上下游遍历、影响分析、关键路径、环检测、子图渲染），并给 NodeResponse 补上下游计数。

**Architecture:** 沿用 3A 分层 routers → services → cypher/。边唯一性靠服务层条件 CREATE；所有图算法单条 Cypher 直出，变长路径上限 `max_traversal_depth`（默认 15）由服务层把 `__DEPTH__` 占位符 `.replace` 成实际值后执行（不能参数化变长上界，且 Cypher 的 `{}` 与 `str.format` 冲突，故用 replace）。

**Tech Stack:** Python 3.10+、FastAPI、neo4j driver、Pydantic v2、pytest、testcontainers[neo4j]。

参考 spec：`docs/superpowers/specs/2026-06-09-phase3b-edges-graph-queries-design.md`。

---

## File Structure

- `backend/app/schemas/graph.py` — 改：加 Edge*/Graph*/Page/Impact*/CriticalPath*/Cycle* 模型；NodeResponse 加 upstream_count/downstream_count。
- `backend/app/cypher/edges.py` — 新建：边 CRUD + 成环预警 Cypher。
- `backend/app/cypher/graph.py` — 新建：遍历/子图/关键路径/环检测 Cypher（含 `__DEPTH__` 占位符）。
- `backend/app/cypher/nodes.py` — 改：GET 加递归上下游计数；LIST/UPDATE 加邻居计数。
- `backend/app/services/edge_service.py` — 新建：边 CRUD + 唯一性 + 成环预警 + 审计。
- `backend/app/services/graph_service.py` — 新建：遍历（分页）、impact、关键路径、环检测、子图。
- `backend/app/services/node_service.py` — 改：GET 递归计数、LIST/UPDATE 邻居计数、_row_to_node 读计数。
- `backend/app/routers/edges.py` — 新建：`/projects/{pid}/edges` 系列。
- `backend/app/routers/graph.py` — 新建：`/projects/{pid}/graph`、`/cycles`、`/critical-paths`。
- `backend/app/routers/nodes.py` — 改：加 `/{nid}/upstream`、`/downstream`、`/impact`。
- `backend/app/main.py` — 改：注册 edges + graph 路由。
- 测试：`test_schemas_graph_edges.py`、`test_edge_api.py`、`test_node_counts.py`、`test_graph_query_api.py`、`test_critical_path_api.py`、`test_cycle_api.py`、`test_graph_permission_matrix.py`（改）。

约定：所有命令在 `cd backend && . .venv/bin/activate` 下跑；commit 在仓库根 `/Users/zyc/Data/App/obsidian/pawnZzz/tmp8`，message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## Task 1: 图边/图查询 Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/graph.py`
- Test: `backend/tests/test_schemas_graph_edges.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_schemas_graph_edges.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.graph import (
    CreateEdgeRequest,
    EdgeResponse,
    GraphNode,
    NodeResponse,
)


def test_create_edge_defaults():
    r = CreateEdgeRequest(source_id="a", target_id="b")
    assert r.edge_type == "data_flow"
    assert r.is_required is True
    assert r.strength == "strong"
    assert r.ext_props == {}


def test_create_edge_rejects_bad_edge_type():
    with pytest.raises(ValidationError):
        CreateEdgeRequest(source_id="a", target_id="b", edge_type="bogus")


def test_create_edge_rejects_bad_strength():
    with pytest.raises(ValidationError):
        CreateEdgeRequest(source_id="a", target_id="b", strength="medium")


def test_node_response_counts_default_zero():
    n = NodeResponse(
        id="n", project_id=1, name="x", type="t",
        tags=[], ext_props={}, is_critical=False,
        created_at="2026-06-09T00:00:00", updated_at="2026-06-09T00:00:00",
        created_by=1, updated_by=1, children_count=0,
    )
    assert n.upstream_count == 0
    assert n.downstream_count == 0


def test_graph_node_minimal():
    g = GraphNode(id="n", name="x", type="t", is_critical=False)
    assert g.priority is None
    assert g.parent_id is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_schemas_graph_edges.py -q`
Expected: FAIL（ImportError: cannot import name 'CreateEdgeRequest'）

- [ ] **Step 3: 在 `backend/app/schemas/graph.py` 顶部 import 区确认有 `Literal`**

文件首行已是 `from typing import Any, Literal`（3A 已引入）。若没有则改成该行。

- [ ] **Step 4: 给 NodeResponse 加两计数字段**

把 `NodeResponse` 里 `children_count: int` 那行后面紧接着加两行：
```python
    children_count: int
    upstream_count: int = 0
    downstream_count: int = 0
```

- [ ] **Step 5: 在 `backend/app/schemas/graph.py` 末尾追加边/图模型**

```python
EdgeType = Literal["trigger", "data_flow", "api_call", "custom"]
Strength = Literal["strong", "weak"]


class CreateEdgeRequest(BaseModel):
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    edge_type: EdgeType = "data_flow"
    description: str | None = None
    is_required: bool = True
    strength: Strength = "strong"
    ext_props: dict[str, Any] = {}


class UpdateEdgeRequest(BaseModel):
    edge_type: EdgeType | None = None
    description: str | None = None
    is_required: bool | None = None
    strength: Strength | None = None
    ext_props: dict[str, Any] | None = None


class EdgeResponse(BaseModel):
    id: str
    project_id: int
    source_id: str
    target_id: str
    edge_type: str
    description: str | None = None
    is_required: bool
    strength: str
    ext_props: dict[str, Any]
    created_at: datetime
    created_by: int


class EdgeWarnings(BaseModel):
    creates_cycle: bool = False


class CreateEdgeResponse(BaseModel):
    edge: EdgeResponse
    warnings: EdgeWarnings


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    priority: str | None = None
    is_critical: bool
    parent_id: str | None = None


class GraphStats(BaseModel):
    node_count: int
    edge_count: int
    has_cycle: bool


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[EdgeResponse]
    stats: GraphStats


class NodePage(BaseModel):
    items: list[NodeResponse]
    total: int
    limit: int
    offset: int


class CycleResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[EdgeResponse]


class ImpactResponse(BaseModel):
    upstream: list[NodeResponse]
    downstream: list[NodeResponse]
    warnings: dict


class PathItem(BaseModel):
    nodes: list[GraphNode]
    edges: list[EdgeResponse]
    depth: int
    score: int | None = None


class CriticalPathResponse(BaseModel):
    mode: str
    paths: list[PathItem]
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_schemas_graph_edges.py -q`
Expected: 5 passed。

- [ ] **Step 7: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/schemas/graph.py backend/tests/test_schemas_graph_edges.py
git commit -m "feat: 图边与图查询 Pydantic schemas + NodeResponse 上下游计数字段"
```

## Task 2: 依赖边 CRUD（cypher + service + router）

**Files:**
- Modify: `backend/app/cypher/__init__.py`
- Create: `backend/app/cypher/edges.py`
- Create: `backend/app/services/edge_service.py`
- Create: `backend/app/routers/edges.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_edge_api.py`

- [ ] **Step 1: 在 `backend/app/cypher/__init__.py` 加深度内联 helper**

文件当前为空，写入：
```python
from app.config import get_settings


def inline_depth(cypher: str) -> str:
    """把 Cypher 里的 __DEPTH__ 占位符替换为 config 的 max_traversal_depth。

    变长路径上界 `*1..N` 的 N 不能用 Cypher 参数，只能拼串；N 来自可信 config，
    非用户输入，无注入风险。
    """
    return cypher.replace("__DEPTH__", str(get_settings().max_traversal_depth))
```

- [ ] **Step 2: 创建 `backend/app/cypher/edges.py`**

```python
# 边响应统一投影：关系本身不存 project_id/source/target，从两端节点取
_EDGE = """{
  id: r.id, project_id: s.project_id, source_id: s.id, target_id: t.id,
  edge_type: r.edge_type, description: r.description, is_required: r.is_required,
  strength: r.strength, ext_props: r.ext_props, created_at: r.created_at,
  created_by: r.created_by
}"""

# 条件创建：两端点须存在且尚无 (s)->(t) 边，否则返回 0 行
CREATE_IF_ABSENT = """
MATCH (s:LineageNode {project_id: $pid, id: $source_id})
MATCH (t:LineageNode {project_id: $pid, id: $target_id})
WHERE NOT (s)-[:DEPENDS_ON]->(t)
CREATE (s)-[r:DEPENDS_ON {
  id: $id, edge_type: $edge_type, description: $description,
  is_required: $is_required, strength: $strength, ext_props: $ext_props,
  created_at: datetime(), created_by: $uid
}]->(t)
RETURN __EDGE__ AS edge
""".replace("__EDGE__", _EDGE)

# 建边后判是否成环：s 能否沿出边回到自身
CREATES_CYCLE = """
MATCH (s:LineageNode {project_id: $pid, id: $source_id})
RETURN EXISTS { MATCH (s)-[:DEPENDS_ON*1..__DEPTH__]->(s) } AS creates_cycle
"""

GET = """
MATCH (s:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(t:LineageNode)
RETURN __EDGE__ AS edge
""".replace("__EDGE__", _EDGE)

LIST = """
MATCH (s:LineageNode {project_id: $pid})-[r:DEPENDS_ON]->(t:LineageNode)
WHERE ($source_id IS NULL OR s.id = $source_id)
  AND ($target_id IS NULL OR t.id = $target_id)
  AND ($edge_type IS NULL OR r.edge_type = $edge_type)
RETURN __EDGE__ AS edge
ORDER BY r.created_at
""".replace("__EDGE__", _EDGE)

UPDATE = """
MATCH (s:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(t:LineageNode)
SET r += $props
RETURN __EDGE__ AS edge
""".replace("__EDGE__", _EDGE)

DELETE = """
MATCH (:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(:LineageNode)
DELETE r
RETURN count(r) AS deleted
"""

EXISTS = """
MATCH (:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(:LineageNode)
RETURN r.id AS id
"""
```

- [ ] **Step 3: 创建 `backend/app/services/edge_service.py`**

```python
import json
import logging
import uuid
from typing import Any

from app.cypher import edges as q
from app.cypher import inline_depth
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.graph_repo import GraphRepo

logger = logging.getLogger("app.audit")

_EDGE_SCALARS = ["edge_type", "description", "is_required", "strength"]


def _row_to_edge(edge: dict) -> dict:
    data = dict(edge)
    data["ext_props"] = json.loads(data.get("ext_props") or "{}")
    created = data.get("created_at")
    if hasattr(created, "to_native"):
        data["created_at"] = created.to_native()
    return data


def _node_exists(repo: GraphRepo, pid: int, nid: str) -> bool:
    from app.cypher import nodes as nq
    return bool(repo.run_read(nq.EXISTS, pid=pid, nid=nid))


def create_edge(repo: GraphRepo, pid: int, uid: int, payload: dict) -> dict:
    source_id, target_id = payload["source_id"], payload["target_id"]
    if source_id == target_id:
        raise ValidationError("边的两端不能是同一节点", {"code": "SELF_LOOP"})
    if not _node_exists(repo, pid, source_id):
        raise NotFoundError("源节点不存在", {"id": source_id})
    if not _node_exists(repo, pid, target_id):
        raise NotFoundError("目标节点不存在", {"id": target_id})

    rows = repo.run_write(
        q.CREATE_IF_ABSENT,
        pid=pid, id=str(uuid.uuid4()), source_id=source_id, target_id=target_id,
        edge_type=payload.get("edge_type", "data_flow"),
        description=payload.get("description"),
        is_required=payload.get("is_required", True),
        strength=payload.get("strength", "strong"),
        ext_props=json.dumps(payload.get("ext_props") or {}),
        uid=uid,
    )
    if not rows:
        raise ConflictError("两节点间已存在依赖边", {"code": "EDGE_EXISTS"})

    cycle = repo.run_read(inline_depth(q.CREATES_CYCLE), pid=pid, source_id=source_id)
    creates_cycle = bool(cycle and cycle[0]["creates_cycle"])
    edge = _row_to_edge(rows[0]["edge"])
    logger.info("edge.create pid=%s eid=%s by=%s", pid, edge["id"], uid)
    return {"edge": edge, "warnings": {"creates_cycle": creates_cycle}}


def get_edge(repo: GraphRepo, pid: int, eid: str) -> dict:
    rows = repo.run_read(q.GET, pid=pid, eid=eid)
    if not rows:
        raise NotFoundError("依赖边不存在", {"id": eid})
    return _row_to_edge(rows[0]["edge"])


def list_edges(repo: GraphRepo, pid: int, filters: dict) -> list[dict]:
    rows = repo.run_read(
        q.LIST, pid=pid,
        source_id=filters.get("source_id"), target_id=filters.get("target_id"),
        edge_type=filters.get("edge_type"),
    )
    return [_row_to_edge(r["edge"]) for r in rows]


def update_edge(repo: GraphRepo, pid: int, eid: str, uid: int, patch: dict) -> dict:
    get_edge(repo, pid, eid)  # 404 if missing
    props: dict[str, Any] = {}
    for key in _EDGE_SCALARS:
        if key in patch and patch[key] is not None:
            props[key] = patch[key]
    if "ext_props" in patch and patch["ext_props"] is not None:
        props["ext_props"] = json.dumps(patch["ext_props"])
    rows = repo.run_write(q.UPDATE, pid=pid, eid=eid, props=props)
    logger.info("edge.update pid=%s eid=%s by=%s", pid, eid, uid)
    return _row_to_edge(rows[0]["edge"])


def delete_edge(repo: GraphRepo, pid: int, eid: str, uid: int) -> None:
    rows = repo.run_write(q.DELETE, pid=pid, eid=eid)
    if not rows or rows[0]["deleted"] == 0:
        raise NotFoundError("依赖边不存在", {"id": eid})
    logger.info("edge.delete pid=%s eid=%s by=%s", pid, eid, uid)
```

- [ ] **Step 4: 创建 `backend/app/routers/edges.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import (
    CreateEdgeRequest,
    CreateEdgeResponse,
    EdgeResponse,
    UpdateEdgeRequest,
)
from app.services import edge_service

router = APIRouter(prefix="/api/v1/projects/{pid}/edges", tags=["edges"])


@router.get("", response_model=list[EdgeResponse])
def list_edges(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    source_id: Annotated[str | None, Query()] = None,
    target_id: Annotated[str | None, Query()] = None,
    edge_type: Annotated[str | None, Query()] = None,
) -> list[EdgeResponse]:
    filters = {"source_id": source_id, "target_id": target_id, "edge_type": edge_type}
    return edge_service.list_edges(repo, ctx.project.id, filters)


@router.post("", response_model=CreateEdgeResponse, status_code=status.HTTP_201_CREATED)
def create_edge(
    payload: CreateEdgeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> CreateEdgeResponse:
    return edge_service.create_edge(repo, ctx.project.id, ctx.user.id, payload.model_dump())


@router.get("/{eid}", response_model=EdgeResponse)
def get_edge(
    eid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> EdgeResponse:
    return edge_service.get_edge(repo, ctx.project.id, eid)


@router.patch("/{eid}", response_model=EdgeResponse)
def update_edge(
    eid: str,
    payload: UpdateEdgeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> EdgeResponse:
    return edge_service.update_edge(
        repo, ctx.project.id, eid, ctx.user.id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{eid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edge(
    eid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> None:
    edge_service.delete_edge(repo, ctx.project.id, eid, ctx.user.id)
    return None
```

- [ ] **Step 5: `backend/app/main.py` 注册 edges 路由**

在 nodes_router 注册之后追加：
```python
    from app.routers import edges as edges_router

    app.include_router(edges_router.router)
```

- [ ] **Step 6: 写测试 `backend/tests/test_edge_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _mk_schema(client, seed, p, owner):
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))


def _mk_node(client, seed, p, owner, name):
    return client.post(f"/api/v1/projects/{p.id}/nodes",
                       json={"name": name, "type": "t"},
                       headers=_auth(seed, owner)).json()["id"]


def test_create_and_get_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b, "edge_type": "trigger"},
                    headers=_auth(seed, owner))
    assert r.status_code == 201
    body = r.json()
    assert body["warnings"]["creates_cycle"] is False
    eid = body["edge"]["id"]
    assert body["edge"]["source_id"] == a and body["edge"]["target_id"] == b
    r2 = client.get(f"/api/v1/projects/{p.id}/edges/{eid}", headers=_auth(seed, owner))
    assert r2.status_code == 200
    assert r2.json()["edge_type"] == "trigger"


def test_create_edge_missing_endpoint_404(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": "nope"}, headers=_auth(seed, owner))
    assert r.status_code == 404


def test_duplicate_edge_409(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    body = {"source_id": a, "target_id": b}
    client.post(f"/api/v1/projects/{p.id}/edges", json=body, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/edges", json=body, headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "EDGE_EXISTS"


def test_self_loop_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": a}, headers=_auth(seed, owner))
    assert r.status_code == 422
    assert r.json()["error"]["details"].get("code") == "SELF_LOOP"


def test_list_edges_filter(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    c = _mk_node(client, seed, p, owner, "c")
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": a, "target_id": b, "edge_type": "trigger"},
                headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": a, "target_id": c, "edge_type": "data_flow"},
                headers=_auth(seed, owner))
    r = client.get(f"/api/v1/projects/{p.id}/edges?source_id={a}", headers=_auth(seed, owner))
    assert len(r.json()) == 2
    r2 = client.get(f"/api/v1/projects/{p.id}/edges?edge_type=trigger", headers=_auth(seed, owner))
    assert {e["target_id"] for e in r2.json()} == {b}


def test_update_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    eid = client.post(f"/api/v1/projects/{p.id}/edges",
                      json={"source_id": a, "target_id": b},
                      headers=_auth(seed, owner)).json()["edge"]["id"]
    r = client.patch(f"/api/v1/projects/{p.id}/edges/{eid}",
                     json={"strength": "weak", "description": "soft"},
                     headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["strength"] == "weak"
    assert r.json()["description"] == "soft"


def test_delete_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    eid = client.post(f"/api/v1/projects/{p.id}/edges",
                      json={"source_id": a, "target_id": b},
                      headers=_auth(seed, owner)).json()["edge"]["id"]
    r = client.delete(f"/api/v1/projects/{p.id}/edges/{eid}", headers=_auth(seed, owner))
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/projects/{p.id}/edges/{eid}", headers=_auth(seed, owner))
    assert r2.status_code == 404


def test_edge_write_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer"); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b}, headers=_auth(seed, viewer))
    assert r.status_code == 403
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_edge_api.py -q`
Expected: 8 passed。若边 `created_at` 序列化报错，确认 `_row_to_edge` 的 `.to_native()` 已生效。

- [ ] **Step 8: 全量回归**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿。

- [ ] **Step 9: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher/__init__.py backend/app/cypher/edges.py backend/app/services/edge_service.py backend/app/routers/edges.py backend/app/main.py backend/tests/test_edge_api.py
git commit -m "feat: 依赖边 CRUD（cypher+service+router）含唯一性、自环拒绝与成环预警"
```

## Task 3: NodeResponse 上下游计数（详情递归 / 列表邻居）

**Files:**
- Modify: `backend/app/cypher/nodes.py`
- Modify: `backend/app/services/node_service.py`
- Test: `backend/tests/test_node_counts.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_node_counts.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _mk_schema(client, seed, p, owner):
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))


def _mk_node(client, seed, p, owner, name):
    return client.post(f"/api/v1/projects/{p.id}/nodes",
                       json={"name": name, "type": "t"},
                       headers=_auth(seed, owner)).json()["id"]


def _edge(client, seed, p, owner, s, t):
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": s, "target_id": t}, headers=_auth(seed, owner))


def test_detail_counts_are_recursive(client, seed):
    # a -> b -> c：a 的上游递归=2（b,c），c 的下游递归=2（a,b）
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    c = _mk_node(client, seed, p, owner, "c")
    _edge(client, seed, p, owner, a, b)
    _edge(client, seed, p, owner, b, c)
    da = client.get(f"/api/v1/projects/{p.id}/nodes/{a}", headers=_auth(seed, owner)).json()
    assert da["upstream_count"] == 2
    assert da["downstream_count"] == 0
    dc = client.get(f"/api/v1/projects/{p.id}/nodes/{c}", headers=_auth(seed, owner)).json()
    assert dc["downstream_count"] == 2
    assert dc["upstream_count"] == 0


def test_list_counts_are_neighbors(client, seed):
    # a -> b -> c：list 里 a 上游邻居=1（仅 b），c 下游邻居=1（仅 b）
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    c = _mk_node(client, seed, p, owner, "c")
    _edge(client, seed, p, owner, a, b)
    _edge(client, seed, p, owner, b, c)
    rows = client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, owner)).json()
    by = {n["name"]: n for n in rows}
    assert by["a"]["upstream_count"] == 1 and by["a"]["downstream_count"] == 0
    assert by["b"]["upstream_count"] == 1 and by["b"]["downstream_count"] == 1
    assert by["c"]["upstream_count"] == 0 and by["c"]["downstream_count"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_node_counts.py -q`
Expected: FAIL（upstream_count 都是 0，断言不通过）

- [ ] **Step 3: 改 `backend/app/cypher/nodes.py` 的 GET（递归计数）**

把现有 `GET = """..."""` 整段替换为：
```python
GET = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
RETURN n, parent.id AS parent_id,
  COUNT { (n)<-[:CHILD_OF]-(:LineageNode) } AS children_count,
  COUNT { MATCH (n)-[:DEPENDS_ON*1..__DEPTH__]->(m:LineageNode) RETURN DISTINCT m } AS upstream_count,
  COUNT { MATCH (n)<-[:DEPENDS_ON*1..__DEPTH__]-(m:LineageNode) RETURN DISTINCT m } AS downstream_count
"""
```

- [ ] **Step 4: 改 `backend/app/cypher/nodes.py` 的 LIST（邻居计数）**

把 LIST 末尾的 `RETURN n, parent_id, children_count` 行替换为：
```python
RETURN n, parent_id, children_count,
  COUNT { (n)-[:DEPENDS_ON]->(:LineageNode) } AS upstream_count,
  COUNT { (n)<-[:DEPENDS_ON]-(:LineageNode) } AS downstream_count
```
（`ORDER BY n.name` 保持在最后不变。）

- [ ] **Step 5: 改 `backend/app/cypher/nodes.py` 的 UPDATE（邻居计数）**

把 UPDATE 整段替换为：
```python
UPDATE = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
SET n += $props, n.updated_at = datetime(), n.updated_by = $uid
WITH n
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
RETURN n, parent.id AS parent_id,
  COUNT { (n)<-[:CHILD_OF]-(:LineageNode) } AS children_count,
  COUNT { (n)-[:DEPENDS_ON]->(:LineageNode) } AS upstream_count,
  COUNT { (n)<-[:DEPENDS_ON]-(:LineageNode) } AS downstream_count
"""
```

- [ ] **Step 6: 改 `backend/app/services/node_service.py`**

顶部 import 区把 `from app.cypher import nodes as q` 下面加一行：
```python
from app.cypher import inline_depth
```

在 `_row_to_node` 里 `node["children_count"] = row.get("children_count", 0)` 之后加两行：
```python
    node["upstream_count"] = row.get("upstream_count", 0)
    node["downstream_count"] = row.get("downstream_count", 0)
```

把 `get_node` 里 `rows = repo.run_read(q.GET, pid=pid, nid=nid)` 改为：
```python
    rows = repo.run_read(inline_depth(q.GET), pid=pid, nid=nid)
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_node_counts.py tests/test_node_api.py tests/test_parent_api.py -q`
Expected: 全绿（含 3A 既有节点/父子测试无回归）。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher/nodes.py backend/app/services/node_service.py backend/tests/test_node_counts.py
git commit -m "feat: NodeResponse 上下游计数（详情递归、列表/改邻居）"
```

## Task 4: 上下游遍历（分页）+ 影响分析

**Files:**
- Create: `backend/app/cypher/graph.py`
- Create: `backend/app/services/graph_service.py`
- Modify: `backend/app/routers/nodes.py`
- Test: `backend/tests/test_graph_query_api.py`（本任务先写遍历/impact 部分）

- [ ] **Step 1: 创建 `backend/app/cypher/graph.py`**

```python
# 子图/环检测里把关系、节点投影成普通 map（ext_props/created_at 在 Python 再 coerce）。
# parent_id 用 pattern comprehension 取（节点至多一个 CHILD_OF 出边）。
GNODE = (
    "{id:x.id, name:x.name, type:x.type, priority:x.priority, "
    "is_critical:x.is_critical, parent_id: head([(x)-[:CHILD_OF]->(pp) | pp.id])}"
)
EDGE_FROM_REL = (
    "{id:r.id, project_id:startNode(r).project_id, source_id:startNode(r).id, "
    "target_id:endNode(r).id, edge_type:r.edge_type, description:r.description, "
    "is_required:r.is_required, strength:r.strength, ext_props:r.ext_props, "
    "created_at:r.created_at, created_by:r.created_by}"
)

# 遍历结果节点用「邻居计数」（省得每个结果再跑变长遍历）。m AS n 对齐 _row_to_node。
_TRAVERSE_RETURN = """
WITH DISTINCT m
OPTIONAL MATCH (m)-[:CHILD_OF]->(parent:LineageNode)
RETURN m AS n, parent.id AS parent_id,
  COUNT { (m)<-[:CHILD_OF]-(:LineageNode) } AS children_count,
  COUNT { (m)-[:DEPENDS_ON]->(:LineageNode) } AS upstream_count,
  COUNT { (m)<-[:DEPENDS_ON]-(:LineageNode) } AS downstream_count
ORDER BY m.name SKIP $offset LIMIT $limit
"""

UPSTREAM = (
    "MATCH (start:LineageNode {project_id: $pid, id: $nid})"
    "-[:DEPENDS_ON*1..__DEPTH__]->(m:LineageNode)" + _TRAVERSE_RETURN
)
DOWNSTREAM = (
    "MATCH (start:LineageNode {project_id: $pid, id: $nid})"
    "<-[:DEPENDS_ON*1..__DEPTH__]-(m:LineageNode)" + _TRAVERSE_RETURN
)
UPSTREAM_COUNT = """
MATCH (start:LineageNode {project_id: $pid, id: $nid})-[:DEPENDS_ON*1..__DEPTH__]->(m:LineageNode)
RETURN count(DISTINCT m) AS total
"""
DOWNSTREAM_COUNT = """
MATCH (start:LineageNode {project_id: $pid, id: $nid})<-[:DEPENDS_ON*1..__DEPTH__]-(m:LineageNode)
RETURN count(DISTINCT m) AS total
"""

# 某节点参与的环（impact 用）
NODE_CYCLES = (
    "MATCH path=(n:LineageNode {project_id: $pid, id: $nid})-[:DEPENDS_ON*1..__DEPTH__]->(n) "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges LIMIT 50"
)
```

- [ ] **Step 2: 创建 `backend/app/services/graph_service.py`**

```python
import json
from typing import Any

from app.cypher import graph as q
from app.cypher import inline_depth
from app.repositories.graph_repo import GraphRepo
from app.services.node_service import _row_to_node, get_node


def _coerce_edge(e: dict) -> dict:
    e = dict(e)
    e["ext_props"] = json.loads(e.get("ext_props") or "{}")
    created = e.get("created_at")
    if hasattr(created, "to_native"):
        e["created_at"] = created.to_native()
    return e


def _coerce_cycle(row: dict) -> dict:
    return {"nodes": row["nodes"], "edges": [_coerce_edge(e) for e in row["edges"]]}


def _traverse(repo: GraphRepo, pid: int, nid: str, direction: str, limit: int, offset: int) -> dict:
    get_node(repo, pid, nid)  # 404 if node missing
    list_q = q.UPSTREAM if direction == "upstream" else q.DOWNSTREAM
    count_q = q.UPSTREAM_COUNT if direction == "upstream" else q.DOWNSTREAM_COUNT
    rows = repo.run_read(inline_depth(list_q), pid=pid, nid=nid, limit=limit, offset=offset)
    total = repo.run_read(inline_depth(count_q), pid=pid, nid=nid)[0]["total"]
    return {"items": [_row_to_node(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


def upstream(repo: GraphRepo, pid: int, nid: str, limit: int, offset: int) -> dict:
    return _traverse(repo, pid, nid, "upstream", limit, offset)


def downstream(repo: GraphRepo, pid: int, nid: str, limit: int, offset: int) -> dict:
    return _traverse(repo, pid, nid, "downstream", limit, offset)


def impact(repo: GraphRepo, pid: int, nid: str) -> dict:
    get_node(repo, pid, nid)  # 404 if missing
    up_total = repo.run_read(inline_depth(q.UPSTREAM_COUNT), pid=pid, nid=nid)[0]["total"]
    down_total = repo.run_read(inline_depth(q.DOWNSTREAM_COUNT), pid=pid, nid=nid)[0]["total"]
    up_rows = repo.run_read(inline_depth(q.UPSTREAM), pid=pid, nid=nid, limit=up_total, offset=0)
    down_rows = repo.run_read(inline_depth(q.DOWNSTREAM), pid=pid, nid=nid, limit=down_total, offset=0)
    cycles = repo.run_read(inline_depth(q.NODE_CYCLES), pid=pid, nid=nid)
    return {
        "upstream": [_row_to_node(r) for r in up_rows],
        "downstream": [_row_to_node(r) for r in down_rows],
        "warnings": {"cycles": [_coerce_cycle(c) for c in cycles]},
    }
```

> `limit=0`（无上下游时）Neo4j 的 `LIMIT 0` 合法、返回空，符合预期。

- [ ] **Step 3: 改 `backend/app/routers/nodes.py` 加 3 个端点**

顶部 import 区加：
```python
from app.schemas.graph import ImpactResponse, NodePage
from app.services import graph_service
```
（与已有 `from app.services import node_service` 并列；`fastapi` 的 `Query` 已在 3A import。）

在文件末尾（父子端点之后）追加：
```python
@router.get("/{nid}/upstream", response_model=NodePage)
def node_upstream(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NodePage:
    return graph_service.upstream(repo, ctx.project.id, nid, limit, offset)


@router.get("/{nid}/downstream", response_model=NodePage)
def node_downstream(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NodePage:
    return graph_service.downstream(repo, ctx.project.id, nid, limit, offset)


@router.get("/{nid}/impact", response_model=ImpactResponse)
def node_impact(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> ImpactResponse:
    return graph_service.impact(repo, ctx.project.id, nid)
```

- [ ] **Step 4: 写测试 `backend/tests/test_graph_query_api.py`（遍历 + impact）**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _setup_chain(client, seed):
    # a -> b -> c -> d 链
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    ids = {}
    for nm in ["a", "b", "c", "d"]:
        ids[nm] = client.post(f"/api/v1/projects/{p.id}/nodes",
                              json={"name": nm, "type": "t"},
                              headers=_auth(seed, owner)).json()["id"]
    for s, t in [("a", "b"), ("b", "c"), ("c", "d")]:
        client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": ids[s], "target_id": ids[t]},
                    headers=_auth(seed, owner))
    return owner, p, ids


def test_upstream_recursive(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['a']}/upstream", headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert {n["name"] for n in body["items"]} == {"b", "c", "d"}


def test_downstream_recursive(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['d']}/downstream", headers=_auth(seed, owner))
    assert {n["name"] for n in r.json()["items"]} == {"a", "b", "c"}


def test_upstream_pagination(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['a']}/upstream?limit=2&offset=0",
                   headers=_auth(seed, owner))
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["limit"] == 2


def test_upstream_missing_node_404(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/nope/upstream", headers=_auth(seed, owner))
    assert r.status_code == 404


def test_impact_shape(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['b']}/impact", headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert {n["name"] for n in body["upstream"]} == {"c", "d"}
    assert {n["name"] for n in body["downstream"]} == {"a"}
    assert body["warnings"]["cycles"] == []
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_graph_query_api.py -q`
Expected: 5 passed。

- [ ] **Step 6: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher/graph.py backend/app/services/graph_service.py backend/app/routers/nodes.py backend/tests/test_graph_query_api.py
git commit -m "feat: 上下游遍历（分页）与影响分析接口"
```

## Task 5: 关键路径（impact / longest / manual 三模式）

**Files:**
- Modify: `backend/app/schemas/graph.py`（加 CriticalPathRequest）
- Modify: `backend/app/cypher/graph.py`（加 3 模式 Cypher）
- Modify: `backend/app/services/graph_service.py`（加 critical_paths）
- Create: `backend/app/routers/graph.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_critical_path_api.py`

- [ ] **Step 1: `backend/app/schemas/graph.py` 加请求模型**

在 `CriticalPathResponse` 定义之前加：
```python
class CriticalPathRequest(BaseModel):
    mode: Literal["impact", "longest", "manual"] = "impact"
    node_ids: list[str] | None = None
```
（非法 mode 由 `Literal` 触发 Pydantic 422，无需服务层再校验。）

- [ ] **Step 2: `backend/app/cypher/graph.py` 末尾加 3 模式 Cypher**

```python
# 模式 1：下游影响面最大的节点 → 取其最深下游链（score=影响面）
CRITICAL_IMPACT = (
    "MATCH (n:LineageNode {project_id: $pid}) "
    "OPTIONAL MATCH (n)<-[:DEPENDS_ON*1..__DEPTH__]-(d:LineageNode) "
    "WITH n, count(DISTINCT d) AS impact ORDER BY impact DESC LIMIT 1 "
    "MATCH path = (n)<-[:DEPENDS_ON*1..__DEPTH__]-(leaf:LineageNode) "
    "WHERE NOT (leaf)<-[:DEPENDS_ON]-() "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges, "
    "length(path) AS depth, impact AS score ORDER BY depth DESC LIMIT 1"
)

# 模式 2：DAG 最长链 top5（无入边起点 → 无出边终点）
CRITICAL_LONGEST = (
    "MATCH path = (start:LineageNode {project_id: $pid})"
    "-[:DEPENDS_ON*1..__DEPTH__]->(end:LineageNode) "
    "WHERE NOT ()-[:DEPENDS_ON]->(start) AND NOT (end)-[:DEPENDS_ON]->() "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges, "
    "length(path) AS depth, null AS score ORDER BY depth DESC LIMIT 5"
)

# 模式 3：手动关键节点两两 shortestPath。node_ids 给定则用之，否则用 is_critical
CRITICAL_MANUAL = (
    "MATCH (a:LineageNode {project_id: $pid}) "
    "MATCH (b:LineageNode {project_id: $pid}) "
    "WHERE a.id <> b.id AND "
    "(($node_ids IS NULL AND a.is_critical AND b.is_critical) OR "
    " ($node_ids IS NOT NULL AND a.id IN $node_ids AND b.id IN $node_ids)) "
    "MATCH path = shortestPath((a)-[:DEPENDS_ON*1..__DEPTH__]->(b)) "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges, "
    "length(path) AS depth, null AS score ORDER BY depth DESC LIMIT 5"
)
```

- [ ] **Step 3: `backend/app/services/graph_service.py` 加 critical_paths**

```python
_CRITICAL_Q = {
    "impact": q.CRITICAL_IMPACT,
    "longest": q.CRITICAL_LONGEST,
    "manual": q.CRITICAL_MANUAL,
}


def _coerce_path(row: dict) -> dict:
    return {
        "nodes": row["nodes"],
        "edges": [_coerce_edge(e) for e in row["edges"]],
        "depth": row["depth"],
        "score": row.get("score"),
    }


def critical_paths(repo: GraphRepo, pid: int, mode: str, node_ids: list | None) -> dict:
    rows = repo.run_read(inline_depth(_CRITICAL_Q[mode]), pid=pid, node_ids=node_ids)
    return {"mode": mode, "paths": [_coerce_path(r) for r in rows]}
```

> `impact`/`longest` 的 Cypher 不含 `$node_ids`，但 driver 多传无害参数会报错——故三条都通过同一 `run_read(..., node_ids=node_ids)` 调用时，需保证每条 Cypher 都「引用」该参数或 driver 忽略未用参数。Neo4j driver **允许多余参数**（未用即忽略），故安全。

- [ ] **Step 4: 创建 `backend/app/routers/graph.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import CriticalPathRequest, CriticalPathResponse
from app.services import graph_service

router = APIRouter(prefix="/api/v1/projects/{pid}", tags=["graph"])


@router.post("/critical-paths", response_model=CriticalPathResponse)
def critical_paths(
    payload: CriticalPathRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> CriticalPathResponse:
    return graph_service.critical_paths(
        repo, ctx.project.id, payload.mode, payload.node_ids
    )
```

- [ ] **Step 5: `backend/app/main.py` 注册 graph 路由**

在 edges_router 注册之后追加：
```python
    from app.routers import graph as graph_router

    app.include_router(graph_router.router)
```

- [ ] **Step 6: 写测试 `backend/tests/test_critical_path_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _chain(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    ids = {}
    for nm in ["a", "b", "c"]:
        ids[nm] = client.post(f"/api/v1/projects/{p.id}/nodes",
                              json={"name": nm, "type": "t"},
                              headers=_auth(seed, owner)).json()["id"]
    for s, t in [("a", "b"), ("b", "c")]:
        client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": ids[s], "target_id": ids[t]},
                    headers=_auth(seed, owner))
    return owner, p, ids


def test_critical_impact_mode(client, seed):
    owner, p, ids = _chain(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "impact"}, headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "impact"
    assert len(body["paths"]) == 1
    assert body["paths"][0]["depth"] >= 1


def test_critical_longest_mode(client, seed):
    owner, p, ids = _chain(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "longest"}, headers=_auth(seed, owner))
    assert r.status_code == 200
    # 最长链 a->b->c depth=2
    assert max(pth["depth"] for pth in r.json()["paths"]) == 2


def test_critical_manual_mode_with_node_ids(client, seed):
    owner, p, ids = _chain(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "manual", "node_ids": [ids["a"], ids["c"]]},
                    headers=_auth(seed, owner))
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert len(paths) == 1
    assert {n["name"] for n in paths[0]["nodes"]} == {"a", "b", "c"}


def test_critical_invalid_mode_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "bogus"}, headers=_auth(seed, owner))
    assert r.status_code == 422
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_critical_path_api.py -q`
Expected: 4 passed。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/schemas/graph.py backend/app/cypher/graph.py backend/app/services/graph_service.py backend/app/routers/graph.py backend/app/main.py backend/tests/test_critical_path_api.py
git commit -m "feat: 关键路径三模式（impact/longest/manual）"
```

## Task 6: 子图渲染 `/graph` + 环检测 `/cycles`

**Files:**
- Modify: `backend/app/cypher/graph.py`
- Modify: `backend/app/services/graph_service.py`
- Modify: `backend/app/routers/graph.py`
- Test: `backend/tests/test_cycle_api.py`、`backend/tests/test_graph_query_api.py`（补子图用例）

- [ ] **Step 1: `backend/app/cypher/graph.py` 末尾加子图/环 Cypher**

```python
# 子图收集后回捞内部边的公共尾部
_SUBGRAPH_TAIL = (
    "WITH collect(DISTINCT n) AS ns "
    "UNWIND ns AS node "
    "OPTIONAL MATCH (node)-[r:DEPENDS_ON]->(other:LineageNode) WHERE other IN ns "
    "WITH ns, collect(DISTINCT r) AS rels "
    "RETURN [x IN ns | " + GNODE + "] AS nodes, "
    "[r IN rels | " + EDGE_FROM_REL + "] AS edges"
)

# __D__ 为 clamp 后的请求深度（服务层 replace）
SUBGRAPH_BOTH = (
    "MATCH (center:LineageNode {project_id: $pid, id: $center_id}) "
    "CALL { WITH center MATCH (center)-[:DEPENDS_ON*0..__D__]->(n:LineageNode) RETURN n "
    "UNION WITH center MATCH (center)<-[:DEPENDS_ON*0..__D__]-(n:LineageNode) RETURN n } "
    + _SUBGRAPH_TAIL
)
SUBGRAPH_UP = (
    "MATCH (center:LineageNode {project_id: $pid, id: $center_id}) "
    "MATCH (center)-[:DEPENDS_ON*0..__D__]->(n:LineageNode) " + _SUBGRAPH_TAIL
)
SUBGRAPH_DOWN = (
    "MATCH (center:LineageNode {project_id: $pid, id: $center_id}) "
    "MATCH (center)<-[:DEPENDS_ON*0..__D__]-(n:LineageNode) " + _SUBGRAPH_TAIL
)
FULL_GRAPH = (
    "MATCH (n:LineageNode {project_id: $pid}) " + _SUBGRAPH_TAIL
)

HAS_CYCLE = (
    "RETURN EXISTS { MATCH (n:LineageNode {project_id: $pid})"
    "-[:DEPENDS_ON*1..__DEPTH__]->(n) } AS has"
)
PROJECT_CYCLES = (
    "MATCH path=(n:LineageNode {project_id: $pid})-[:DEPENDS_ON*1..__DEPTH__]->(n) "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges LIMIT 50"
)
```

- [ ] **Step 2: `backend/app/services/graph_service.py` 加 subgraph/cycles**

顶部 import 区加：
```python
from app.config import get_settings
```

末尾追加：
```python
_SUBGRAPH_Q = {"upstream": q.SUBGRAPH_UP, "downstream": q.SUBGRAPH_DOWN, "both": q.SUBGRAPH_BOTH}


def _clamp_depth(d: int) -> int:
    return max(0, min(d, get_settings().max_traversal_depth))


def subgraph(repo: GraphRepo, pid: int, center: str | None, depth: int, direction: str) -> dict:
    if center is None:
        rows = repo.run_read(q.FULL_GRAPH, pid=pid)
    else:
        get_node(repo, pid, center)  # 404 if center missing
        cypher = _SUBGRAPH_Q[direction].replace("__D__", str(_clamp_depth(depth)))
        rows = repo.run_read(cypher, pid=pid, center_id=center)
    nodes = rows[0]["nodes"] if rows else []
    edges = [_coerce_edge(e) for e in (rows[0]["edges"] if rows else [])]
    has_cycle = repo.run_read(inline_depth(q.HAS_CYCLE), pid=pid)[0]["has"]
    return {
        "nodes": nodes, "edges": edges,
        "stats": {"node_count": len(nodes), "edge_count": len(edges), "has_cycle": has_cycle},
    }


def cycles(repo: GraphRepo, pid: int) -> list[dict]:
    rows = repo.run_read(inline_depth(q.PROJECT_CYCLES), pid=pid)
    return [_coerce_cycle(r) for r in rows]
```

- [ ] **Step 3: `backend/app/routers/graph.py` 加 2 个端点**

顶部 import 改为：
```python
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import (
    CriticalPathRequest,
    CriticalPathResponse,
    CycleResponse,
    GraphResponse,
)
from app.services import graph_service
```

末尾追加：
```python
@router.get("/graph", response_model=GraphResponse)
def get_subgraph(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    center: Annotated[str | None, Query()] = None,
    depth: Annotated[int, Query(ge=0, le=50)] = 2,
    direction: Annotated[Literal["upstream", "downstream", "both"], Query()] = "both",
) -> GraphResponse:
    return graph_service.subgraph(repo, ctx.project.id, center, depth, direction)


@router.get("/cycles", response_model=list[CycleResponse])
def get_cycles(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> list[CycleResponse]:
    return graph_service.cycles(repo, ctx.project.id)
```

- [ ] **Step 4: 写测试 `backend/tests/test_cycle_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _setup(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    ids = {}
    for nm in ["a", "b", "c"]:
        ids[nm] = client.post(f"/api/v1/projects/{p.id}/nodes",
                              json={"name": nm, "type": "t"},
                              headers=_auth(seed, owner)).json()["id"]
    return owner, p, ids


def _edge(client, seed, p, owner, s, t):
    return client.post(f"/api/v1/projects/{p.id}/edges",
                       json={"source_id": s, "target_id": t}, headers=_auth(seed, owner))


def test_creating_cycle_warns(client, seed):
    owner, p, ids = _setup(client, seed)
    _edge(client, seed, p, owner, ids["a"], ids["b"])
    _edge(client, seed, p, owner, ids["b"], ids["c"])
    # c -> a 制造环
    r = _edge(client, seed, p, owner, ids["c"], ids["a"])
    assert r.status_code == 201
    assert r.json()["warnings"]["creates_cycle"] is True


def test_cycles_endpoint_lists_cycle(client, seed):
    owner, p, ids = _setup(client, seed)
    _edge(client, seed, p, owner, ids["a"], ids["b"])
    _edge(client, seed, p, owner, ids["b"], ids["a"])
    r = client.get(f"/api/v1/projects/{p.id}/cycles", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert len(r.json()) >= 1
    names = {n["name"] for cyc in r.json() for n in cyc["nodes"]}
    assert {"a", "b"} <= names


def test_no_cycle_empty(client, seed):
    owner, p, ids = _setup(client, seed)
    _edge(client, seed, p, owner, ids["a"], ids["b"])
    r = client.get(f"/api/v1/projects/{p.id}/cycles", headers=_auth(seed, owner))
    assert r.json() == []
```

- [ ] **Step 5: 在 `backend/tests/test_graph_query_api.py` 末尾补子图用例**

```python
def test_subgraph_centered(client, seed):
    owner, p, ids = _setup_chain(client, seed)  # a->b->c->d
    r = client.get(f"/api/v1/projects/{p.id}/graph?center={ids['b']}&depth=1&direction=both",
                   headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    # depth1 both：b 自身 + 上游 c + 下游 a
    assert {n["name"] for n in body["nodes"]} == {"a", "b", "c"}
    assert body["stats"]["has_cycle"] is False


def test_subgraph_full_graph(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/graph", headers=_auth(seed, owner))
    body = r.json()
    assert body["stats"]["node_count"] == 4
    assert body["stats"]["edge_count"] == 3


def test_subgraph_direction_upstream(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/graph?center={ids['a']}&depth=15&direction=upstream",
                   headers=_auth(seed, owner))
    # a 的上游 b,c,d + a 自身
    assert {n["name"] for n in r.json()["nodes"]} == {"a", "b", "c", "d"}
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_cycle_api.py tests/test_graph_query_api.py -q`
Expected: 全绿（cycle 3 + graph_query 8）。

- [ ] **Step 7: 全量回归**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher/graph.py backend/app/services/graph_service.py backend/app/routers/graph.py backend/tests/test_cycle_api.py backend/tests/test_graph_query_api.py
git commit -m "feat: 子图渲染与环检测（建边成环预警已在边CRUD）"
```

## Task 7: 图端点权限矩阵扩展 + DoD

**Files:**
- Modify: `backend/tests/test_graph_permission_matrix.py`

- [ ] **Step 1: 在 `backend/tests/test_graph_permission_matrix.py` 末尾追加边写权限矩阵**

```python
# 边写需 editor+，图读 viewer+
EDGE_MATRIX = [
    ("owner", 201, 200),
    ("admin", 201, 200),
    ("editor", 201, 200),
    ("viewer", 403, 200),
]


@pytest.mark.parametrize("role,write_code,read_code", EDGE_MATRIX, ids=[r[0] for r in EDGE_MATRIX])
def test_edge_endpoints_by_role(client, seed, role, write_code, read_code):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)

    # owner 准备 schema + 两节点
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    a = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    b = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "b", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]

    # 写边
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b}, headers=_auth(seed, caller))
    assert r.status_code == write_code

    # 读边列表
    r = client.get(f"/api/v1/projects/{p.id}/edges", headers=_auth(seed, caller))
    assert r.status_code == read_code


@pytest.mark.parametrize("role", [r[0] for r in EDGE_MATRIX])
def test_graph_query_reads_allow_all_members(client, seed, role):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)
    # 图查询读端点对全员 200
    assert client.get(f"/api/v1/projects/{p.id}/graph", headers=_auth(seed, caller)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/cycles", headers=_auth(seed, caller)).status_code == 200
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "impact"}, headers=_auth(seed, caller))
    assert r.status_code == 200
```

- [ ] **Step 2: 运行权限矩阵测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_graph_permission_matrix.py -q`
Expected: 全绿（3A 的 schema/node 矩阵 + 本次 edge 矩阵：8 + 8）。

- [ ] **Step 3: 全量回归 + DoD 验证**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿（Phase 1+2+3A+3B 无回归）。

- [ ] **Step 4: 真实 Neo4j 端到端 smoke（DoD）**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8 && docker compose up -d neo4j
# 等就绪
for i in $(seq 1 30); do docker compose exec -T neo4j cypher-shell -u neo4j -p neo4jpassword "RETURN 1" >/dev/null 2>&1 && break; sleep 10; done
cd backend && . .venv/bin/activate && python -m scripts.init_neo4j_constraints
```
Expected: 打印 "Neo4j 约束与索引已就绪"，无报错（确认 3B 未破坏约束脚本）。
然后 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8 && docker compose down -v`。

- [ ] **Step 5: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/tests/test_graph_permission_matrix.py
git commit -m "test: 边写端点权限矩阵 + 图查询读端点全员可读"
```

## Phase 3B 完成标准（Definition of Done）

- [ ] 全量 `pytest` 绿（Phase 1+2+3A+3B，无回归）。
- [ ] 完整流程走通：建节点 → 建边（含成环预警）→ 上游/下游（分页）/影响/关键路径（3 模式）/环检测/子图 → 改边 → 删边。
- [ ] 边 (source,target) 全局唯一（409 `EDGE_EXISTS`）、自环拒绝（422 `SELF_LOOP`）、端点不存在 404。
- [ ] 建边成环不报错，POST 响应 `warnings.creates_cycle=true`，边照建。
- [ ] `NodeResponse` 详情递归计数、列表/改邻居计数语义正确。
- [ ] 权限符合 spec §5.11（边写 editor+、图读 viewer+）。
- [ ] 可变长路径深度受 `max_traversal_depth` 上限约束。
- [ ] 错误响应符合 §8 信封（404/409/422）。

## 下一子项目预告（不在本计划内）

- 3C：SQL 解析导入（sqlglot），复用 edge_service/node_service。
- 3D：文件 JSON/CSV 导入导出。
- 3E：删项目状态机 + Neo4j 后台清理 + 归档项目写入守卫（见 [[phase3-archived-project-write-guard]]）。









