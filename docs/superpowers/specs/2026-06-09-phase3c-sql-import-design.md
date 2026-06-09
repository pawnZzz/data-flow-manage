# 任务血缘工具 Phase 3C：SQL 解析导入 — 设计文档

**日期：** 2026-06-09
**上游 spec：** `docs/superpowers/specs/2026-06-05-task-lineage-tool-design.md`（§5.7 SQL 导入 API、§6.6 sqlglot 解析、§8 错误处理）
**前置子项目：** Phase 3A（节点/schema/父子）、Phase 3B（依赖边 + 图查询）

## 目标

粘贴 SQL → 解析出表（节点）与依赖（边）供用户确认 → commit 写入图。复用 3B 的 `node_service`/`edge_service`/`schema_service`。

## 范围

**做（master §5.7/§6.6）：**
- `POST /projects/:pid/sql-import/preview`：body `{sql, dialect?}` → `{tables, dependencies, unrecognized}`，只读（解析 + 表名→已存在节点匹配，不写库）。
- `POST /projects/:pid/sql-import/commit`：body `{tables, dependencies}`（用户编辑过）→ 写入，返回 `{created_nodes, reused_nodes, created_edges, skipped_edges}`。
- 两端点权限 editor+。

**不做（YAGNI / 留后续）：**
- 列级血缘（仅表级）。
- preview 草稿持久化（commit 无状态，body 自带全部数据）。
- 文件 JSON/CSV 导入导出（3D）、删项目清理（3E）。

## 决策（已与用户确认）

- **表节点 type**：commit 时若 `CommitTable.type`（默认 "table"）的 schema 不存在，自动建一个空 fields 的最小 schema 再建节点。
- **commit 冲突**：表名已是节点 → 复用不报错；边已存在 → 跳过不报错。返回汇总计数。
- **表名规范化**：保留 sqlglot 还原的完整限定名（如 `dw.ods_user`），不同库同表名不合并。
- **方言**：`dialect` 透传 sqlglot，默认 `"mysql"`，接受任意 sqlglot 支持的方言串。
- **解析覆盖**：`INSERT/CREATE...AS/MERGE/UPDATE` 产出血缘；`SELECT`/`SET` 等能解析但非血缘语句 → `unrecognized`；整段 SQL 语法错 → 422。
- **edge_type**：SQL 推断的边一律 `data_flow`。

## 复用 Phase 3A/3B

- `node_service.create_node`（要求 type 有 schema、name 项目内唯一→409）、`schema_service.create_schema`、`edge_service.create_edge`（唯一性→409 `EDGE_EXISTS`、自环→422 `SELF_LOOP`）。
- `AppError` 体系与 §8 信封；`require_role(editor)`；`GraphRepoDep`；分层 routers→services→cypher。

## 1. 文件结构

| 文件 | 新建/改 | 职责 |
|------|--------|------|
| `backend/pyproject.toml` | 改 | 主依赖加 `sqlglot` |
| `app/services/sql_parser.py` | 新建 | 纯函数 `parse_sql(sql, dialect)` → {tables, dependencies, unrecognized}，不碰 DB |
| `app/services/sql_import_service.py` | 新建 | 编排 preview/commit；自动建最小 schema；复用/跳过 |
| `app/cypher/nodes.py` | 改 | 加 `GET_BY_NAME`（按 name 精确查节点 id） |
| `app/schemas/sql_import.py` | 新建 | Pydantic 请求/响应 |
| `app/routers/sql_import.py` | 新建 | 两端点 |
| `app/main.py` | 改 | 注册路由 |
| `tests/test_sql_parser.py` | 新建 | 纯单元 |
| `tests/test_sql_import_api.py` | 新建 | preview/commit 集成（testcontainers）|

## 2. 解析层 `sql_parser.py`（纯函数）

