# 任务血缘工具 Phase 3D：文件导入导出（JSON 全图）— 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§5.8 文件导入导出、§8 错误处理）
**前置子项目：** Phase 3A（节点/schema/父子）、3B（边/图查询）、3C（SQL 导入，复用其 commit 风格）、3E（写守卫）

## 目标

项目全图 JSON 导出 + 导入（备份恢复 / 跨项目迁移）。复用 3A/3B/3C 的 node/edge/schema service。

## 范围

**做（master §5.8）：**
- `GET /projects/:pid/export`（viewer+）→ 全图 JSON `{schemas, nodes, edges}`，节点含 parent 名。
- `POST /projects/:pid/import`（editor+，require_active）→ JSON body 合并导入，返回汇总计数。

**不做（YAGNI / 留后续）：**
- CSV 格式（图结构用 CSV 表达别扭，易丢信息）。
- 布局/坐标（前端 X6 负责，不入库）。
- 跨项目自动改名去重（名冲突即复用）。

## 决策（已与用户确认）

- **只 JSON**：导入导出统一一个 JSON 对象。
- **合并语义**：schema/节点按 type_key/name 复用已有、不存在才建；边已存在跳过；返回汇总计数（与 3C commit 一致）。
- **引用用节点名**：边、父子引用都用节点 `name`（项目内唯一、跨项目可移植），不导出 UUID。
- **import 用 JSON body**（非 multipart）：与导出形态一致、可直接往返、易测；有意偏离 master 的 "form-data"。
- **包含父子层级**：导出 parent 节点名，导入重建 CHILD_OF。
- **权限**：export viewer+（读）；import editor+ 且 require_active=True（写，受 3E 守卫）。

## 复用 Phase 3A/3B/3C/3E

- `schema_service.list_schemas/get_schema/create_schema`、`node_service.list_nodes/create_node/set_parent`、`edge_service.list_edges/create_edge`。
- `cypher/nodes.GET_BY_NAME`（3C 加）做名→id。
- 3C 的"名→id 映射 + 捕获 409/422 跳过"编排模式。
- 3E 的 `require_role(..., require_active=True)` 守卫（import 写）。

## 1. 文件结构

| 文件 | 新建/改 | 职责 |
|------|--------|------|
| `app/schemas/graph_io.py` | 新建 | `ExportNode`/`ExportEdge`/`ExportResponse`、`ImportRequest`/`ImportResponse` |
| `app/services/graph_io_service.py` | 新建 | `export_graph(repo, pid)` + `import_graph(repo, pid, uid, payload)` |
| `app/routers/graph_io.py` | 新建 | export/import 两端点 |
| `app/main.py` | 改 | 注册路由（sql_import 之后） |
| `tests/test_graph_io_api.py` | 新建 | 导出形态、往返、合并幂等、父子重建、权限、坏数据 |

复用现成：`cypher/nodes.GET_BY_NAME`、各 service 函数，无需新 cypher。

## 2. Pydantic 模型（`schemas/graph_io.py`）

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
    parent: str | None = None  # 父节点名


class ExportEdge(BaseModel):
    source: str = Field(min_length=1)  # 节点名
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

> Import/Export 共用 `ExportSchema`/`ExportNode`/`ExportEdge`，保证往返同构。

## 3. 导出 `export_graph(repo, pid)`（只读）

```
schemas = schema_service.list_schemas(repo, pid)        # 已是 {type_key, display_name, fields}
nodes_raw = node_service.list_nodes(repo, pid, {})       # 全 NodeResponse dict（含 id/parent_id/...）
edges_raw = edge_service.list_edges(repo, pid, {})       # 含 source_id/target_id (UUID)
id2name = {n["id"]: n["name"] for n in nodes_raw}
nodes = [{
  "name","type","description","owner","department","system","priority",
  "tags","ext_props","is_critical",
  "parent": id2name.get(n["parent_id"]) if n["parent_id"] else None,
} for n in sorted(nodes_raw, key=lambda x: x["name"])]
edges = [{
  "source": id2name[e["source_id"]], "target": id2name[e["target_id"]],
  "edge_type","description","is_required","strength","ext_props",
} for e in edges_raw]
return {"schemas":[...], "nodes": nodes, "edges": edges}
```
- 不导出 UUID/时间戳/created_by（非可移植/非数据本体）。
- 节点按 name 排序，导出稳定（可 diff/快照测试）。

## 4. 导入 `import_graph(repo, pid, uid, payload)`（顺序敏感）

