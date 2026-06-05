# 任务血缘管理工具 — 设计文档

- 日期：2026-06-05
- 状态：已通过 brainstorming 评审，待用户确认
- 主题：轻量级计算任务/服务血缘管理工具

## 1. 背景与目标

### 1.1 要解决的问题

在混合了数据任务（ETL、数仓作业等）和服务依赖的环境里，变更某个任务或服务时，
很难快速、完整地看清它的上下游依赖，容易遗漏受影响的下游。本工具提供一个可视化、
可编辑的血缘图谱，让用户在图上直接增删改查任务及其上下游关系，并在变更前做影响分析。

### 1.2 核心使用场景

- 混合场景：同时管理数据任务和服务依赖（统一为"节点"，靠 type 字段区分）。
- 变更影响评估：选中一个节点，查看其全链路上游和下游，高亮关键路径，防止遗漏。
- 依赖维护：在图上手动编辑依赖，或通过 SQL 解析、文件、API 批量导入。

### 1.3 规模与约束

- 数据规模：中等规模，单项目几百个节点，可能涉及多个团队。
- 运行形态：单实例本地 Web 服务，前后端分离，可部署到团队内网一台机器供多人访问。
- 权限：完整账号体系，按项目/工作区组织，项目内四级角色。

### 1.4 非目标（YAGNI）

- 不做完整版本历史和回滚（仅保留不可回滚的操作日志）。
- 不做大规模（上千节点以上）分布式图计算优化。
- 不做节点级细粒度权限（权限以项目为边界）。
- 画布布局、折叠、过滤等个人视图偏好不入库（存浏览器本地）。

## 2. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3（Composition API + `<script setup>`）+ Pinia + Vue Router + AntV X6 + Element Plus |
| 后端 | Python + FastAPI + Pydantic |
| 关系数据库 | MySQL 8.x（账号、项目、成员、角色、审计日志） |
| 图数据库 | Neo4j 5.x Community（血缘节点、依赖边、节点类型 schema） |
| 关系库 ORM/迁移 | SQLAlchemy + Alembic |
| 图驱动 | 官方 neo4j Python driver（Bolt 协议） |
| SQL 解析 | sqlglot |
| 部署 | docker-compose（mysql + neo4j + backend + frontend/nginx） |

## 3. 架构总览

整体形态：单实例本地 Web 服务，前后端分离 + 双数据库（职责拆分）。

```
┌──────────────────┐
│  Vue 3 + AntV X6 │   浏览器 SPA
└────────┬─────────┘
         │ HTTP / JSON
┌────────▼─────────┐
│   FastAPI 后端    │   单 Python 进程
│ ┌──────────────┐ │
│ │ API 路由层    │ │
│ │ 服务层        │ │
│ │ 仓储层        │ │   账号仓储(SQLAlchemy) + 图仓储(neo4j driver)
│ └──────────────┘ │
└──┬────────────┬──┘
   │            │
┌──▼────┐  ┌────▼─────┐
│ MySQL │  │  Neo4j   │
│ users │  │ Lineage  │
│projects│ │ Node     │
│members│  │ Edges    │
│ roles │  │ TypeSchema│
│ audit │  │          │
└───────┘  └──────────┘
```

### 3.1 职责划分

- MySQL：管"人和组织"——用户、密码、项目、成员、角色、审计日志。经典关系模型。
- Neo4j：管"图谱本身"——血缘节点、依赖边、节点类型 schema。承担所有图遍历、
  影响分析、关键路径、环检测。
- FastAPI 后端：暴露 REST API、鉴权、协调两库写入、SQL 解析。
- 前端：图编辑、属性面板、影响分析视图、SQL 导入入口、项目和成员管理。

### 3.2 跨库引用规则

两库之间唯一的耦合点是 `project_id`：

- MySQL 的 `projects.id` 是项目的唯一真实来源（source of truth）。
- Neo4j 的 `:LineageNode` 通过属性 `project_id` 标识归属，只读这个 ID，不反向写。
- 创建项目：写 MySQL。删项目：MySQL 标记 `deleting` → 后台任务删 Neo4j 数据 → 删 MySQL 记录。
- 写节点/边：直接写 Neo4j。写审计日志：写 MySQL。
- 读图：先查 MySQL 鉴权（用户对该项目的角色），通过后查 Neo4j 取图数据。

### 3.3 一致性兜底

- 单库内强一致：MySQL 用事务，Neo4j 用事务。
- 跨库不一致只可能出现在"删项目"环节，用项目状态机（active / archived / deleting）+ 可重试的
  后台清理任务解决。
