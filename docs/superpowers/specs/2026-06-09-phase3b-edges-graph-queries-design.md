# 任务血缘工具 Phase 3B：依赖边 + 图查询/算法 — 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§4.2 边模型、§5.5 边 API、§5.6 图查询、§6 图算法、§8 错误处理）
**前置子项目：** Phase 3A（Neo4j 基座 + 节点 Schema + 节点 CRUD + 父子）`docs/superpowers/specs/2026-06-08-phase3a-neo4j-nodes-schema-design.md`

## 目标

在 3A（节点 + 父子）之上加依赖边 `:DEPENDS_ON` 与全部图查询/算法，让用户能在图上维护依赖并做变更影响分析（上下游追溯、关键路径、环检测、子图渲染）。

## 范围

**做（master design §5.5/5.6/6）：**
- 依赖边 `:DEPENDS_ON` CRUD：建/列/取/改/删。
- `NodeResponse` 补 `upstream_count`/`downstream_count`（详情递归全传递、列表直接邻居）。
- 节点级遍历：`/nodes/:nid/upstream`、`/downstream`（分页）、`/impact`。
- 项目级图查询：`/graph`（子图渲染）、`/cycles`（环检测）、`/critical-paths`（3 模式）。
- 建边成环不阻止，POST 响应带 `warnings.creates_cycle`。

**不做（YAGNI / 留后续子项目）：**
- SQL 解析导入（3C）、文件导入导出（3D）。
- 删项目 `deleting` 状态机 + Neo4j 后台清理 + 归档项目写入守卫（3E，见 [[phase3-archived-project-write-guard]]）。
- 边的图布局/坐标（前端 X6 dagre 负责，不入库）。

## 复用 Phase 1/2/3A

- `AppError` 体系与 §8 错误信封；`require_role(min_role)` / `ProjectContext` / `GraphRepoDep`。
- 分层 routers → services → cypher/；testcontainers fixture + `seed`/`client` helper。
- 3A 的 `graph_repo`、`cypher/` 目录、`schemas/graph.py`、节点模型与 `_coerce_datetimes`/`_row_to_node` 模式。
- config 已有 `max_traversal_depth: int = 15`。

## 架构决策

沿用 3A 的**仓储层 + 服务层 + Cypher 集中**（方案 A）：
- `app/cypher/edges.py` + `app/cypher/graph.py` 集中 Cypher 串，与 Python 解耦、便于单独 review。
- 服务层做业务逻辑（UUID 生成、唯一性、成环预警、审计、分页 total 计算）。
- 所有图算法**单条 Cypher 直出，不引入 GDS 库**（保持依赖轻量，master §6 前提）。
- 可变长路径硬上限：`*1..N` 的 N 从 config `max_traversal_depth` 读，Python 内联进 Cypher 串（Neo4j 不支持把变长上界参数化）。

**边唯一性落地：** Neo4j 5 Community 的关系唯一约束只能约束单个关系属性值（如 `r.id`），**无法表达 (source,target) 对唯一**（参 https://neo4j.com/docs/cypher-manual/5/constraints/syntax/ 与 https://neo4j.com/docs/cypher-manual/4.4/constraints/ 的 Community/Enterprise 划分）。因此 (source,target) 全局唯一由**服务层**用一条「条件 CREATE」Cypher（`WHERE NOT (s)-[:DEPENDS_ON]->(t)`，已存在则返回 0 行 → 服务判 409）保证。与 3A schema create 的 pre-check 风格一致。此处存在极小 TOCTOU 窗口，在本工具中等规模、单写场景下可接受。

**方向约定（master §5.5）：** `(source)-[:DEPENDS_ON]->(target)` 表示 **source 依赖 target**。source=依赖方（下游），target=被依赖方（上游）。
- 「节点 X 的上游」= X 依赖的、沿出边 `*1..N` 递归可达的节点。
- 「节点 X 的下游」= 依赖 X 的、沿入边 `*1..N` 递归可达的节点。

## 1. 文件结构

