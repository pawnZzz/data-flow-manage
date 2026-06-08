# 任务血缘工具 Phase 3A：Neo4j 基座 + 节点类型 Schema + 节点 CRUD — 设计文档

**日期：** 2026-06-08
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§3.2 跨库规则、§4.2 Neo4j 模型、§4.3 父子语义、§4.4 约束索引、§5.3 schema、§5.4 节点、§6.4 父子树、§8 错误处理）

## 目标

在 Phase 2（项目 + 成员 + RBAC）之上建立 Neo4j 图写入基座：Neo4j 访问层、约束/索引初始化、节点类型 Schema（NodeTypeSchema）CRUD、血缘节点（LineageNode）CRUD，以及父子（CHILD_OF）关系。这是整个图功能的写入基础，后续子项目（边、图查询、SQL 导入、导出、删项目清理）都依赖它。

## 范围

**做：**
- Neo4j 约束/索引初始化（可复用函数 + 部署脚本）。
- Neo4j 访问封装（repositories/graph_repo + cypher/ 目录）。
- NodeTypeSchema CRUD（建/列/取/改/删），改 schema 的兼容性检查。
- LineageNode CRUD（建/列/取/改/删），ext_props 按 schema 全面严格校验。
- 父子 CHILD_OF 关系：设父/解父、子节点/后代查询、设父成环预检。
- testcontainers Neo4j 测试基建。

**不做（YAGNI / 留待后续子项目）：**
- 依赖边 `:DEPENDS_ON` 与图查询/算法（Phase 3B）——因此 3A 的 NodeResponse 不含 upstream_count/downstream_count。
- SQL 解析导入（3C）、文件导入导出（3D）。
- 删项目 `deleting` 状态机 + Neo4j 后台清理 + 归档项目写入守卫（3E，见 [[phase3-archived-project-write-guard]]）。

## 复用 Phase 1/2

- `AppError` 体系与 §8 错误信封；`require_role(min_role)` / `ProjectContext` / `DbSession`（鉴权先走 MySQL）。
- 分层 routers → services → repositories；testcontainers fixture 模式；`seed` helper。
- 既有 `app/db/neo4j.py`（driver 单例、ping、close）。

## 架构决策

采用**仓储层 + 服务层 + Cypher 集中**（方案 A，契合 spec §10 目录规划）：

- `app/cypher/` 集中 Cypher 字符串，按资源分文件，与 Python 解耦、便于单独 review，为 3B 图算法铺路。
- `app/repositories/graph_repo.py` 封装 Neo4j 会话/事务执行。
- 服务层做业务逻辑（UUID 生成、ext_props 校验、兼容性检查、成环预检）。
- 备选方案 B（仓储内联 Cypher）否决：与 spec §10 的 cypher/ 目录规划及 3B 集中管理不一致；方案 C（服务直连 driver）否决：session/事务/错误处理散落、与既有分层冲突。

**跨库规则（spec §3.2）：** `require_role` 先查 MySQL 鉴权，通过后才操作 Neo4j；Neo4j 节点用属性 `project_id`（整数，= MySQL projects.id）标识归属，只读不反写。

## 1. 文件结构

新增文件及职责：

- `app/db/neo4j_constraints.py` — `init_constraints(driver)`，幂等施加 §4.4 全部约束/索引（`CREATE ... IF NOT EXISTS`）。
- `scripts/__init__.py` + `scripts/init_neo4j_constraints.py` — 部署脚本，调 `init_constraints`。
- `app/repositories/__init__.py` + `app/repositories/graph_repo.py` — Neo4j 执行封装：`run_write(cypher, **params)`、`run_read(cypher, **params)`，统一开 session、参数化、record→dict。
- `app/cypher/__init__.py` + `app/cypher/schemas.py` + `app/cypher/nodes.py` — Cypher 串集中（父子树/成环预检放 nodes.py）。
- `app/schemas/graph.py` — Pydantic 请求/响应模型。
- `app/services/schema_service.py` — schema CRUD + 兼容性检查。
- `app/services/node_service.py` — 节点 CRUD + ext_props 校验 + 父子关系 + 成环预检。
- `app/routers/schemas.py` + `app/routers/nodes.py` — HTTP 层。
- `app/main.py` — 注册两个新路由（启动已有 Neo4j ping，无需改）。
- 测试：`tests/conftest.py` 加 testcontainers Neo4j fixture + seed 扩展；`test_neo4j_constraints.py`、`test_schema_api.py`、`test_node_api.py`、`test_parent_api.py`、`test_node_service.py`、`test_schema_service.py`、`test_graph_permission_matrix.py`。

**Neo4j 测试基建：** session 级 `neo4j_container` fixture（testcontainers `Neo4jContainer`），起容器后跑 `init_constraints`；function 级 fixture 清空图（`MATCH (n) DETACH DELETE n`）保证隔离；`graph_repo` 在测试中指向容器（类似 MySQL 的 `get_session` override）。

