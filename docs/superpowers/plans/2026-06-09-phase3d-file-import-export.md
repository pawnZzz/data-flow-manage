# 任务血缘工具 Phase 3D：文件导入导出（JSON 全图）— Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 项目全图 JSON 导出（节点名引用、含父子）+ 合并导入（复用/跳过，返回汇总），复用 3A/3B/3C service。

**Architecture:** 薄路由 + `graph_io_service`（export 只读拼装、import 编排 schemas→nodes→parents→edges）。引用全用节点名，导入复用 3C 的"名→id + 捕获 409/422 跳过"模式，非事务可重导。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、neo4j、pytest、testcontainers。

参考 spec：`docs/superpowers/specs/2026-06-09-phase3d-file-import-export-design.md`。

---

## File Structure

- `backend/app/schemas/graph_io.py` — 新建：Export*/Import* 模型。
- `backend/app/services/graph_io_service.py` — 新建：`export_graph`、`import_graph`。
- `backend/app/routers/graph_io.py` — 新建：export/import 两端点。
- `backend/app/main.py` — 改：注册路由（sql_import 之后）。
- `backend/tests/test_schemas_graph_io.py` — 新建：纯单元（模型）。
- `backend/tests/test_graph_io_api.py` — 新建：集成（往返/幂等/权限）。

复用现成：`schema_service.{list_schemas,get_schema,create_schema}`、`node_service.{list_nodes,create_node,set_parent}`、`edge_service.{list_edges,create_edge}`、`cypher/nodes.GET_BY_NAME`。无需新 cypher。

约定：命令在 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/backend && . .venv/bin/activate` 下跑；commit 在仓库根，message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## Task 1: 模型 + 导出（schemas + export_graph + GET /export）

**Files:**
- Create: `backend/app/schemas/graph_io.py`
- Create: `backend/app/services/graph_io_service.py`
- Create: `backend/app/routers/graph_io.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_schemas_graph_io.py`, `backend/tests/test_graph_io_api.py`

- [ ] **Step 1: 写失败单元测试 `backend/tests/test_schemas_graph_io.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.graph_io import ExportNode, ImportRequest


def test_export_node_defaults():
    n = ExportNode(name="dw.t", type="t")
    assert n.parent is None
    assert n.tags == [] and n.ext_props == {} and n.is_critical is False


def test_export_node_requires_name():
    with pytest.raises(ValidationError):
        ExportNode(name="", type="t")


def test_import_request_defaults_empty():
    r = ImportRequest()
    assert r.schemas == [] and r.nodes == [] and r.edges == []
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_schemas_graph_io.py -q` → ModuleNotFoundError。

- [ ] **Step 3: 创建 `backend/app/schemas/graph_io.py`**

```python
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.graph import SchemaFieldSpec


class ExportSchema(BaseModel):
    type_key: str
    display_name: str
    fields: list[SchemaFieldSpec] = []