| 文件 | 新建/改 | 职责 |
|------|--------|------|
| `app/cypher/edges.py` | 新建 | 边 CRUD Cypher（条件 CREATE、列表过滤、GET/UPDATE/DELETE、EXISTS） |
| `app/cypher/graph.py` | 新建 | 遍历（上/下游+count）、子图、关键路径 3 模式、环检测、邻居计数 Cypher |
| `app/schemas/graph.py` | 改 | 加 Edge*/Graph*/Impact*/CriticalPath*/Cycle* 模型；NodeResponse 加两计数 |
| `app/services/edge_service.py` | 新建 | 边 CRUD + 唯一性 + 成环预警 + 审计日志 |
| `app/services/graph_service.py` | 新建 | 上/下游遍历（分页）、impact、子图、关键路径、环检测 |
| `app/services/node_service.py` | 改 | GET 递归计数、LIST 邻居计数（改 GET/LIST Cypher 与 `_row_to_node`） |
| `app/cypher/nodes.py` | 改 | GET 加递归 up/down count；LIST 加邻居 up/down count |
| `app/routers/edges.py` | 新建 | `/projects/:pid/edges` 系列端点 |
| `app/routers/graph.py` | 新建 | `/projects/:pid/graph`、`/cycles`、`/critical-paths` |
| `app/routers/nodes.py` | 改 | 加 `/:nid/upstream`、`/downstream`、`/impact` |
| `app/main.py` | 改 | 注册 edges + graph 路由 |
| `tests/test_edge_api.py` | 新建 | 边 CRUD/冲突/自环/过滤/权限 |
| `tests/test_graph_query_api.py` | 新建 | 上下游/分页/impact/子图/stats |
| `tests/test_critical_path_api.py` | 新建 | 3 模式 + 非法 mode |
| `tests/test_cycle_api.py` | 新建 | 环检测 + 建边成环预警 |
| `tests/test_node_counts.py` | 新建 | 详情递归计数 vs 列表邻居计数 |
| `tests/test_graph_permission_matrix.py` | 改 | 扩展边写端点 × 角色 |

## 2. 边数据模型（master §4.2）

```cypher
(:LineageNode)-[:DEPENDS_ON {
  id:          string,   // 边 UUID
  edge_type:   string,   // trigger | data_flow | api_call | custom
  description: string?,
  is_required: boolean,  // 必需依赖 vs 软依赖，默认 true
  strength:    string,   // strong | weak，默认 strong
  ext_props:   string,   // JSON 串（与节点 ext_props 一致的序列化方式）
  created_at:  datetime,
  created_by:  integer
}]->(:LineageNode)
```

边不做 per-type schema 校验（节点才有 schema；边的 ext_props 自由）。`edge_type`/`strength` 用 Pydantic `Literal` 限定取值。`ext_props` 存 Neo4j 时序列化为 JSON 串、读出反序列化（沿用 3A 节点 `json.dumps`/`json.loads` 模式）；`created_at` 用 `.to_native()` 转 Python datetime（沿用 3A `_coerce_datetimes`）。

## 3. API 与权限

写 editor+、读 viewer+，统一走 `require_role`（在 FastAPI dependency 里，不散落业务代码）。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/projects/:pid/edges` | viewer | query: `source_id`/`target_id`/`edge_type` 可选过滤 |
| POST | `/projects/:pid/edges` | editor | body `CreateEdgeRequest`；返回 `CreateEdgeResponse`（含 warnings） |
| GET | `/projects/:pid/edges/:eid` | viewer | 边详情 |
| PATCH | `/projects/:pid/edges/:eid` | editor | 改 edge_type/description/is_required/strength/ext_props（端点不可改） |
| DELETE | `/projects/:pid/edges/:eid` | editor | 删边 |
| GET | `/projects/:pid/nodes/:nid/upstream` | viewer | 递归上游，query `limit`(默认200)/`offset`(默认0) |
| GET | `/projects/:pid/nodes/:nid/downstream` | viewer | 递归下游，分页同上 |
| GET | `/projects/:pid/nodes/:nid/impact` | viewer | `{upstream, downstream, warnings:{cycles}}` |
| GET | `/projects/:pid/graph` | viewer | query `center?`/`depth`(默认2)/`direction`(upstream\|downstream\|both，默认 both)；无 center 返回全图 |
| GET | `/projects/:pid/cycles` | viewer | 环检测列表 |
| POST | `/projects/:pid/critical-paths` | viewer | body `{mode: impact\|longest\|manual, node_ids?}` |

> 节点级遍历端点放 `routers/nodes.py`（路径在 `/nodes/:nid` 下）；项目级图查询放 `routers/graph.py`。

## 4. Pydantic 模型（加到 `schemas/graph.py`）

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

class GraphNode(BaseModel):  # 子图精简节点，不带递归计数
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

class Page(BaseModel):  # 分页信封
    items: list[NodeResponse]
    total: int
    limit: int
    offset: int

class CycleResponse(BaseModel):  # 单个环
    nodes: list[GraphNode]
    edges: list[EdgeResponse]

# GET /cycles 返回 list[CycleResponse]

class ImpactResponse(BaseModel):
    upstream: list[NodeResponse]
    downstream: list[NodeResponse]
    warnings: dict  # {"cycles": list[CycleResponse]}（该节点参与的环，无则空列表）

class PathItem(BaseModel):
    nodes: list[GraphNode]
    edges: list[EdgeResponse]
    depth: int
    score: int | None = None  # impact 模式带影响面分数

class CriticalPathResponse(BaseModel):
    mode: str
    paths: list[PathItem]
```