- 提供管理命令 `rebuild-graph --project=N`，从导出快照重放，处理极端不一致。

## 4. 数据模型

### 4.1 MySQL 表结构

```sql
-- 用户
users (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  username      VARCHAR(64)  UNIQUE NOT NULL,
  email         VARCHAR(128) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,            -- bcrypt
  display_name  VARCHAR(64),
  status        ENUM('active','disabled') DEFAULT 'active',
  created_at    DATETIME,
  updated_at    DATETIME
)

-- 项目（工作区）
projects (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  name         VARCHAR(128) NOT NULL,
  description  TEXT,
  status       ENUM('active','archived','deleting') DEFAULT 'active',
  created_by   BIGINT NOT NULL REFERENCES users(id),
  created_at   DATETIME,
  updated_at   DATETIME,
  INDEX idx_status (status)
)

-- 项目成员 + 角色
project_members (
  project_id   BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id      BIGINT NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
  role         ENUM('owner','admin','editor','viewer') NOT NULL,
  joined_at    DATETIME,
  PRIMARY KEY (project_id, user_id),
  INDEX idx_user (user_id)
)

-- 操作日志（不可回滚）
audit_logs (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id       BIGINT NOT NULL REFERENCES users(id),
  project_id    BIGINT REFERENCES projects(id),       -- 非项目级操作可空
  action        VARCHAR(64) NOT NULL,                 -- node.create / edge.delete / project.invite ...
  target_type   VARCHAR(32),                          -- node / edge / project / member / schema
  target_id     VARCHAR(64),                          -- Neo4j 节点 UUID 或 MySQL 资源 ID（统一存 string）
  payload       JSON,                                 -- 操作前后差异/参数
  ip            VARCHAR(45),
  created_at    DATETIME,
  INDEX idx_project_time (project_id, created_at),
  INDEX idx_user_time (user_id, created_at)
)
```

说明：

- 所有跨库引用（如 `audit_logs.target_id` 指向 Neo4j 节点）一律用 string 存 UUID，避免 ID 类型耦合。
- `project_members` 用复合主键，保证一个用户在同项目内只有一个角色。
- 审计日志的 `payload` 用 JSON 存灵活内容，无需为每种操作建表。

### 4.2 Neo4j 数据模型

**节点 label 和属性**：

```cypher
(:LineageNode {
  id:           string,        // UUID，主标识
  project_id:   integer,       // MySQL projects.id
  name:         string,        // 节点名称（项目内唯一）
  type:         string,        // 节点类型 key，对应 NodeTypeSchema
  description:  string,

  // 组织归属
  owner:        string,        // 负责人（用户名或邮箱，文本字段）
  department:   string,        // 所属部门
  system:       string,        // 所属系统

  // 重要等级
  priority:     string,        // P0 / P1 / P2 / P3 / P4 / P5，可空（未分级）

  tags:         list<string>,
  ext_props:    map,           // 项目 schema 定义的自定义扩展字段
  is_critical:  boolean,       // 是否被手动标记为关键节点（默认 false）

  created_at:   datetime,
  updated_at:   datetime,
  created_by:   integer,       // user_id
  updated_by:   integer
})

(:NodeTypeSchema {
  id:           string,
  project_id:   integer,
  type_key:     string,        // data_task / service / table ...
  display_name: string,
  fields:       list<map>,     // [{name, label, type, required, options, default}, ...]
  created_at:   datetime,
  updated_at:   datetime
})
```

`department` / `system` / `priority` 是节点的**内置字段**（所有类型通用），不在 per-type schema 中重复定义；
`ext_props` 才是各 type 自定义的字段。

**关系**：

```cypher
// 依赖关系：A -[:DEPENDS_ON]-> B 表示 A 依赖 B（B 是 A 的上游）
(:LineageNode)-[:DEPENDS_ON {
  id:           string,        // 边 UUID，便于日志/前端引用
  edge_type:    string,        // trigger / data_flow / api_call / custom
  description:  string,
  is_required:  boolean,       // 必需依赖 vs 软依赖
  strength:     string,        // strong / weak
  ext_props:    map,
  created_at:   datetime,
  created_by:   integer
}]->(:LineageNode)

// 父子关系：A -[:CHILD_OF]-> B 表示 A 是 B 的子节点（结构性归属，非依赖）
(:LineageNode)-[:CHILD_OF]->(:LineageNode)
```

### 4.3 父子关系语义

父子关系表达"组成"，与"依赖"正交，用单独的 `:CHILD_OF` 关系表达：