## 2. 数据模型

### Neo4j 节点/关系（仓储层直接 Cypher 读写，不用 ORM）

```
(:NodeTypeSchema {id(UUID), project_id(int), type_key, display_name,
                  fields(JSON 字符串), created_at, updated_at})
(:LineageNode {id(UUID), project_id(int), name, type, description,
               owner, department, system, priority,
               tags(list<string>), ext_props(JSON 字符串), is_critical(bool),
               created_at, updated_at, created_by(int), updated_by(int)})
(:LineageNode)-[:CHILD_OF]->(:LineageNode)   // 子→父，无属性
```

- `fields` 与 `ext_props` 是嵌套结构，Neo4j 属性不支持嵌套 map/对象列表，故在仓储层**序列化为 JSON 字符串**存储，读出时反序列化。服务层与 API 看到的都是结构化对象。
- `department` / `system` / `priority` 是内置字段（所有类型通用），不进 per-type schema；`ext_props` 才是各 type 自定义字段。

### 约束/索引（§4.4）

node id 唯一、(project_id,name) 唯一、schema id 唯一、(project_id,type_key) 唯一；外加 (project_id,type)、(project_id,department,system)、(project_id,priority) 三个索引。

### Pydantic schemas（`app/schemas/graph.py`）

- `SchemaFieldSpec`：name, label, type(enum: string/number/url/enum/bool), required(bool=False), options(list[str]|None), default(Any|None)。
- `CreateSchemaRequest`：type_key, display_name, fields(list[SchemaFieldSpec])。
- `UpdateSchemaRequest`：display_name?, fields?。
- `SchemaResponse`：id, type_key, display_name, fields, created_at, updated_at。
- `CreateNodeRequest`：name, type, description?, owner?, department?, system?, priority?(`^P[0-5]$`|None), tags(list[str]=[]), ext_props(dict={}), is_critical(bool=False)。
- `UpdateNodeRequest`：上述字段全可选（PATCH 语义）。
- `NodeResponse`：全部节点字段 + parent_id(str|None) + children_count(int)。**3A 不含 upstream_count/downstream_count**（依赖 :DEPENDS_ON，留 3B）。
- `SetParentRequest`：parent_id(str)。

## 3. API 端点、权限与跨库流程

`routers/schemas.py`（prefix `/api/v1/projects/{pid}/schemas`）、`routers/nodes.py`（prefix `/api/v1/projects/{pid}/nodes`）。全部经 `require_role` 先 MySQL 鉴权。

| 方法 路径 | 权限 | 服务 | 关键行为 / 错误 |
|---|---|---|---|
| `GET /schemas` | viewer | `list_schemas(pid)` | — |
| `POST /schemas` | editor | `create_schema(...)` | type_key 重复→409 `SCHEMA_CONFLICT` |
| `GET /schemas/{type_key}` | viewer | `get_schema(...)` | 无→404 |
| `PUT /schemas/{type_key}` | editor | `update_schema(...)` | 不兼容现有节点→409 `SCHEMA_INCOMPATIBLE`（返回冲突节点）|
| `DELETE /schemas/{type_key}` | admin | `delete_schema(...)` | 仍有节点用该 type→409 `SCHEMA_IN_USE` |
| `GET /nodes` | viewer | `list_nodes(pid, filters)` | query: type/department/system/priority/tag/name 模糊/parent_id/has_parent |
| `POST /nodes` | editor | `create_node(...)` | type 无 schema→422；ext_props 不合法→422；name 重复→409 `NODE_NAME_CONFLICT` |
| `GET /nodes/{nid}` | viewer | `get_node(...)` | 含 parent_id + children_count；无→404 |
| `PATCH /nodes/{nid}` | editor | `update_node(...)` | 同建节点校验；改 name 冲突→409 |
| `DELETE /nodes/{nid}` | editor | `delete_node(...)` | `DETACH DELETE`，子节点 CHILD_OF 一并删（变顶层），子节点本身不删 |
| `POST /nodes/{nid}/parent` | editor | `set_parent(nid, parent_id)` | 跨项目/自环→400；成环→400 `PARENT_CYCLE` |
| `DELETE /nodes/{nid}/parent` | editor | `clear_parent(nid)` | 删 CHILD_OF 出边 |
| `GET /nodes/{nid}/children` | viewer | `list_children(nid)` | 直接子节点 |
| `GET /nodes/{nid}/descendants` | viewer | `list_descendants(nid)` | 递归后代（`CHILD_OF*1..`）|

**建节点跨库流程：** `require_role(editor)` 查 MySQL membership → `node_service.create_node` 取该 project+type 的 schema（无则 422）→ 按 schema 校验 ext_props → 生成 UUID → Cypher `CREATE` 写 Neo4j（违反 (project_id,name) 唯一约束→捕获转 409 `NODE_NAME_CONFLICT`）。