```
created_schemas = reused_schemas = created_nodes = reused_nodes = 0
set_parents = created_edges = skipped_edges = 0
name_to_id = {}

# 1. schemas（先建，保证节点 type 有 schema）
for s in payload["schemas"]:
    try:
        schema_service.get_schema(repo, pid, s["type_key"]); reused_schemas += 1
    except NotFoundError:
        schema_service.create_schema(repo, pid, s["type_key"], s["display_name"], s["fields"])
        created_schemas += 1

# 2. nodes
for n in payload["nodes"]:
    existing = repo.run_read(nq.GET_BY_NAME, pid=pid, name=n["name"])
    if existing:
        name_to_id[n["name"]] = existing[0]["id"]; reused_nodes += 1
        continue
    node = node_service.create_node(repo, pid, uid, {
        "name","type","description","owner","department","system","priority",
        "tags","ext_props","is_critical"})  # 从 n 取
    name_to_id[n["name"]] = node["id"]; created_nodes += 1

# 3. parents
for n in payload["nodes"]:
    if not n.get("parent"):
        continue
    child = name_to_id.get(n["name"]) or _find(pid, n["name"])
    parent = name_to_id.get(n["parent"]) or _find(pid, n["parent"])
    if not child or not parent:
        continue
    try:
        node_service.set_parent(repo, pid, child, parent); set_parents += 1
    except (ValidationError, NotFoundError):
        pass  # 成环/自环/缺失 → 跳过

# 4. edges
for e in payload["edges"]:
    sid = name_to_id.get(e["source"]) or _find(pid, e["source"])
    tid = name_to_id.get(e["target"]) or _find(pid, e["target"])
    if not sid or not tid:
        skipped_edges += 1; continue
    try:
        edge_service.create_edge(repo, pid, uid, {"source_id":sid,"target_id":tid,
            "edge_type":e["edge_type"],"description":e["description"],
            "is_required":e["is_required"],"strength":e["strength"],"ext_props":e["ext_props"]})
        created_edges += 1
    except (ConflictError, ValidationError):
        skipped_edges += 1

logger.info("graph.import pid=%s by=%s ...", pid, uid, ...)
return {7 个计数}
```
`_find(pid, name)` = `repo.run_read(nq.GET_BY_NAME, pid=pid, name=name)` → id or None。
非事务（与 3C/3E 一致），中途失败已写留存，可重导（合并幂等）。

## 5. 路由（`graph_io.py`）

```python
router = APIRouter(prefix="/api/v1/projects/{pid}", tags=["graph-io"])

@router.get("/export", response_model=ExportResponse)   # require_role(viewer)
@router.post("/import", response_model=ImportResponse)  # require_role(editor, require_active=True)
```
main.py 在 sql_import_router 之后注册。

## 6. 错误处理（§8 信封）

| 场景 | 处理 |
|------|------|
| JSON body 结构非法（缺必填 name/type） | Pydantic 422 |
| 节点 type 既不在 payload.schemas 也不在项目 | create_node → 422（中途中止，部分写留存）|
| 父子成环/自环/父缺失 | 跳过该 set_parent |
| 边重/自环/端点缺失 | 跳过该边 |
| import 非 editor / 项目非 active | 403 / 409 PROJECT_NOT_ACTIVE |
| export 非成员 | 403 |

## 7. 测试（`test_graph_io_api.py`，testcontainers）

- **导出形态**：建 schema + 父子节点(parent) + 边 → GET export，断言：节点用 name 无 uuid、parent 是名、edges 用名、schemas 完整、节点按名排序。
- **往返**：项目 A 建图 → export → POST import 到空项目 B → B 的 schemas/节点/边/父子与 A 一致（created 计数）。
- **合并幂等**：同 payload 二次导入同项目 → created 全 0、reused/skipped 命中。
- **父子重建**：导入后 GET 子节点详情 `parent_id` 正确。
- **跳过**：payload 含重复边 + 引用不存在父 → skipped_edges>0、set_parents 不计缺失。
- **权限**：export viewer 200；import viewer 403；import 到 archived 项目 409 PROJECT_NOT_ACTIVE。
- **坏数据**：缺 node.name → 422。

## Definition of Done

- 全量 `pytest` 绿（Phase 1+2+3A+3B+3C+3E+3D，无回归）。
- export→import 往返保真（schemas/nodes/edges/父子）。
- 合并幂等（二次导入零新建）。
- export viewer+ / import editor+active。
- 错误符合 §8 信封（422/403/409）。

## 下一阶段预告（不在本计划内）

- 前端：Vue3 + Pinia + AntV X6 画布、属性面板、影响分析、SQL 导入入口、导入导出入口、项目/成员管理。
- 至此后端功能全部完成（认证/RBAC/节点/边/图查询/SQL导入/删项目清理/文件导入导出）。