- 方向：子 → 父。每个节点至多 1 条出边 `:CHILD_OF`（单一父亲），可有任意多入边（多个孩子），形成树。
- 约束：
  1. 同一项目内才能建立父子关系（`A.project_id = B.project_id`）。
  2. 严格禁止成环（与依赖不同，父子是树，设父节点前预检查祖先链）。
  3. 删除父节点时，子节点的 `:CHILD_OF` 关系一并删除（子节点变为顶层节点），子节点本身不删；前端二次确认。
- 与依赖完全独立：影响分析（上下游追溯）只走 `:DEPENDS_ON`，不走 `:CHILD_OF`。
- 提供辅助查询「节点 X 的所有后代」用于画布的展开/收起。

### 4.4 索引和约束

```cypher
CREATE CONSTRAINT lineage_node_id_unique
  FOR (n:LineageNode) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT lineage_node_name_unique
  FOR (n:LineageNode) REQUIRE (n.project_id, n.name) IS UNIQUE;

CREATE INDEX lineage_node_project_type
  FOR (n:LineageNode) ON (n.project_id, n.type);

CREATE INDEX lineage_node_dept_system
  FOR (n:LineageNode) ON (n.project_id, n.department, n.system);

CREATE INDEX lineage_node_priority
  FOR (n:LineageNode) ON (n.project_id, n.priority);

CREATE CONSTRAINT schema_id_unique
  FOR (s:NodeTypeSchema) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT schema_type_unique_per_project
  FOR (s:NodeTypeSchema) REQUIRE (s.project_id, s.type_key) IS UNIQUE;
```

### 4.5 节点类型 Schema 示例

```json
{
  "type_key": "data_task",
  "display_name": "数据任务",
  "fields": [
    { "name": "schedule", "label": "调度周期", "type": "string", "required": true },
    { "name": "sla",      "label": "SLA",      "type": "string", "required": false },
    { "name": "engine",   "label": "执行引擎", "type": "enum", "options": ["spark","hive","flink"], "required": true },
    { "name": "doc_url",  "label": "文档链接", "type": "url",  "required": false }
  ]
}
```

创建/更新节点时，后端用项目内对应 `type_key` 的 schema 校验 `ext_props`。

### 4.6 设计决策落地对照

| 设计决策 | 落地位置 |
|---|---|
| 节点统一模型 + type 区分 | `:LineageNode.type` |
| 节点扩展字段 + 类型 schema | `:LineageNode.ext_props` + `:NodeTypeSchema` |
| 部门/系统/优先级 | `:LineageNode` 内置字段 department/system/priority |
| 父子节点 | `:CHILD_OF` 树关系 |
| 边带完整属性 | `:DEPENDS_ON` 关系属性 |
| 允许环 | 不加非循环约束，查询时检测并警告 |
| 项目级权限 | MySQL `project_members.role` |
| 审计日志（不可回滚） | MySQL `audit_logs` |

## 5. API 设计

REST 风格，所有路径以 `/api/v1` 开头。鉴权用 JWT（登录返回 Bearer Token），需登录的接口走统一中间件校验。

### 5.1 鉴权和用户

```
POST   /auth/register             注册（可配置关闭）
POST   /auth/login                登录，返回 JWT
POST   /auth/logout               登出（前端丢 token，后端记审计）
GET    /auth/me                   当前用户
PATCH  /auth/me                   修改个人信息
POST   /auth/password             修改密码
```

### 5.2 项目和成员

```
GET    /projects                       我加入的项目列表
POST   /projects                       创建项目（创建者自动成为 owner）
GET    /projects/:pid                   项目详情
PATCH  /projects/:pid                   修改项目（admin+）
DELETE /projects/:pid                   归档项目（owner，状态 → deleting，触发后台清理）

GET    /projects/:pid/members           成员列表
POST   /projects/:pid/members           添加成员（admin+）
PATCH  /projects/:pid/members/:uid      修改角色（owner / admin）
DELETE /projects/:pid/members/:uid      移除成员（admin+；不能踢 owner）
```

### 5.3 节点类型 Schema

```
GET    /projects/:pid/schemas               当前项目所有 schema
POST   /projects/:pid/schemas               新增 schema（editor+）
GET    /projects/:pid/schemas/:type_key     单个 schema
PUT    /projects/:pid/schemas/:type_key     更新 schema（editor+，触发已有节点 ext_props 兼容性检查）
DELETE /projects/:pid/schemas/:type_key     删除 schema（admin+，需无节点使用该 type）
```

### 5.4 节点