```python
import sqlglot
from sqlglot import exp

_LINEAGE_STMTS = (exp.Insert, exp.Create, exp.Merge, exp.Update)


def parse_sql(sql: str, dialect: str = "mysql") -> dict:
    """解析 SQL → {tables, dependencies, unrecognized}。语法错抛 sqlglot.errors.ParseError。"""
    parsed = sqlglot.parse(sql, dialect=dialect)  # list[Expression | None]
    tables: list[str] = []
    dependencies: list[dict] = []
    unrecognized: list[str] = []
    for stmt in parsed:
        if stmt is None:
            continue
        if isinstance(stmt, _LINEAGE_STMTS):
            target = _target_table(stmt)
            sources = _source_tables(stmt)
            if target:
                tables.append(target)
            tables.extend(sources)
            for src in sources:
                if target and src != target:
                    dependencies.append(
                        {"source": target, "target": src, "edge_type": "data_flow"}
                    )
        else:
            unrecognized.append(stmt.sql(dialect=dialect))
    # 去重，保序
    tables = list(dict.fromkeys(tables))
    return {"tables": tables, "dependencies": dependencies, "unrecognized": unrecognized}
```

辅助：
- `_target_table(stmt)`：取写入目标表的完整限定名。`Insert`→`stmt.this`（Table 或 Schema 包裹的 Table）；`Create`→`stmt.this`（CREATE TABLE x AS ...）；`Update`→`stmt.this`；`Merge`→`stmt.this`。用 `exp.Table` 的 `.sql()` 还原限定名。
- `_source_tables(stmt)`：`stmt.find_all(exp.Table)` 收集所有表，排除 target 本身与 CTE 别名。CTE 名通过 `stmt.find_all(exp.CTE)` 的 `.alias` 收集后从 sources 剔除（CTE 是中间产物，不建节点）。
- 限定名用 `table_expr.sql(dialect=dialect)`，保留 `db.table`。

> 解析层不依赖项目/DB，输入 SQL+dialect，输出纯数据，单元测试直接断言。

## 3. Pydantic 模型 `sql_import.py`

preview/commit 的 dependency 用**表名** `source`/`target`（不是边 UUID），避免与 `EdgeResponse` 混淆。

```python
from pydantic import BaseModel, Field


class PreviewRequest(BaseModel):
    sql: str = Field(min_length=1)
    dialect: str = "mysql"


class ParsedTable(BaseModel):
    name: str
    exists: bool
    node_id: str | None = None


class ParsedDependency(BaseModel):
    source: str
    target: str
    edge_type: str = "data_flow"


class PreviewResponse(BaseModel):
    tables: list[ParsedTable]
    dependencies: list[ParsedDependency]
    unrecognized: list[str]


class CommitTable(BaseModel):
    name: str = Field(min_length=1)
    type: str = "table"


class CommitDependency(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    edge_type: str = "data_flow"


class CommitRequest(BaseModel):
    tables: list[CommitTable] = []
    dependencies: list[CommitDependency] = []


class CommitResponse(BaseModel):
    created_nodes: int
    reused_nodes: int
    created_edges: int
    skipped_edges: int
```

## 4. 编排 `sql_import_service.py`