**新增错误 code**（沿用 `AppError` 子类，必要时传 code 覆盖）：`SCHEMA_CONFLICT`/`SCHEMA_INCOMPATIBLE`/`SCHEMA_IN_USE`（→409 `ConflictError`）、`NODE_NAME_CONFLICT`（→409）、`PARENT_CYCLE`（→400/422 `ValidationError`）。权限依据 spec §5.3/§5.4/§5.11（schema 删除 admin+，余写操作 editor+，读 viewer）。

## 4. ext_props 校验与成环预检

### ext_props 全面严格校验（`_validate_ext_props(schema_fields, ext_props) -> dict`）

```
对每个 field in schema.fields:
  - required 且 ext_props 缺该 key → 422 缺必填字段
  - 提供了值则按 field.type 校验:
      string → str；number → int/float；url → str 且 http(s):// 前缀；
      bool → bool；enum → str 且 ∈ field.options
对 ext_props 里 schema 未定义的 key → 422 未知字段（全面严格）
未提供且非 required：若 field.default 存在则填入，否则留空
返回补好 default 的规范化 ext_props
```

错误以 `ValidationError`(422) 抛出，details 带字段名与问题。schema 兼容性检查复用此函数。

### schema PUT 兼容性检查（`schema_service.update_schema`）

用新 fields 跑该 type 所有现有节点的 `_validate_ext_props`，任一不通过 → 收集冲突 → 409 `SCHEMA_INCOMPATIBLE`，details 列 `{node_id, name, errors}`，拒绝更新。

### 设父成环预检（`node_service.set_parent`，spec §6.4）

CHILD_OF 方向为"子→父"。设 nid 的父为 parent，即建 `(nid)-[:CHILD_OF]->(parent)`。

```
1. parent_id == nid → 400（自环）
2. 两节点同项目（都属 pid）→ 否则 400
3. 成环预检：成环当且仅当 parent 已是 nid 的后代，即存在
     MATCH (parent {id:$parent_id})-[:CHILD_OF*1..]->(target {id:$nid})
   存在该路径 → 设置会成环 → 400 PARENT_CYCLE
4. nid 已有父（CHILD_OF 出边）→ 先删旧再建新（单一父亲，§4.3）
5. CREATE (nid)-[:CHILD_OF]->(parent)
```

## 5. 错误处理与测试

### 错误处理（复用 §8 信封）

| 场景 | 异常 → HTTP / code |
|---|---|
| 项目不存在 / 非成员 / 角色不足 | `require_role`（Phase 2）→ 404/403 |
| schema/节点不存在 | `NotFoundError` → 404 |
| type_key 重复建 schema | `ConflictError` → 409 `SCHEMA_CONFLICT` |
| PUT schema 与现有节点不兼容 | `ConflictError` → 409 `SCHEMA_INCOMPATIBLE` |
| 删 schema 仍有节点用 | `ConflictError` → 409 `SCHEMA_IN_USE` |
| 建节点时 type 无 schema | `ValidationError` → 422 |
| ext_props 不合法 | `ValidationError` → 422（带字段详情）|
| name 项目内重复 | `ConflictError` → 409 `NODE_NAME_CONFLICT` |
| 设父成环 / 跨项目 / 自环 | `ValidationError` → 400 `PARENT_CYCLE` 等 |

### 测试（testcontainers Neo4j + MySQL；seed 扩展加建 schema/节点 helper）

- `test_neo4j_constraints.py`：`init_constraints` 幂等、唯一约束生效。
- `test_schema_api.py`：schema CRUD、type_key 重复 409、删除被占用 409、PUT 不兼容 409、权限。
- `test_node_api.py`：建节点（须先有 schema）、无 schema 422、ext_props 各类校验 422、name 重复 409、列表过滤、改/删、DETACH DELETE 后子节点变顶层、权限。
- `test_parent_api.py`：设父/解父、子节点/后代查询、成环 400、跨项目 400、换父（单一父亲）、删父后 CHILD_OF 消失。
- `test_node_service.py` / `test_schema_service.py`：`_validate_ext_props` 单元（每种 type、缺必填、未知字段、default 填充）、兼容性检查单元。
- `test_graph_permission_matrix.py`：schema/node 写端点 × 角色参数化（沿用 Phase 2 风格）。

## Definition of Done

- 全量 `pytest` 绿（Phase 1+2+3A，无回归）。
- `scripts/init_neo4j_constraints.py` 对真实 Neo4j 成功建约束/索引。
- 完整流程可走通：建 schema → 建节点（ext_props 校验）→ 设父子 → 查后代 → 改 → 删。
- 错误响应符合 §8 信封。
- 权限符合 spec §5.3/§5.4/§5.11。

## 下一子项目预告（不在本计划内）

3B：依赖边 `:DEPENDS_ON` CRUD + 图查询/算法（上下游遍历、影响分析、关键路径、环检测、子图渲染）。将复用 3A 的 `graph_repo`、`cypher/` 目录、节点模型，并给 NodeResponse 补 upstream_count/downstream_count。

