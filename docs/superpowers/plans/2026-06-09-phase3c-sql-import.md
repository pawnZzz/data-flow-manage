# 任务血缘工具 Phase 3C：SQL 解析导入 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 粘贴 SQL → 解析出表（节点）与依赖（边）供用户确认 → commit 写入图，复用 3B 的 node/edge/schema service。

**Architecture:** 纯函数解析层（sqlglot，不碰 DB）+ 编排服务层（preview 只读匹配、commit 自动建最小 schema + 复用/跳过）+ 薄路由。沿用既有 routers→services→cypher 分层。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、sqlglot 30.x、neo4j、pytest、testcontainers。

参考 spec：`docs/superpowers/specs/2026-06-09-phase3c-sql-import-design.md`。

---

## File Structure

- `backend/pyproject.toml` — 改：主依赖加 `sqlglot>=25`。
- `backend/app/services/sql_parser.py` — 新建：`parse_sql(sql, dialect)` 纯函数。
- `backend/app/schemas/sql_import.py` — 新建：Pydantic 请求/响应。
- `backend/app/cypher/nodes.py` — 改：加 `GET_BY_NAME`。
- `backend/app/services/sql_import_service.py` — 新建：preview/commit 编排。
- `backend/app/routers/sql_import.py` — 新建：两端点。
- `backend/app/main.py` — 改：注册路由（graph 之后）。
- `backend/tests/test_sql_parser.py` — 新建：纯单元。
- `backend/tests/test_sql_import_api.py` — 新建：preview/commit 集成。