```
GET    /projects/:pid/nodes                 节点列表（query: type, department, system, priority, tag, name 模糊, parent_id, has_parent）
POST   /projects/:pid/nodes                 新增节点（editor+）
GET    /projects/:pid/nodes/:nid            节点详情（含 parent_id, children_count, 上下游计数）
PATCH  /projects/:pid/nodes/:nid            修改节点（editor+）
DELETE /projects/:pid/nodes/:nid            删除节点（editor+，级联删 :DEPENDS_ON 和 :CHILD_OF）

POST   /projects/:pid/nodes/:nid/parent     设置父节点 body: {parent_id}
DELETE /projects/:pid/nodes/:nid/parent     解除父子关系
GET    /projects/:pid/nodes/:nid/children   直接子节点列表
GET    /projects/:pid/nodes/:nid/descendants  所有后代（递归）
```

### 5.5 边（依赖）

> 方向约定：边的 `source_id` 是**依赖方**（下游），`target_id` 是**被依赖方**（上游），
> 对应图中 `(source)-[:DEPENDS_ON]->(target)`，即"source 依赖 target"。

```
GET    /projects/:pid/edges                 边列表（query: source_id, target_id, edge_type）
POST   /projects/:pid/edges                 新增边（editor+）body: {source_id, target_id, edge_type, ...}
GET    /projects/:pid/edges/:eid            边详情
PATCH  /projects/:pid/edges/:eid            修改边
DELETE /projects/:pid/edges/:eid            删除边
```

### 5.6 图查询（核心功能）

```
GET    /projects/:pid/graph                 查询子图（画布渲染）
         query: ?center=:nid&depth=N&direction=upstream|downstream|both&include_children=true
         返回: { nodes, edges, groups, stats }
         无 center 时返回项目全图

GET    /projects/:pid/nodes/:nid/upstream   全部上游（递归），query: ?max_depth=N
GET    /projects/:pid/nodes/:nid/downstream 全部下游（递归）
GET    /projects/:pid/nodes/:nid/impact     影响分析综合接口
         返回: { upstream, downstream, critical_path: {mode, path, score}, warnings: {cycles} }

POST   /projects/:pid/critical-paths        关键路径计算
         body: { mode: "impact"|"longest"|"manual", node_ids?: [...] }

GET    /projects/:pid/cycles                环检测，返回: [{ nodes, edges }]
```

### 5.7 SQL 解析导入

```
POST   /projects/:pid/sql-import/preview    粘贴 SQL 解析为待确认的节点和边
         body: { sql, dialect: "mysql"|"hive"|"spark"|..., default_node_type?: "table" }
         返回: { tables, dependencies, unrecognized }

POST   /projects/:pid/sql-import/commit      用户确认（可调整）后写入
         body: { tables, dependencies }
```

### 5.8 文件导入导出

```
POST   /projects/:pid/import                 JSON / CSV 导入（form-data）
GET    /projects/:pid/export                 JSON 导出全图（仅数据，不含布局）
```

### 5.9 审计

```
GET    /projects/:pid/audit-logs             query: ?user_id=&action=&from=&to=&limit=&offset=
GET    /audit-logs/me                        我自己的操作历史（跨项目）
```

### 5.10 核心响应体形态

节点详情：

```json
{
  "id": "n_8f3...uuid",
  "project_id": 12,
  "name": "ods_user_event",
  "type": "data_task",
  "description": "用户行为日志清洗",
  "owner": "alice",
  "department": "数据平台",
  "system": "数仓",
  "priority": "P1",
  "tags": ["daily", "core"],
  "ext_props": { "schedule": "0 2 * * *", "engine": "spark", "sla": "4h" },
  "is_critical": false,
  "parent_id": "n_a1b...uuid",
  "children_count": 3,
  "upstream_count": 5,
  "downstream_count": 12,
  "created_at": "...", "updated_at": "...",
  "created_by": 7, "updated_by": 7
}
```

子图响应（图查询统一形态，直接喂给 X6）：

```json
{
  "nodes": [{ "id": "...", "name": "...", "type": "...", "priority": "...", "...": "..." }],
  "edges": [{ "id": "...", "source_id": "...", "target_id": "...", "edge_type": "...", "...": "..." }],
  "groups": [{ "id": "...", "name": "...", "children": ["...", "..."] }],
  "stats": { "node_count": 32, "edge_count": 41, "has_cycle": false }
}
```

### 5.11 权限矩阵

| 角色 | 读项目 | 写节点/边 | 改 schema | 管成员 | 改项目 | 删项目 |
|---|---|---|---|---|---|---|
| Owner  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Admin  | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Editor | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Viewer | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |

权限校验在 FastAPI dependency 里统一做（`require_role(min_role)`），不散落到业务代码。

## 6. 图算法与查询实现

所有图算法都是单条 Cypher 直出，不引入 GDS 库（保持依赖轻量）。所有可变长路径都写硬上限。