class ExportNode(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    description: str | None = None
    owner: str | None = None
    department: str | None = None
    system: str | None = None
    priority: str | None = None
    tags: list[str] = []
    ext_props: dict[str, Any] = {}
    is_critical: bool = False
    parent: str | None = None


class ExportEdge(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    edge_type: str = "data_flow"
    description: str | None = None
    is_required: bool = True
    strength: str = "strong"
    ext_props: dict[str, Any] = {}


class ExportResponse(BaseModel):
    schemas: list[ExportSchema]
    nodes: list[ExportNode]
    edges: list[ExportEdge]


class ImportRequest(BaseModel):
    schemas: list[ExportSchema] = []
    nodes: list[ExportNode] = []
    edges: list[ExportEdge] = []


class ImportResponse(BaseModel):
    created_schemas: int
    reused_schemas: int
    created_nodes: int
    reused_nodes: int
    set_parents: int
    created_edges: int
    skipped_edges: int
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_schemas_graph_io.py -q` → expect 3 passed。

- [ ] **Step 5: 创建 `backend/app/services/graph_io_service.py`（先只 export）**

```python
import logging

from app.repositories.graph_repo import GraphRepo
from app.services import edge_service, node_service, schema_service

logger = logging.getLogger("app.audit")

_NODE_KEYS = [
    "name", "type", "description", "owner", "department", "system",
    "priority", "tags", "ext_props", "is_critical",
]
_EDGE_KEYS = ["edge_type", "description", "is_required", "strength", "ext_props"]


def export_graph(repo: GraphRepo, pid: int) -> dict:
    schemas = schema_service.list_schemas(repo, pid)
    nodes_raw = node_service.list_nodes(repo, pid, {})
    edges_raw = edge_service.list_edges(repo, pid, {})
    id2name = {n["id"]: n["name"] for n in nodes_raw}

    nodes = []
    for n in sorted(nodes_raw, key=lambda x: x["name"]):
        item = {k: n[k] for k in _NODE_KEYS}
        item["parent"] = id2name.get(n["parent_id"]) if n.get("parent_id") else None
        nodes.append(item)

    edges = []
    for e in edges_raw:
        item = {k: e[k] for k in _EDGE_KEYS}
        item["source"] = id2name[e["source_id"]]
        item["target"] = id2name[e["target_id"]]
        edges.append(item)

    return {"schemas": schemas, "nodes": nodes, "edges": edges}
```

- [ ] **Step 6: 创建 `backend/app/routers/graph_io.py`（先只 export）**

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph_io import ExportResponse
from app.services import graph_io_service

router = APIRouter(prefix="/api/v1/projects/{pid}", tags=["graph-io"])


@router.get("/export", response_model=ExportResponse)
def export_graph(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> ExportResponse:
    return graph_io_service.export_graph(repo, ctx.project.id)
```

- [ ] **Step 7: 注册路由 `backend/app/main.py`**

在 `app.include_router(sql_import_router.router)` 之后追加：
```python
    from app.routers import graph_io as graph_io_router

    app.include_router(graph_io_router.router)
```

- [ ] **Step 8: 写导出集成测试 `backend/tests/test_graph_io_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _build_graph(client, seed):
    """schema t + 节点 a/b/child(parent=a) + 边 a->b，返回 (owner, p)。"""
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    for nm in ["a", "b", "child"]:
        client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": nm, "type": "t"},
                    headers=_auth(seed, owner))
    # child 的父设为 a（按 id）
    ids = {n["name"]: n["id"] for n in
           client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, owner)).json()}
    client.post(f"/api/v1/projects/{p.id}/nodes/{ids['child']}/parent",
                json={"parent_id": ids["a"]}, headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": ids["a"], "target_id": ids["b"]}, headers=_auth(seed, owner))
    return owner, p


def test_export_shape(client, seed):
    owner, p = _build_graph(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert {s["type_key"] for s in body["schemas"]} == {"t"}
    names = [n["name"] for n in body["nodes"]]
    assert names == sorted(names)  # 按名排序
    # 无 uuid 字段泄漏
    assert all("id" not in n for n in body["nodes"])
    child = next(n for n in body["nodes"] if n["name"] == "child")
    assert child["parent"] == "a"   # 父用名
    assert {"source": "a", "target": "b"} == {k: body["edges"][0][k] for k in ("source", "target")}


def test_export_requires_member(client, seed):
    owner = seed.user("owner"); outsider = seed.user("outsider")
    p = seed.project(owner)
    r = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, outsider))
    assert r.status_code == 403
```

- [ ] **Step 9: 运行确认通过**

Run: `pytest tests/test_graph_io_api.py -q` → expect 2 passed。

- [ ] **Step 10: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/schemas/graph_io.py backend/app/services/graph_io_service.py backend/app/routers/graph_io.py backend/app/main.py backend/tests/test_schemas_graph_io.py backend/tests/test_graph_io_api.py
git commit -m "feat: 全图 JSON 导出（节点名引用、含父子）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 2: 导入（import_graph + POST /import）

**Files:**
- Modify: `backend/app/services/graph_io_service.py`
- Modify: `backend/app/routers/graph_io.py`
- Test: `backend/tests/test_graph_io_api.py`（追加）

- [ ] **Step 1: 追加 import 编排到 `backend/app/services/graph_io_service.py`**

顶部 import 区改为：
```python
import logging

from app.cypher import nodes as nq
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.graph_repo import GraphRepo
from app.services import edge_service, node_service, schema_service
```

文件末尾追加：
```python
def _find_id(repo: GraphRepo, pid: int, name: str) -> str | None:
    rows = repo.run_read(nq.GET_BY_NAME, pid=pid, name=name)
    return rows[0]["id"] if rows else None


def import_graph(repo: GraphRepo, pid: int, uid: int, payload: dict) -> dict:
    created_schemas = reused_schemas = 0
    created_nodes = reused_nodes = set_parents = 0
    created_edges = skipped_edges = 0
    name_to_id: dict[str, str] = {}

    # 1. schemas（先建，保证节点 type 有 schema）
    for s in payload["schemas"]:
        try:
            schema_service.get_schema(repo, pid, s["type_key"])
            reused_schemas += 1
        except NotFoundError:
            schema_service.create_schema(repo, pid, s["type_key"], s["display_name"], s["fields"])
            created_schemas += 1

    # 2. nodes
    for n in payload["nodes"]:
        existing = _find_id(repo, pid, n["name"])
        if existing:
            name_to_id[n["name"]] = existing
            reused_nodes += 1
            continue
        node = node_service.create_node(repo, pid, uid, {
            "name": n["name"], "type": n["type"], "description": n["description"],
            "owner": n["owner"], "department": n["department"], "system": n["system"],
            "priority": n["priority"], "tags": n["tags"], "ext_props": n["ext_props"],
            "is_critical": n["is_critical"],
        })
        name_to_id[n["name"]] = node["id"]
        created_nodes += 1

    # 3. parents
    for n in payload["nodes"]:
        if not n.get("parent"):
            continue
        child = name_to_id.get(n["name"]) or _find_id(repo, pid, n["name"])
        parent = name_to_id.get(n["parent"]) or _find_id(repo, pid, n["parent"])
        if not child or not parent:
            continue
        try:
            node_service.set_parent(repo, pid, child, parent)
            set_parents += 1
        except (ValidationError, NotFoundError):
            pass  # 成环/自环/缺失 → 跳过

    # 4. edges
    for e in payload["edges"]:
        sid = name_to_id.get(e["source"]) or _find_id(repo, pid, e["source"])
        tid = name_to_id.get(e["target"]) or _find_id(repo, pid, e["target"])
        if not sid or not tid:
            skipped_edges += 1
            continue
        try:
            edge_service.create_edge(repo, pid, uid, {
                "source_id": sid, "target_id": tid, "edge_type": e["edge_type"],
                "description": e["description"], "is_required": e["is_required"],
                "strength": e["strength"], "ext_props": e["ext_props"],
            })
            created_edges += 1
        except (ConflictError, ValidationError):
            skipped_edges += 1

    logger.info("graph.import pid=%s by=%s created_nodes=%s created_edges=%s",
                pid, uid, created_nodes, created_edges)
    return {
        "created_schemas": created_schemas, "reused_schemas": reused_schemas,
        "created_nodes": created_nodes, "reused_nodes": reused_nodes,
        "set_parents": set_parents,
        "created_edges": created_edges, "skipped_edges": skipped_edges,
    }
```

- [ ] **Step 2: 追加 import 端点到 `backend/app/routers/graph_io.py`**

顶部 import 改为：
```python
from app.schemas.graph_io import ExportResponse, ImportRequest, ImportResponse
```
末尾追加：
```python
@router.post("/import", response_model=ImportResponse)
def import_graph(
    payload: ImportRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor, require_active=True))],
    repo: GraphRepoDep,
) -> ImportResponse:
    return graph_io_service.import_graph(repo, ctx.project.id, ctx.user.id, payload.model_dump())
```

- [ ] **Step 3: 追加导入集成测试到 `backend/tests/test_graph_io_api.py`**

```python
def test_roundtrip_export_import(client, seed):
    owner, p = _build_graph(client, seed)
    exported = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, owner)).json()
    # 导入到全新空项目 B
    p2 = seed.project(owner, name="proj2")
    r = client.post(f"/api/v1/projects/{p2.id}/import", json=exported, headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert body["created_schemas"] == 1
    assert body["created_nodes"] == 3
    assert body["created_edges"] == 1
    assert body["set_parents"] == 1
    # B 的图与 A 同构
    exported2 = client.get(f"/api/v1/projects/{p2.id}/export", headers=_auth(seed, owner)).json()
    assert {n["name"] for n in exported2["nodes"]} == {"a", "b", "child"}
    child2 = next(n for n in exported2["nodes"] if n["name"] == "child")
    assert child2["parent"] == "a"
    assert exported2["edges"][0]["source"] == "a" and exported2["edges"][0]["target"] == "b"


def test_import_merge_idempotent(client, seed):
    owner, p = _build_graph(client, seed)
    exported = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, owner)).json()
    # 导回同项目：全部已存在
    r = client.post(f"/api/v1/projects/{p.id}/import", json=exported, headers=_auth(seed, owner))
    body = r.json()
    assert body["created_schemas"] == 0 and body["reused_schemas"] == 1
    assert body["created_nodes"] == 0 and body["reused_nodes"] == 3
    assert body["created_edges"] == 0 and body["skipped_edges"] == 1


def test_import_skips_dup_edge_and_missing_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    payload = {
        "schemas": [{"type_key": "t", "display_name": "T", "fields": []}],
        "nodes": [
            {"name": "a", "type": "t", "description": None, "owner": None,
             "department": None, "system": None, "priority": None, "tags": [],
             "ext_props": {}, "is_critical": False, "parent": "ghost"},  # 父不存在
            {"name": "b", "type": "t", "description": None, "owner": None,
             "department": None, "system": None, "priority": None, "tags": [],
             "ext_props": {}, "is_critical": False, "parent": None},
        ],
        "edges": [
            {"source": "a", "target": "b", "edge_type": "data_flow", "description": None,
             "is_required": True, "strength": "strong", "ext_props": {}},
            {"source": "a", "target": "b", "edge_type": "data_flow", "description": None,
             "is_required": True, "strength": "strong", "ext_props": {}},  # 重复
            {"source": "a", "target": "ghost", "edge_type": "data_flow", "description": None,
             "is_required": True, "strength": "strong", "ext_props": {}},  # 端点缺失
        ],
    }
    r = client.post(f"/api/v1/projects/{p.id}/import", json=payload, headers=_auth(seed, owner))
    body = r.json()
    assert body["created_nodes"] == 2
    assert body["set_parents"] == 0          # ghost 父缺失，跳过
    assert body["created_edges"] == 1        # 第一条
    assert body["skipped_edges"] == 2        # 重复 + 端点缺失


def test_import_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer")
    r = client.post(f"/api/v1/projects/{p.id}/import",
                    json={"schemas": [], "nodes": [], "edges": []}, headers=_auth(seed, viewer))
    assert r.status_code == 403


def test_import_blocked_on_archived(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))  # archive
    r = client.post(f"/api/v1/projects/{p.id}/import",
                    json={"schemas": [], "nodes": [], "edges": []}, headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ACTIVE"


def test_import_bad_data_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/import",
                    json={"nodes": [{"type": "t"}]}, headers=_auth(seed, owner))  # 缺 name
    assert r.status_code == 422
```

- [ ] **Step 4: 运行导入测试**

Run: `pytest tests/test_graph_io_api.py -q` → expect 8 passed（2 导出 + 6 导入）。

- [ ] **Step 5: 全量回归**

Run: `pytest -q 2>&1 | tail -3` → expect all green。

- [ ] **Step 6: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/services/graph_io_service.py backend/app/routers/graph_io.py backend/tests/test_graph_io_api.py
git commit -m "feat: 全图 JSON 导入（schemas→nodes→parents→edges 合并，复用/跳过）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Phase 3D 完成标准（Definition of Done）

- [ ] 全量 `pytest` 绿（Phase 1+2+3A+3B+3C+3E+3D，无回归）。
- [ ] export→import 往返保真（schemas/nodes/edges/父子同构）。
- [ ] 合并幂等（二次导入零新建、全 reused/skipped）。
- [ ] export viewer+ / import editor+ 且 require_active（archived → 409）。
- [ ] 引用全用节点名、不泄漏 UUID；节点按名排序。
- [ ] 错误符合 §8（422 坏数据、403 权限、409 归档）。

## 下一阶段预告（不在本计划内）

- 前端：Vue3 + Pinia + AntV X6。后端功能至此全部完成。