`NodeResponse` 追加：`upstream_count: int = 0`、`downstream_count: int = 0`。

**计数语义：** `GET /nodes/:nid`（详情）= 递归全传递计数（`count(DISTINCT)`，与 master 示例 5/12 一致）；`GET /nodes`（列表）= 直接邻居出/入度（`size((n)-[:DEPENDS_ON]->())` / `size((n)<-[:DEPENDS_ON]-())`），避免每行一次变长遍历。

## 5. 图算法实现（全部单条 Cypher）

`N` = `max_traversal_depth`（默认 15），由服务层用字符串格式化内联进 Cypher（变长上界不能参数化；N 来自可信 config，非用户输入，无注入风险）。

### 5.1 边条件创建（唯一性 + 端点存在）

```cypher
MATCH (s:LineageNode {project_id:$pid, id:$source_id})
MATCH (t:LineageNode {project_id:$pid, id:$target_id})
WHERE NOT (s)-[:DEPENDS_ON]->(t)
CREATE (s)-[r:DEPENDS_ON {
  id:$id, edge_type:$edge_type, description:$description,
  is_required:$is_required, strength:$strength, ext_props:$ext_props,
  created_at:datetime(), created_by:$uid
}]->(t)
RETURN r, s.id AS source_id, t.id AS target_id
```

服务层 `create_edge` 流程：
1. `source_id == target_id` → `ValidationError` 422 `SELF_LOOP`。
2. `EXISTS` 验两端点都在本项目，缺则 `NotFoundError` 404。
3. 跑条件 CREATE；返回 0 行（两端点都在但边已存在）→ `ConflictError` 409 `EDGE_EXISTS`。
4. 建成后跑成环检测（§5.5 单点版）判 `creates_cycle`，写进 `CreateEdgeResponse.warnings`。
5. 审计：`logger("app.audit")` 记 `edge.create`。

### 5.2 上游 / 下游遍历（分页）

```cypher
-- 上游（X 依赖的递归祖先）；下游把箭头反向 <-[:DEPENDS_ON*1..N]-
MATCH (start:LineageNode {project_id:$pid, id:$nid})-[:DEPENDS_ON*1..N]->(m:LineageNode)
WITH DISTINCT m ORDER BY m.name
RETURN m SKIP $offset LIMIT $limit
```
`total` 用配套 `count(DISTINCT m)` 的 Cypher 单独取。两 query 放 `graph.py`，按 direction 选向。返回 `Page`（items 为完整 `NodeResponse`，但遍历结果节点的 count 用邻居计数填充以省遍历）。

### 5.3 影响分析 `/impact`

组合：上游（全量，到上限）+ 下游（全量）+ 该节点参与的环（§5.5 单点版）。返回 `ImpactResponse`。

### 5.4 关键路径 3 模式（master §6.2）

- `impact`（默认）：下游数最多的节点，取其最深下游链。
- `longest`：DAG 最长链（无入边起点 → 无出边终点），`ORDER BY length(path) DESC LIMIT 5`。
- `manual`：`is_critical:true` 节点两两间 `shortestPath`。