### 6.1 上游 / 下游遍历

```cypher
-- 全部上游（A 依赖的所有递归祖先）
MATCH (start:LineageNode {id: $node_id})
MATCH (start)-[:DEPENDS_ON*1..15]->(upstream:LineageNode)
RETURN DISTINCT upstream

-- 全部下游（依赖 A 的所有递归后代）
MATCH (start:LineageNode {id: $node_id})
MATCH (start)<-[:DEPENDS_ON*1..15]-(downstream:LineageNode)
RETURN DISTINCT downstream
```

### 6.2 关键路径（三种模式，对应需求 Q20-D）

模式 1 — 影响面（默认，按下游节点总数）：

```cypher
MATCH (n:LineageNode {project_id: $pid})
OPTIONAL MATCH (n)<-[:DEPENDS_ON*1..15]-(d:LineageNode)
WITH n, count(DISTINCT d) AS impact
ORDER BY impact DESC LIMIT 1
MATCH path = (n)<-[:DEPENDS_ON*1..15]-(leaf:LineageNode)
WHERE NOT (leaf)<-[:DEPENDS_ON]-()
RETURN path, impact, length(path) AS depth
ORDER BY depth DESC LIMIT 1
```

模式 2 — 最长路径（DAG 最长链）：

```cypher
MATCH path = (start:LineageNode {project_id: $pid})-[:DEPENDS_ON*1..15]->(end:LineageNode)
WHERE NOT ()-[:DEPENDS_ON]->(start)
  AND NOT (end)-[:DEPENDS_ON]->()
RETURN path, length(path) AS depth
ORDER BY depth DESC LIMIT 5
```

模式 3 — 手动标记（`is_critical` 节点之间的路径）：

```cypher
MATCH (a:LineageNode {project_id: $pid, is_critical: true})
MATCH (b:LineageNode {project_id: $pid, is_critical: true})
WHERE a.id <> b.id
MATCH path = shortestPath((a)-[:DEPENDS_ON*1..15]->(b))
RETURN path, a.name AS from, b.name AS to
```

后端 `POST /critical-paths` 按 `mode` 分发到上述三段 Cypher。

### 6.3 环检测

```cypher
MATCH path = (n:LineageNode {project_id: $pid})-[:DEPENDS_ON*1..10]->(n)
WITH nodes(path) AS cycle_nodes, relationships(path) AS cycle_edges
RETURN cycle_nodes, cycle_edges
LIMIT 50
```

警告策略（允许环存在，不阻止）：

- 写边时不阻止，响应里加 `warnings: { creates_cycle: true }`，前端弹"创建后会形成环，确认继续？"。
- 项目图查询接口的 `stats.has_cycle` 用轻量计数 Cypher 提前算出。
- 前端把环上的边渲染为红色虚线。

### 6.4 父子树查询

```cypher
-- 直接子节点
MATCH (parent:LineageNode {id: $node_id})<-[:CHILD_OF]-(child:LineageNode)
RETURN child

-- 所有后代（递归）
MATCH (parent:LineageNode {id: $node_id})<-[:CHILD_OF*1..]-(descendant:LineageNode)
RETURN descendant

-- 设父节点前校验不成环：把 X 设为 Y 的父节点前，检查 Y 不是 X 的祖先
MATCH (x:LineageNode {id: $x_id})
OPTIONAL MATCH (x)-[:CHILD_OF*1..]->(ancestor:LineageNode {id: $y_id})
RETURN ancestor IS NOT NULL AS would_create_cycle
```

### 6.5 子图查询（画布渲染）

`GET /projects/:pid/graph?center=N&depth=2&direction=both`：

```cypher
MATCH (center:LineageNode {id: $center_id})
CALL {
  WITH center
  MATCH (center)-[:DEPENDS_ON*0..2]->(n) RETURN n
  UNION
  WITH center
  MATCH (center)<-[:DEPENDS_ON*0..2]-(n) RETURN n
}
WITH collect(DISTINCT n) AS nodes
UNWIND nodes AS node
OPTIONAL MATCH (node)-[r:DEPENDS_ON]->(other) WHERE other IN nodes
RETURN nodes, collect(DISTINCT r) AS edges
```

未指定 `center` 时返回项目全图（中等规模可承受），前端再做视口剪裁。

### 6.6 SQL 解析（sqlglot）

目标覆盖度为完整解析（DML/DDL/CTE/JOIN/MERGE/视图），落地用 sqlglot 实现。服务层逻辑：