约定：命令在 `cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/backend && . .venv/bin/activate` 下跑；commit 在仓库根，message 末尾附 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## Task 1: SQL 解析层（依赖 + 纯函数）

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/services/sql_parser.py`
- Test: `backend/tests/test_sql_parser.py`

- [ ] **Step 1: 加依赖**

在 `backend/pyproject.toml` 的 `dependencies = [` 列表里加一行 `"sqlglot>=25",`（与其它主依赖并列，注意逗号）。然后安装：
```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8/backend && . .venv/bin/activate && pip install -e ".[dev]" 2>&1 | tail -2
```

- [ ] **Step 2: 写失败测试 `backend/tests/test_sql_parser.py`**

```python
import pytest
from sqlglot.errors import ParseError

from app.services.sql_parser import parse_sql


def test_insert_select_direction():
    out = parse_sql("INSERT INTO dw.t SELECT * FROM src.a", dialect="mysql")
    assert "dw.t" in out["tables"]
    assert "src.a" in out["tables"]
    # 目标依赖源：source=目标 dw.t, target=源 src.a
    assert {"source": "dw.t", "target": "src.a", "edge_type": "data_flow"} in out["dependencies"]


def test_create_table_as_multi_source():
    out = parse_sql(
        "CREATE TABLE x AS SELECT * FROM a JOIN b ON a.id=b.id", dialect="mysql"
    )
    assert "x" in out["tables"]
    assert {"a", "b"} <= set(out["tables"])
    deps = {(d["source"], d["target"]) for d in out["dependencies"]}
    assert ("x", "a") in deps and ("x", "b") in deps


def test_cte_intermediate_excluded():
    out = parse_sql(
        "INSERT INTO dw.t WITH c AS (SELECT * FROM src.base) SELECT * FROM c",
        dialect="mysql",
    )
    # CTE 名 c 不应成为表/依赖端点；真正的源是 src.base
    assert "c" not in out["tables"]
    assert "src.base" in out["tables"]
    deps = {(d["source"], d["target"]) for d in out["dependencies"]}
    assert ("dw.t", "src.base") in deps
    assert all("c" not in pair for pair in deps)


def test_select_only_unrecognized():
    out = parse_sql("SELECT 1", dialect="mysql")
    assert out["tables"] == []
    assert out["dependencies"] == []
    assert len(out["unrecognized"]) == 1


def test_qualified_name_preserved():
    out = parse_sql("INSERT INTO dw.ods_user SELECT * FROM raw.log", dialect="mysql")
    assert "dw.ods_user" in out["tables"]
    assert "raw.log" in out["tables"]


def test_syntax_error_raises():
    with pytest.raises(ParseError):
        parse_sql("INSERT INTO", dialect="mysql")


def test_multi_statement_mixed():
    out = parse_sql("SELECT 1; INSERT INTO a SELECT * FROM b", dialect="mysql")
    assert {"a", "b"} <= set(out["tables"])
    assert len(out["unrecognized"]) == 1  # SELECT 1
```

- [ ] **Step 3: 运行确认失败**

Run: `pytest tests/test_sql_parser.py -q` → FAIL（ModuleNotFoundError: app.services.sql_parser）

- [ ] **Step 4: 创建 `backend/app/services/sql_parser.py`**

```python
import sqlglot
from sqlglot import exp

_LINEAGE_STMTS = (exp.Insert, exp.Create, exp.Merge, exp.Update)


def _target_table(stmt: exp.Expression) -> str | None:
    """写入目标表的完整限定名。stmt.this 可能是 Table，或被 Schema(列定义) 包裹。"""
    node = stmt.this
    if isinstance(node, exp.Table):
        return node.sql()
    tbl = node.find(exp.Table) if node is not None else None
    return tbl.sql() if tbl is not None else None


def _source_tables(stmt: exp.Expression, target: str | None) -> list[str]:
    """FROM/JOIN/CTE 来源表，排除 target 自身与 CTE 中间名。"""
    cte_names = {c.alias for c in stmt.find_all(exp.CTE)}
    out: list[str] = []
    for t in stmt.find_all(exp.Table):
        name = t.sql()
        if name == target or name in cte_names:
            continue
        out.append(name)
    return list(dict.fromkeys(out))


def parse_sql(sql: str, dialect: str = "mysql") -> dict:
    """解析 SQL → {tables, dependencies, unrecognized}。

    语法错抛 sqlglot.errors.ParseError；未知 dialect 抛 ValueError。
    依赖方向：目标依赖源 → {source: 目标, target: 源}（对齐 (source)-[:DEPENDS_ON]->(target)）。
    """
    parsed = sqlglot.parse(sql, dialect=dialect)
    tables: list[str] = []
    dependencies: list[dict] = []
    unrecognized: list[str] = []
    for stmt in parsed:
        if stmt is None:
            continue
        if isinstance(stmt, _LINEAGE_STMTS):
            target = _target_table(stmt)
            sources = _source_tables(stmt, target)
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
    tables = list(dict.fromkeys(tables))
    return {"tables": tables, "dependencies": dependencies, "unrecognized": unrecognized}
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/test_sql_parser.py -q` → expect 7 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/pyproject.toml backend/app/services/sql_parser.py backend/tests/test_sql_parser.py
git commit -m "feat: SQL 解析层（sqlglot 抽表与依赖，纯函数）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 2: Pydantic schemas + GET_BY_NAME cypher

**Files:**
- Create: `backend/app/schemas/sql_import.py`
- Modify: `backend/app/cypher/nodes.py`
- Test: `backend/tests/test_schemas_sql_import.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_schemas_sql_import.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.sql_import import CommitRequest, CommitTable, PreviewRequest


def test_preview_request_defaults():
    r = PreviewRequest(sql="SELECT 1")
    assert r.dialect == "mysql"


def test_preview_request_rejects_empty_sql():
    with pytest.raises(ValidationError):
        PreviewRequest(sql="")


def test_commit_table_default_type():
    t = CommitTable(name="dw.t")
    assert t.type == "table"


def test_commit_request_defaults_empty_lists():
    r = CommitRequest()
    assert r.tables == [] and r.dependencies == []
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_schemas_sql_import.py -q` → FAIL（ModuleNotFoundError）

- [ ] **Step 3: 创建 `backend/app/schemas/sql_import.py`**

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

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_schemas_sql_import.py -q` → expect 4 passed.

- [ ] **Step 5: 加 `GET_BY_NAME` 到 `backend/app/cypher/nodes.py`**

在 `EXISTS = """..."""` 之后追加：
```python
GET_BY_NAME = """
MATCH (n:LineageNode {project_id: $pid, name: $name}) RETURN n.id AS id
"""
```

- [ ] **Step 6: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/schemas/sql_import.py backend/app/cypher/nodes.py backend/tests/test_schemas_sql_import.py
git commit -m "feat: SQL 导入 Pydantic schemas 与按名查节点 cypher

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Task 3: 编排服务 + 路由 + 集成测试

**Files:**
- Create: `backend/app/services/sql_import_service.py`
- Create: `backend/app/routers/sql_import.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_sql_import_api.py`

- [ ] **Step 1: 创建 `backend/app/services/sql_import_service.py`**

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
            pass
    seen.add(type_key)


def commit(repo: GraphRepo, pid: int, uid: int, payload: dict) -> dict:
    created_nodes = reused_nodes = created_edges = skipped_edges = 0
    name_to_id: dict[str, str] = {}
    seen_types: set = set()

    for t in payload["tables"]:
        name = t["name"]
        type_key = t.get("type") or "table"
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
                "edge_type": d.get("edge_type") or "data_flow",
            })
            created_edges += 1
        except (ConflictError, ValidationError):
            skipped_edges += 1

    logger.info("sql_import.commit pid=%s by=%s created_nodes=%s created_edges=%s",
                pid, uid, created_nodes, created_edges)
    return {"created_nodes": created_nodes, "reused_nodes": reused_nodes,
            "created_edges": created_edges, "skipped_edges": skipped_edges}
```

- [ ] **Step 2: 创建 `backend/app/routers/sql_import.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.sql_import import (
    CommitRequest,
    CommitResponse,
    PreviewRequest,
    PreviewResponse,
)
from app.services import sql_import_service

router = APIRouter(prefix="/api/v1/projects/{pid}/sql-import", tags=["sql-import"])