`POST /critical-paths` 按 `mode` 分发到对应 Cypher；非法 mode → `ValidationError` 422。

### 5.5 环检测（master §6.3）

```cypher
-- 项目全环
MATCH path=(n:LineageNode {project_id:$pid})-[:DEPENDS_ON*1..N]->(n)
RETURN nodes(path) AS cycle_nodes, relationships(path) AS cycle_edges LIMIT 50
-- 单点是否在环上（建边预警/impact 用）：把起点固定为某节点
-- has_cycle 轻量版：上面加 RETURN count(*)>0 ... LIMIT 1
```

### 5.6 子图渲染（master §6.5）

```cypher
MATCH (center:LineageNode {project_id:$pid, id:$center_id})
CALL {
  WITH center MATCH (center)-[:DEPENDS_ON*0..D]->(n) RETURN n
  UNION
  WITH center MATCH (center)<-[:DEPENDS_ON*0..D]-(n) RETURN n
}
WITH collect(DISTINCT n) AS ns
UNWIND ns AS node
OPTIONAL MATCH (node)-[r:DEPENDS_ON]->(other) WHERE other IN ns
RETURN ns AS nodes, collect(DISTINCT r) AS edges
```
`direction=upstream` 只保留出边分支（`CALL{}` 内仅 `(center)-[:DEPENDS_ON*0..D]->(n)`）、`downstream` 只入边分支、`both` 两分支 UNION（如上）。`D`=query `depth`（受 N 上限钳制）。无 `center` 时返回项目全部节点 + 全部边。`stats.has_cycle` 用轻量计数。

## 6. 错误处理（§8 信封）

| 场景 | 异常 → 码 |
|------|----------|
| source/target 节点不存在 | `NotFoundError` 404 `NOT_FOUND` |
| 边已存在（同 source→target） | `ConflictError` 409（details.code=`EDGE_EXISTS`） |
| 自环（source==target） | `ValidationError` 422（details.code=`SELF_LOOP`） |
| 边 id 不存在（GET/PATCH/DELETE） | `NotFoundError` 404 |
| edge_type/strength 非法 | Pydantic `RequestValidationError` 422 |
| 建边成环 | **不报错**，POST 响应 `warnings.creates_cycle=true`，边照建 |
| `critical-paths` mode 非法 | `ValidationError` 422 |

## 7. 测试（testcontainers Neo4j+MySQL，沿用 seed/client）

- `test_edge_api.py`：建/列/取/改/删边；404 端点不存在；409 重复；422 自环；按 source/target/edge_type 过滤；写需 editor（viewer 403）。
- `test_graph_query_api.py`：上游/下游递归正确 + 分页（limit/offset/total）；impact 形态；子图 center/depth/direction + 全图；stats.has_cycle。
- `test_critical_path_api.py`：impact/longest/manual 三模式各自形态；非法 mode 422。
- `test_cycle_api.py`：建环 → `/cycles` 返回环；POST 制造环的边 → `warnings.creates_cycle=true` 且边已建。
- `test_node_counts.py`：详情递归计数（多跳）vs 列表邻居计数（一跳）差异。
- `test_graph_permission_matrix.py`：扩展边写端点 × 角色参数化（editor+ 可写、viewer 403、读全员 200）。

## Definition of Done

- 全量 `pytest` 绿（Phase 1+2+3A+3B，无回归）。
- 完整流程走通：建节点 → 建边（含成环预警）→ 上游/下游/影响/关键路径/环检测/子图 → 改边 → 删边。
- 错误响应符合 §8 信封（404/409/422）。
- 权限符合 §5.11（边写 editor+、图读 viewer+）。
- 可变长路径深度受 `max_traversal_depth` 上限约束。
- `NodeResponse` 详情递归计数、列表邻居计数语义正确。

## 下一子项目预告（不在本计划内）

3C：SQL 解析导入（sqlglot，master §5.7/§6.6）——复用 3B 的 edge_service/node_service 落库。
3D：文件 JSON/CSV 导入导出（§5.8）。
3E：删项目状态机 + Neo4j 后台清理 + 归档项目写入守卫（见 [[phase3-archived-project-write-guard]]）。