```python
def parse_sql_to_lineage(sql: str, dialect: str, project_id: int):
    parsed = sqlglot.parse(sql, dialect=dialect)
    suggestions = {"tables": [], "dependencies": [], "unrecognized": []}
    for stmt in parsed:
        if isinstance(stmt, (exp.Insert, exp.Create, exp.Merge, exp.Update)):
            target = extract_target_table(stmt)      # 写入目标
            sources = extract_source_tables(stmt)    # FROM/JOIN/CTE 中的源
            suggestions["tables"].extend([target, *sources])
            for src in sources:
                suggestions["dependencies"].append({
                    "source_id": target,   # 目标依赖源（A 依赖 B）
                    "target_id": src,
                    "edge_type": "data_flow",
                })
        else:
            suggestions["unrecognized"].append(stmt.sql())
    # 表名 → 已存在节点 ID 映射；找不到的标记为"待创建"
    return suggestions
```

`/sql-import/preview` 返回 `{ tables, dependencies, unrecognized }`，前端表格化展示供用户勾选/编辑后再 `commit`。

### 6.7 性能与缓存

中等规模下默认不加缓存，但有两层保护：

1. 可变长路径硬上限：所有 `*1..N` 的 N 从配置读（默认 15），防止误操作跑爆 Neo4j。
2. 图查询接口分页：`upstream` / `downstream` 超过 200 节点时分页返回；前端默认渲染前 200，按需加载。

### 6.8 前端渲染契约

后端返回的子图直接喂给 X6：nodes → X6 节点；edges → X6 边；groups → X6 group node（含 children）。
布局用 X6 自带 `dagre` 分层布局，前端首次渲染时调用，节点位置不入库（保持后端纯净）。

## 7. 前端结构

Vue 3（Composition API + `<script setup>`）+ Pinia + Vue Router + AntV X6 + Element Plus。

### 7.1 页面路由

```
/login                    登录/注册
/projects                 项目列表（我加入的）
/projects/:pid            项目主视图（核心，画布在这里）
/projects/:pid/members    成员管理
/projects/:pid/schemas    节点类型 schema 管理
/projects/:pid/audit      操作日志
/profile                  个人设置
```

### 7.2 项目主视图布局

```
┌─────────────────────────────────────────────────────────┐
│ 顶栏: 项目名 │ 搜索框 │ 布局 │ 影响分析 │ SQL导入 │ 导出  │
├──────────┬──────────────────────────────────┬───────────┤
│ 左侧栏   │        X6 画布                    │  右侧栏   │
│ - 节点    │   [节点]──>[节点]──>[节点]        │ 属性面板  │
│   树/列表 │      │                           │ (选中节点 │
│ - 类型/   │   [容器节点 ▼]                   │  /边的    │
│   部门/   │      [子][子]                    │  详情编辑)│
│   系统/   │                                  │           │
│   优先级  │                                  │           │
│   过滤    │                                  │           │
└──────────┴──────────────────────────────────┴───────────┘
```

- 左侧栏：节点列表/树（父子层级或扁平），多维过滤（type / department / system / priority / tag），点击定位画布。
- 中间画布：X6 渲染，支持拖拽、缩放、框选、右键菜单、连线建边、拖入容器建父子。
- 右侧栏：选中节点/边时显示属性面板，按 schema 动态渲染表单，编辑即调 PATCH。

### 7.3 组件分解（按单一职责）

```
src/
├── api/                      # API 客户端层（每个资源一个文件）
│   ├── client.ts             # axios 实例 + JWT 拦截器 + 错误统一处理
│   ├── auth.ts / projects.ts / nodes.ts / edges.ts
│   ├── graph.ts              # 图查询/影响分析/环检测
│   ├── schemas.ts / sqlImport.ts
├── stores/                   # Pinia
│   ├── auth.ts               # 当前用户 + token
│   ├── project.ts            # 当前项目 + 成员 + 我的角色
│   ├── graph.ts              # 当前画布 nodes/edges/groups + 选中态
│   └── schema.ts             # 当前项目 type schemas
├── views/                    # 路由页面
│   ├── LoginView / ProjectListView / ProjectView（主容器）
│   ├── MembersView / SchemasView / AuditView
├── components/
│   ├── graph/
│   │   ├── GraphCanvas.vue        # X6 画布封装（渲染 + 交互事件）
│   │   ├── graphController.ts     # X6 图实例命令封装（增删节点/边/布局）
│   │   ├── nodeShapes.ts          # 自定义节点样式（按 type/priority 着色）
│   │   ├── contextMenu.ts         # 右键菜单
│   │   └── layout.ts              # dagre 布局调用
│   ├── panels/
│   │   ├── NodePanel.vue          # 节点属性编辑（含 schema 动态表单）
│   │   ├── EdgePanel.vue          # 边属性编辑
│   │   ├── ImpactPanel.vue        # 影响分析结果展示
│   │   └── SchemaForm.vue         # 按 schema 渲染字段（复用）
│   ├── sidebar/
│   │   ├── NodeTree.vue / FilterBar.vue
│   ├── sql/
│   │   └── SqlImportDialog.vue    # SQL 粘贴 + preview 表格 + commit
│   └── common/
│       ├── PriorityTag.vue        # P0~P5 彩色标签
│       └── RoleGuard.vue          # 按角色显隐操作按钮
└── router/guards.ts          # 路由守卫（未登录跳 login）
```