@router.post("/preview", response_model=PreviewResponse)
def preview(
    payload: PreviewRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> PreviewResponse:
    return sql_import_service.preview(repo, ctx.project.id, payload.sql, payload.dialect)


@router.post("/commit", response_model=CommitResponse)
def commit(
    payload: CommitRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> CommitResponse:
    return sql_import_service.commit(repo, ctx.project.id, ctx.user.id, payload.model_dump())
```

- [ ] **Step 3: 注册路由 `backend/app/main.py`**

在 `graph_router` 注册之后追加：
```python
    from app.routers import sql_import as sql_import_router

    app.include_router(sql_import_router.router)
```

- [ ] **Step 4: 写集成测试 `backend/tests/test_sql_import_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_preview_marks_existing(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    # 预建 schema "table" + 节点 src.a，使 preview 能标记 exists
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "table", "display_name": "table", "fields": []},
                headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes",
                json={"name": "src.a", "type": "table"}, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                    json={"sql": "INSERT INTO dw.t SELECT * FROM src.a"},
                    headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    by = {t["name"]: t for t in body["tables"]}
    assert by["src.a"]["exists"] is True and by["src.a"]["node_id"]
    assert by["dw.t"]["exists"] is False
    assert {"source": "dw.t", "target": "src.a", "edge_type": "data_flow"} in body["dependencies"]


def test_preview_does_not_write(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                json={"sql": "INSERT INTO dw.t SELECT * FROM src.a"},
                headers=_auth(seed, owner))
    # preview 不写库：节点列表应为空
    r = client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, owner))
    assert r.json() == []


def test_preview_syntax_error_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                    json={"sql": "INSERT INTO"}, headers=_auth(seed, owner))
    assert r.status_code == 422
    assert r.json()["error"]["details"].get("code") == "SQL_PARSE_ERROR"


def test_commit_creates_all(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    # 不预建 schema：commit 应自动建最小 schema
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                    json={"tables": [{"name": "dw.t"}, {"name": "src.a"}],
                          "dependencies": [{"source": "dw.t", "target": "src.a"}]},
                    headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json() == {"created_nodes": 2, "reused_nodes": 0,
                        "created_edges": 1, "skipped_edges": 0}
    # 验证确实写入
    names = {n["name"] for n in client.get(f"/api/v1/projects/{p.id}/nodes",
                                           headers=_auth(seed, owner)).json()}
    assert {"dw.t", "src.a"} <= names
    edges = client.get(f"/api/v1/projects/{p.id}/edges", headers=_auth(seed, owner)).json()
    assert len(edges) == 1


def test_commit_reuses_and_skips(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    body = {"tables": [{"name": "dw.t"}, {"name": "src.a"}],
            "dependencies": [{"source": "dw.t", "target": "src.a"}]}
    client.post(f"/api/v1/projects/{p.id}/sql-import/commit", json=body, headers=_auth(seed, owner))
    # 再次 commit 同样内容：节点复用、边跳过
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit", json=body, headers=_auth(seed, owner))
    assert r.json() == {"created_nodes": 0, "reused_nodes": 2,
                        "created_edges": 0, "skipped_edges": 1}


def test_commit_skips_unresolved_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    # 依赖端点表名不在 tables 中且库里没有 → 该边 skipped
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                    json={"tables": [{"name": "only"}],
                          "dependencies": [{"source": "only", "target": "ghost"}]},
                    headers=_auth(seed, owner))
    assert r.json()["created_nodes"] == 1
    assert r.json()["skipped_edges"] == 1


def test_sql_import_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer")
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                    json={"sql": "SELECT 1"}, headers=_auth(seed, viewer))
    assert r.status_code == 403
    r2 = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                     json={"tables": [], "dependencies": []}, headers=_auth(seed, viewer))
    assert r2.status_code == 403
```

- [ ] **Step 5: 运行集成测试**

Run: `pytest tests/test_sql_import_api.py -q` → expect 7 passed（首次拉容器较慢）。

- [ ] **Step 6: 全量回归**

Run: `pytest -q 2>&1 | tail -3` → expect all green（Phase 1+2+3A+3B+3C）。

- [ ] **Step 7: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/services/sql_import_service.py backend/app/routers/sql_import.py backend/app/main.py backend/tests/test_sql_import_api.py
git commit -m "feat: SQL 导入 preview/commit 编排与路由（自动建 schema、复用/跳过）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

## Phase 3C 完成标准（Definition of Done）

- [ ] 全量 `pytest` 绿（Phase 1+2+3A+3B+3C，无回归）。
- [ ] 流程走通：preview（标记 exists、不写库）→ commit（自动建最小 schema、复用/跳过、汇总计数）。
- [ ] 解析方向正确（目标依赖源）、CTE 中间表剔除、限定名保留、非血缘语句进 unrecognized。
- [ ] 语法错/坏方言 → 422 `SQL_PARSE_ERROR`；preview/commit 需 editor+（viewer 403）。
- [ ] `sqlglot` 加入主依赖。

## 下一子项目预告（不在本计划内）

- 3D：文件 JSON/CSV 导入导出。
- 3E：删项目状态机 + Neo4j 后台清理 + 归档项目写入守卫（见 [[phase3-archived-project-write-guard]]）。