```python
import logging

from sqlglot.errors import SqlglotError

from app.cypher import nodes as nq
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.graph_repo import GraphRepo
from app.services import edge_service, node_service, schema_service
from app.services.sql_parser import parse_sql

logger = logging.getLogger("app.audit")


def _find_node_id(repo: GraphRepo, pid: int, name: str) -> str | None:
    rows = repo.run_read(nq.GET_BY_NAME, pid=pid, name=name)
    return rows[0]["id"] if rows else None


def preview(repo: GraphRepo, pid: int, sql: str, dialect: str) -> dict:
    try:
        parsed = parse_sql(sql, dialect)
    except (SqlglotError, ValueError) as e:
        # SqlglotError 覆盖 ParseError 等；ValueError 覆盖未知 dialect
        raise ValidationError("SQL 解析失败", {"code": "SQL_PARSE_ERROR", "detail": str(e)})
    tables = []
    for name in parsed["tables"]:
        nid = _find_node_id(repo, pid, name)
        tables.append({"name": name, "exists": nid is not None, "node_id": nid})
    return {"tables": tables, "dependencies": parsed["dependencies"],
            "unrecognized": parsed["unrecognized"]}


def _ensure_schema(repo: GraphRepo, pid: int, type_key: str, seen: set) -> None:
    if type_key in seen:
        return
    try:
        schema_service.get_schema(repo, pid, type_key)
    except NotFoundError:
        try:
            schema_service.create_schema(repo, pid, type_key, type_key, [])
        except ConflictError:
            pass  # 并发/重复，忽略
    seen.add(type_key)


def commit(repo: GraphRepo, pid: int, uid: int, payload: dict) -> dict:
    created_nodes = reused_nodes = created_edges = skipped_edges = 0
    name_to_id: dict[str, str] = {}
    seen_types: set = set()

    for t in payload["tables"]:
        name, type_key = t["name"], t.get("type", "table")
        existing = _find_node_id(repo, pid, name)
        if existing:
            name_to_id[name] = existing
            reused_nodes += 1
            continue
        _ensure_schema(repo, pid, type_key, seen_types)
        node = node_service.create_node(repo, pid, uid, {"name": name, "type": type_key})
        name_to_id[name] = node["id"]
        created_nodes += 1

    for d in payload["dependencies"]:
        sid = name_to_id.get(d["source"]) or _find_node_id(repo, pid, d["source"])
        tid = name_to_id.get(d["target"]) or _find_node_id(repo, pid, d["target"])
        if not sid or not tid:
            skipped_edges += 1
            continue
        try:
            edge_service.create_edge(repo, pid, uid, {
                "source_id": sid, "target_id": tid,
                "edge_type": d.get("edge_type", "data_flow"),
            })
            created_edges += 1
        except (ConflictError, ValidationError):  # 已存在 / 自环
            skipped_edges += 1

    logger.info("sql_import.commit pid=%s by=%s created_nodes=%s created_edges=%s",
                pid, uid, created_nodes, created_edges)
    return {"created_nodes": created_nodes, "reused_nodes": reused_nodes,
            "created_edges": created_edges, "skipped_edges": skipped_edges}
```

> commit body 里 dependency 的端点表名若不在本次 tables 中，回退用 `_find_node_id` 查既有节点；仍找不到 → skipped。

## 5. 新 Cypher（`nodes.py`）

```python
GET_BY_NAME = """
MATCH (n:LineageNode {project_id: $pid, name: $name}) RETURN n.id AS id
"""
```

## 6. 路由 `sql_import.py`

```python
router = APIRouter(prefix="/api/v1/projects/{pid}/sql-import", tags=["sql-import"])
# POST /preview  → require_role(editor)  → PreviewResponse
# POST /commit   → require_role(editor)  → CommitResponse
```
main.py 在 graph_router 之后注册。

## 7. 错误处理（§8 信封）

| 场景 | 处理 |
|------|------|
| SQL 语法错（ParseError）/ 不支持方言 | 422 `SQL_PARSE_ERROR` |
| commit 边端点表名无法解析为节点 | 该边 skipped（不报错） |
| 边已存在 / 自环 | skipped（捕获 409/422） |
| 权限不足 | 403（editor+） |

## 8. 测试

- `test_sql_parser.py`（纯单元，无 DB）：`INSERT INTO t SELECT FROM s` 抽 target=t source=s 方向正确；`CREATE TABLE x AS SELECT FROM a JOIN b` 多源；CTE 中间表被剔除；`SELECT 1` → unrecognized；语法错抛 ParseError；限定名 `db.tbl` 保留。
- `test_sql_import_api.py`（testcontainers）：preview 标记 exists/node_id 正确且不写库；commit 全新建（schema 自动建 + created 计数 + 边建好）；commit 复用已有节点（reused_nodes）；commit 重复边 skipped_edges；preview/commit 需 editor（viewer 403）。

## Definition of Done

- 全量 `pytest` 绿（Phase 1+2+3A+3B+3C，无回归）。
- 流程走通：preview → 用户编辑 → commit；自动建最小 schema；复用/跳过计数正确。
- 错误响应符合 §8 信封（422 解析错、403 权限）。
- `sqlglot` 加入主依赖。

## 下一子项目预告（不在本计划内）

- 3D：文件 JSON/CSV 导入导出。
- 3E：删项目状态机 + Neo4j 后台清理 + 归档项目写入守卫（见 [[phase3-archived-project-write-guard]]）。