### 7.4 关键交互到 API 的映射

| 用户操作 | 前端行为 | API |
|---|---|---|
| 拖动节点连线到另一节点 | X6 触发 `edge:connected` | `POST /edges` |
| 删除选中边 | 确认弹窗 | `DELETE /edges/:eid` |
| 拖节点进容器 | X6 触发 `node:change:parent` | `POST /nodes/:nid/parent` |
| 右键"查看影响" | 调影响分析，结果填 ImpactPanel + 画布高亮 | `GET /nodes/:nid/impact` |
| 右键"标记关键节点" | PATCH `is_critical` | `PATCH /nodes/:nid` |
| 属性面板改字段 | 防抖后提交 | `PATCH /nodes/:nid` |
| 顶栏"环检测" | 调环检测，画布红色高亮 | `GET /cycles` |
| 顶栏切换关键路径模式 | 重算并高亮 | `POST /critical-paths` |
| 搜索框输入 | 过滤左侧列表 + 画布聚焦 | `GET /nodes?name=` |

### 7.5 视图保存（个人偏好）

画布布局位置、折叠状态、过滤条件属于"个人视图偏好"，存浏览器 localStorage（key 按 `project_id + user_id`），
不入库——保持后端纯净，也避免多人视图冲突。导出图时只导数据不导布局。

### 7.6 影响分析的视觉呈现

选中节点点"影响分析"后：

- 上游节点染蓝色、下游染橙色、选中节点高亮描边。
- 关键路径的边加粗 + 流动动画。
- 环上的边红色虚线。
- 非相关节点置灰淡出。
- 右侧 ImpactPanel 列出：上游 N 个、下游 M 个、关键路径详情、priority 分布（如 P0 有几个下游受影响）。

## 8. 错误处理

后端统一错误响应：

```json
{
  "error": {
    "code": "NODE_NAME_CONFLICT",
    "message": "节点名称在项目内已存在",
    "details": { "name": "ods_user_event" }
  }
}
```

- FastAPI 全局异常处理器把已知异常映射为结构化响应 + 合适 HTTP 状态码。
- 业务异常用自定义异常类（`ConflictError` / `PermissionDenied` / `NotFound` / `ValidationError` / `CycleError`），各对应固定 `code`。
- 前端 `client.ts` 拦截器统一捕获：401 跳登录，403 提示无权限，其余弹 `error.message`。

关键错误场景：

| 场景 | 处理 |
|---|---|
| 节点名项目内重复 | Neo4j 唯一约束 → `409 NODE_NAME_CONFLICT` |
| 设父节点成环 | 预检查 Cypher → `400 PARENT_CYCLE` |
| 删 schema 但有节点在用 | 计数检查 → `409 SCHEMA_IN_USE` |
| 非成员访问项目 | 鉴权中间件 → `403` |
| ext_props 不符合 schema | Pydantic + schema 校验 → `422` |
| SQL 解析失败 | sqlglot 抛错 → `400 SQL_PARSE_ERROR`，返回出错语句 |
| Neo4j / MySQL 连接失败 | `503`，前端提示"服务暂不可用" |

跨库一致性兜底：

- 删项目：MySQL 标记 `deleting` → 后台任务删 Neo4j 数据 → 删 MySQL 记录。任一步失败，停留在 `deleting`，可重试。
- 管理命令 `rebuild-graph --project=N`：从导出快照重放，处理极端不一致。

## 9. 测试策略

后端（pytest）：

- 单元测试：图算法 Cypher 包装函数（testcontainers 起临时 Neo4j）、SQL 解析模块（给定 SQL 断言节点/边）、
  权限校验逻辑、schema 校验。
- 集成测试：API 端到端（测试用 MySQL + Neo4j 容器），覆盖 CRUD、影响分析、环检测、SQL 导入全流程、
  权限矩阵（每个角色对每个端点的允许/拒绝）。
- 关键用例：环检测正确性、设父成环被拒、删节点级联、跨库删项目流程。

前端（Vitest + Vue Test Utils）：

- 组件测试：SchemaForm 按 schema 正确渲染字段、PriorityTag 着色、RoleGuard 按角色显隐。
- store 测试：graph store 的节点增删改状态流转。
- API 客户端：mock 后端，验证错误拦截。
- 图交互：`graphController` 命令封装单元测试（连线 → 建边的事件转换）。

测试数据：提供 seed 脚本，生成含约 50 节点、多类型、有环、有父子的样例项目，供手动验证和 e2e。

## 10. 项目结构

```
lineage-tool/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + 中间件 + 异常处理
│   │   ├── config.py            # 配置（DB 连接、JWT 密钥、路径上限等）
│   │   ├── deps.py              # 依赖注入（get_db、get_current_user、require_role）
│   │   ├── routers/             # 按资源分路由文件
│   │   ├── services/            # 业务逻辑（graph_service、sql_import、auth_service…）
│   │   ├── repositories/        # mysql_repo（SQLAlchemy）+ neo4j_repo（driver 封装）
│   │   ├── models/              # SQLAlchemy ORM + Pydantic schemas
│   │   ├── cypher/              # Cypher 查询字符串集中管理
│   │   └── exceptions.py
│   ├── migrations/              # Alembic（MySQL）
│   ├── scripts/                 # init_neo4j_constraints.py、seed.py、rebuild_graph.py
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/                     # 见第 7 节
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml           # mysql + neo4j + backend + frontend(nginx)
├── README.md
└── docs/
```

## 11. 部署 / 启动

`docker-compose.yml` 一键拉起四个服务：

```yaml
services:
  mysql:     # 8.x，schema 用 Alembic 初始化
  neo4j:     # 5.x community，挂载 volume，启动后跑约束初始化脚本
  backend:   # FastAPI (uvicorn)，依赖 mysql + neo4j healthy
  frontend:  # 构建后用 nginx 托管静态文件 + 反代 /api 到 backend
```

- 开发模式：后端 `uvicorn --reload`，前端 `vite dev`，数据库用 compose 单独起。
- 首次启动：`alembic upgrade head`（建 MySQL 表）→ `init_neo4j_constraints.py`（建约束）→ 可选 `seed.py`（样例数据）。
- 配置通过 `.env`：DB 地址、JWT 密钥、CORS、路径深度上限等。

## 12. 安全要点

- 密码 bcrypt 哈希；JWT 设合理过期 + 刷新机制。
- 所有 Cypher 用参数化查询（`$param`），杜绝 Cypher 注入；SQL 导入来的表名也必须参数化。
- CORS 限制来源；生产环境 JWT 密钥从环境变量读，不硬编码。
- 内网工具但默认开启鉴权（完整账号体系），不提供免登录后门。
- 登录接口加简单限流防爆破。

## 13. 需求决策汇总

| # | 决策点 | 选择 |
|---|---|---|
| 1 | 使用场景 | 混合（数据任务 + 服务依赖） |
| 2 | 数据规模 | 中等（几百节点） |
| 3 | 节点属性 | 基础 + 元数据 + 扩展字段 |
| 4 | 持久化 | MySQL（账号）+ Neo4j（图） |
| 5 | 影响分析 | 全链路 + 关键路径高亮 |
| 6 | 图交互 | 完整（拖拽/编辑/布局/搜索/分组/视图保存） |
| 7 | 协作 | 完整账号体系 |
| 8 | 运行形态 | 本地 Web 服务（Python 后端 + MySQL/Neo4j） |
| 9 | 节点建模 | 统一模型，type 字段区分 |
| 10 | 边属性 | 完整属性（类型/描述/强弱/是否必需 + 扩展） |
| 11 | 导入 | 文件 + REST API + SQL 解析（sqlglot） |
| 12 | 后端框架 | FastAPI |
| 13 | 前端栈 | Vue 3 + AntV X6 |
| 14 | 鉴权 | 完整账号体系 |
| 15 | 权限范围 | 按项目/工作区组织 |
| 16 | 角色 | Owner / Admin / Editor / Viewer |
| 17 | SQL 解析覆盖度 | 完整（sqlglot 实现） |
| 18 | 审计 | 简单操作日志（不可回滚） |
| 19 | 环依赖 | 允许存在，图上高亮警告 |
| 20 | 关键路径 | 默认影响面，可切最长路径/手动标记 |
| 21 | 扩展字段 | 节点类型 + 项目级 schema |
| — | 父子节点 | 独立 `:CHILD_OF` 树关系 |
| — | 内置字段 | 部门 / 系统 / 优先级(P0-P5) |











