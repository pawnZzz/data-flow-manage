# 任务血缘工具 Phase 3A：Neo4j 基座 + 节点 Schema + 节点 CRUD — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 2 之上建立 Neo4j 图写入基座：约束初始化、Neo4j 仓储层、节点类型 Schema CRUD、节点 CRUD（ext_props 按 schema 严格校验）、父子 CHILD_OF 关系。

**Architecture:** 分层 routers → services → repositories(graph_repo) + cypher/。鉴权先走 Phase 2 的 `require_role`（MySQL），通过后操作 Neo4j。`fields`/`ext_props` 在仓储层序列化为 JSON 字符串存 Neo4j。testcontainers Neo4j 跑真实 Cypher。

**Tech Stack:** Python 3.10+、FastAPI、neo4j(官方 driver)、Pydantic v2、pytest、testcontainers[neo4j]。

参考 spec：`docs/superpowers/specs/2026-06-08-phase3a-neo4j-nodes-schema-design.md`。

---

## File Structure

- `backend/pyproject.toml` — 修改：dev 依赖加 `testcontainers[neo4j]`。
- `backend/app/db/neo4j_constraints.py` — 新建：`init_constraints(driver)`。
- `backend/scripts/__init__.py` + `backend/scripts/init_neo4j_constraints.py` — 新建：部署脚本。
- `backend/app/repositories/__init__.py` + `backend/app/repositories/graph_repo.py` — 新建：`GraphRepo`（run_write/run_read）。
- `backend/app/deps.py` — 修改：加 `get_graph_repo` 依赖 + `GraphRepo` 类型别名。
- `backend/app/cypher/__init__.py` + `cypher/schemas.py` + `cypher/nodes.py` — 新建：Cypher 串。
- `backend/app/schemas/graph.py` — 新建：Pydantic 请求/响应。
- `backend/app/services/schema_service.py` — 新建：schema CRUD + 兼容性检查。
- `backend/app/services/node_service.py` — 新建：节点 CRUD + ext_props 校验 + 父子。
- `backend/app/routers/schemas.py` + `routers/nodes.py` — 新建：HTTP 层。
- `backend/app/main.py` — 修改：注册两路由。
- `backend/tests/conftest.py` — 修改：加 `neo4j_driver`/`graph` fixture + client 覆盖 graph_repo。
- `backend/tests/test_neo4j_constraints.py` / `test_ext_props.py` / `test_schema_api.py` / `test_node_api.py` / `test_parent_api.py` / `test_graph_permission_matrix.py` — 新建。

## Task 1: Neo4j 基座（依赖 + 约束 + GraphRepo + 测试 fixture）

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/db/neo4j_constraints.py`
- Create: `backend/app/repositories/__init__.py`, `backend/app/repositories/graph_repo.py`
- Modify: `backend/app/deps.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_neo4j_constraints.py`

- [ ] **Step 1: pyproject.toml dev 依赖加 neo4j testcontainer**

把 `"testcontainers[mysql]>=4.0",` 改为 `"testcontainers[mysql,neo4j]>=4.0",`。

- [ ] **Step 2: 创建 `backend/app/db/neo4j_constraints.py`**

```python
from neo4j import Driver

# spec §4.4 约束与索引；IF NOT EXISTS 保证幂等
_STATEMENTS = [
    "CREATE CONSTRAINT lineage_node_id_unique IF NOT EXISTS "
    "FOR (n:LineageNode) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT lineage_node_name_unique IF NOT EXISTS "
    "FOR (n:LineageNode) REQUIRE (n.project_id, n.name) IS UNIQUE",
    "CREATE INDEX lineage_node_project_type IF NOT EXISTS "
    "FOR (n:LineageNode) ON (n.project_id, n.type)",
    "CREATE INDEX lineage_node_dept_system IF NOT EXISTS "
    "FOR (n:LineageNode) ON (n.project_id, n.department, n.system)",
    "CREATE INDEX lineage_node_priority IF NOT EXISTS "
    "FOR (n:LineageNode) ON (n.project_id, n.priority)",
    "CREATE CONSTRAINT schema_id_unique IF NOT EXISTS "
    "FOR (s:NodeTypeSchema) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT schema_type_unique_per_project IF NOT EXISTS "
    "FOR (s:NodeTypeSchema) REQUIRE (s.project_id, s.type_key) IS UNIQUE",
]


def init_constraints(driver: Driver) -> None:
    """幂等施加 Neo4j 约束与索引。"""
    with driver.session() as session:
        for stmt in _STATEMENTS:
            session.run(stmt)
```

- [ ] **Step 3: 创建 `backend/app/repositories/__init__.py`（空）和 `backend/app/repositories/graph_repo.py`**

```python
from typing import Any

from neo4j import Driver


class GraphRepo:
    """Neo4j 访问封装：统一开 session、参数化执行、record→dict。"""

    def __init__(self, driver: Driver):
        self._driver = driver

    def run_write(self, cypher: str, **params: Any) -> list[dict]:
        with self._driver.session() as session:
            result = session.execute_write(lambda tx: list(tx.run(cypher, **params)))
        return [r.data() for r in result]

    def run_read(self, cypher: str, **params: Any) -> list[dict]:
        with self._driver.session() as session:
            result = session.execute_read(lambda tx: list(tx.run(cypher, **params)))
        return [r.data() for r in result]
```

- [ ] **Step 4: 在 `backend/app/deps.py` 末尾加 graph_repo 依赖**

文件顶部 import 区加：
```python
from app.db.neo4j import get_driver
from app.repositories.graph_repo import GraphRepo
```
末尾追加：
```python
def get_graph_repo() -> GraphRepo:
    return GraphRepo(get_driver())


GraphRepoDep = Annotated[GraphRepo, Depends(get_graph_repo)]
```

- [ ] **Step 5: 在 `backend/tests/conftest.py` 加 Neo4j 容器 fixture**

顶部 import 区加：
```python
from testcontainers.neo4j import Neo4jContainer

from app.db.neo4j_constraints import init_constraints
from app.deps import get_graph_repo
from app.repositories.graph_repo import GraphRepo
```
（`from neo4j import GraphDatabase` 也加到顶部 import。）

新增 session 级 fixture（放在 `mysql_engine` 之后）：
```python
@pytest.fixture(scope="session")
def neo4j_driver():
    with Neo4jContainer("neo4j:5-community") as neo4j:
        driver = GraphDatabase.driver(
            neo4j.get_connection_url(),
            auth=(neo4j.username, neo4j.password),
        )
        init_constraints(driver)
        yield driver
        driver.close()


@pytest.fixture
def graph(neo4j_driver):
    # 每个测试前清空图数据，保证隔离
    with neo4j_driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    return GraphRepo(neo4j_driver)
```

- [ ] **Step 6: 让 `client` fixture 覆盖 graph_repo 指向测试容器**

修改 `client` fixture：增加 `neo4j_driver` 参数，并在 `app.dependency_overrides` 里加 graph_repo 覆盖。把：
```python
@pytest.fixture
def client(mysql_engine):
    TestingSession = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)

    def _override_get_session():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```
改为：
```python
@pytest.fixture
def client(mysql_engine, neo4j_driver):
    TestingSession = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)

    def _override_get_session():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    # 每个测试前清空图数据
    with neo4j_driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_graph_repo] = lambda: GraphRepo(neo4j_driver)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 7: 写测试 `backend/tests/test_neo4j_constraints.py`**

```python
import pytest
from neo4j.exceptions import ClientError

from app.db.neo4j_constraints import init_constraints


def test_init_constraints_idempotent(neo4j_driver):
    # 再次调用不应抛错（IF NOT EXISTS）
    init_constraints(neo4j_driver)
    init_constraints(neo4j_driver)


def test_node_id_unique_enforced(graph, neo4j_driver):
    with neo4j_driver.session() as s:
        s.run("CREATE (:LineageNode {id:'dup', project_id:1, name:'a'})")
        with pytest.raises(ClientError):
            s.run("CREATE (:LineageNode {id:'dup', project_id:1, name:'b'})")


def test_node_name_unique_per_project(graph, neo4j_driver):
    with neo4j_driver.session() as s:
        s.run("CREATE (:LineageNode {id:'n1', project_id:1, name:'same'})")
        with pytest.raises(ClientError):
            s.run("CREATE (:LineageNode {id:'n2', project_id:1, name:'same'})")
        # 不同项目可同名
        s.run("CREATE (:LineageNode {id:'n3', project_id:2, name:'same'})")
```

- [ ] **Step 8: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_neo4j_constraints.py -v`
Expected: 3 passed（首次会拉 neo4j:5-community 镜像，较慢）。

- [ ] **Step 9: 全量回归确认 Phase 1/2 无破坏**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿（新增 3 个 + 既有 80）。

- [ ] **Step 10: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/pyproject.toml backend/app/db/neo4j_constraints.py backend/app/repositories backend/app/deps.py backend/tests/conftest.py backend/tests/test_neo4j_constraints.py
git commit -m "feat: Neo4j 约束初始化、GraphRepo 仓储与 testcontainers fixture"
```
（commit message 末尾附仓库的 Co-Authored-By trailer，照 `git log -1 --format=%B` 的格式。）

## Task 2: 部署脚本 + Pydantic schemas

**Files:**
- Create: `backend/scripts/__init__.py`, `backend/scripts/init_neo4j_constraints.py`
- Create: `backend/app/schemas/graph.py`
- Test: `backend/tests/test_schemas_graph.py`

- [ ] **Step 1: 创建 `backend/scripts/__init__.py`（空）和 `backend/scripts/init_neo4j_constraints.py`**

```python
"""部署用：对配置的 Neo4j 施加约束与索引。运行：python -m scripts.init_neo4j_constraints"""
from app.db.neo4j import close_driver, get_driver
from app.db.neo4j_constraints import init_constraints


def main() -> None:
    driver = get_driver()
    init_constraints(driver)
    print("Neo4j 约束与索引已就绪")
    close_driver()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 写失败测试 `backend/tests/test_schemas_graph.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.graph import CreateNodeRequest, CreateSchemaRequest, SchemaFieldSpec


def test_field_spec_defaults():
    f = SchemaFieldSpec(name="sla", label="SLA", type="string")
    assert f.required is False
    assert f.options is None


def test_create_schema_ok():
    r = CreateSchemaRequest(
        type_key="data_task",
        display_name="数据任务",
        fields=[SchemaFieldSpec(name="engine", label="引擎", type="enum", options=["spark"])],
    )
    assert r.fields[0].type == "enum"


def test_create_node_priority_pattern():
    with pytest.raises(ValidationError):
        CreateNodeRequest(name="n", type="t", priority="P9")


def test_create_node_priority_optional():
    r = CreateNodeRequest(name="n", type="t")
    assert r.priority is None
    assert r.tags == []
    assert r.ext_props == {}
    assert r.is_critical is False
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_schemas_graph.py -v`
Expected: FAIL（ModuleNotFoundError: app.schemas.graph）

- [ ] **Step 4: 创建 `backend/app/schemas/graph.py`**

```python
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FieldType = Literal["string", "number", "url", "enum", "bool"]


class SchemaFieldSpec(BaseModel):
    name: str = Field(min_length=1)
    label: str
    type: FieldType
    required: bool = False
    options: list[str] | None = None
    default: Any | None = None


class CreateSchemaRequest(BaseModel):
    type_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    fields: list[SchemaFieldSpec] = []


class UpdateSchemaRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    fields: list[SchemaFieldSpec] | None = None


class SchemaResponse(BaseModel):
    id: str
    type_key: str
    display_name: str
    fields: list[SchemaFieldSpec]
    created_at: datetime
    updated_at: datetime


_PRIORITY = r"^P[0-5]$"


class CreateNodeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=64)
    description: str | None = None
    owner: str | None = None
    department: str | None = None
    system: str | None = None
    priority: str | None = Field(default=None, pattern=_PRIORITY)
    tags: list[str] = []
    ext_props: dict[str, Any] = {}
    is_critical: bool = False


class UpdateNodeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    owner: str | None = None
    department: str | None = None
    system: str | None = None
    priority: str | None = Field(default=None, pattern=_PRIORITY)
    tags: list[str] | None = None
    ext_props: dict[str, Any] | None = None
    is_critical: bool | None = None


class NodeResponse(BaseModel):
    id: str
    project_id: int
    name: str
    type: str
    description: str | None
    owner: str | None
    department: str | None
    system: str | None
    priority: str | None
    tags: list[str]
    ext_props: dict[str, Any]
    is_critical: bool
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int
    parent_id: str | None
    children_count: int


class SetParentRequest(BaseModel):
    parent_id: str = Field(min_length=1)
```

> 注：`UpdateNodeRequest` 不含 `type`——节点 type 创建后不可改（改 type 等于换 schema 语义，YAGNI，不支持）。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_schemas_graph.py -v`
Expected: 4 passed。

- [ ] **Step 6: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/scripts backend/app/schemas/graph.py backend/tests/test_schemas_graph.py
git commit -m "feat: Neo4j 约束部署脚本与图 Pydantic schemas"
```
（附 Co-Authored-By trailer。）

## Task 3: ext_props 校验器（纯单元）

**Files:**
- Create: `backend/app/services/ext_props.py`
- Test: `backend/tests/test_ext_props.py`

校验器独立成模块，node_service 与 schema_service（兼容性检查）都复用。

- [ ] **Step 1: 写失败测试 `backend/tests/test_ext_props.py`**

```python
import pytest

from app.exceptions import ValidationError
from app.services.ext_props import validate_ext_props

FIELDS = [
    {"name": "engine", "label": "引擎", "type": "enum", "options": ["spark", "hive"], "required": True},
    {"name": "sla", "label": "SLA", "type": "string", "required": False},
    {"name": "retries", "label": "重试", "type": "number", "required": False, "default": 0},
    {"name": "doc", "label": "文档", "type": "url", "required": False},
]


def test_missing_required_raises():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {})


def test_enum_out_of_options_raises():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "flink"})


def test_unknown_field_raises():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "spark", "bogus": 1})


def test_url_prefix_validated():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "spark", "doc": "not-a-url"})


def test_number_type_checked():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "spark", "retries": "three"})


def test_default_filled_when_absent():
    out = validate_ext_props(FIELDS, {"engine": "spark"})
    assert out["retries"] == 0  # default 填入
    assert out["engine"] == "spark"
    assert "sla" not in out  # 非 required 无 default 不填


def test_valid_full():
    out = validate_ext_props(
        FIELDS,
        {"engine": "hive", "sla": "4h", "retries": 3, "doc": "https://x/y"},
    )
    assert out["sla"] == "4h"
    assert out["retries"] == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_ext_props.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 创建 `backend/app/services/ext_props.py`**

```python
from typing import Any

from app.exceptions import ValidationError


def validate_ext_props(
    schema_fields: list[dict], ext_props: dict[str, Any]
) -> dict[str, Any]:
    """按 schema fields 全面严格校验 ext_props，返回补好 default 的规范化结果。

    schema_fields: [{name, label, type, required, options?, default?}, ...]
    校验失败抛 ValidationError(422)，details 带字段名与原因。
    """
    field_by_name = {f["name"]: f for f in schema_fields}

    # 未知字段（schema 未定义）
    unknown = [k for k in ext_props if k not in field_by_name]
    if unknown:
        raise ValidationError(
            "ext_props 含未定义字段", {"unknown_fields": unknown}
        )

    result: dict[str, Any] = {}
    for field in schema_fields:
        name = field["name"]
        ftype = field["type"]
        required = field.get("required", False)
        present = name in ext_props

        if not present:
            if required:
                raise ValidationError(
                    f"缺少必填字段: {name}", {"field": name}
                )
            if "default" in field and field["default"] is not None:
                result[name] = field["default"]
            continue

        value = ext_props[name]
        _check_type(name, ftype, value, field.get("options"))
        result[name] = value

    return result


def _check_type(name: str, ftype: str, value: Any, options: list[str] | None) -> None:
    if ftype == "string":
        if not isinstance(value, str):
            _bad(name, "应为字符串")
    elif ftype == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _bad(name, "应为数字")
    elif ftype == "bool":
        if not isinstance(value, bool):
            _bad(name, "应为布尔值")
    elif ftype == "url":
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            _bad(name, "应为 http(s) URL")
    elif ftype == "enum":
        if not isinstance(value, str) or value not in (options or []):
            _bad(name, f"应为枚举值之一: {options}")
    else:
        _bad(name, f"未知字段类型: {ftype}")


def _bad(name: str, reason: str) -> None:
    raise ValidationError(f"字段 {name} {reason}", {"field": name, "reason": reason})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_ext_props.py -v`
Expected: 7 passed。

- [ ] **Step 5: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/services/ext_props.py backend/tests/test_ext_props.py
git commit -m "feat: ext_props 按 schema 全面严格校验器"
```
（附 Co-Authored-By trailer。）

## Task 4: NodeTypeSchema CRUD（cypher + service + router）

**Files:**
- Create: `backend/app/cypher/__init__.py`（空）, `backend/app/cypher/schemas.py`
- Create: `backend/app/services/schema_service.py`
- Create: `backend/app/routers/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_schema_api.py`

- [ ] **Step 1: 创建 `backend/app/cypher/__init__.py`（空）和 `backend/app/cypher/schemas.py`**

```python
LIST = """
MATCH (s:NodeTypeSchema {project_id: $pid})
RETURN s ORDER BY s.type_key
"""

GET = """
MATCH (s:NodeTypeSchema {project_id: $pid, type_key: $type_key})
RETURN s
"""

CREATE = """
CREATE (s:NodeTypeSchema {
  id: $id, project_id: $pid, type_key: $type_key, display_name: $display_name,
  fields: $fields, created_at: datetime(), updated_at: datetime()
})
RETURN s
"""

UPDATE = """
MATCH (s:NodeTypeSchema {project_id: $pid, type_key: $type_key})
SET s.display_name = $display_name, s.fields = $fields, s.updated_at = datetime()
RETURN s
"""

DELETE = """
MATCH (s:NodeTypeSchema {project_id: $pid, type_key: $type_key})
DELETE s
"""

COUNT_NODES_OF_TYPE = """
MATCH (n:LineageNode {project_id: $pid, type: $type_key})
RETURN count(n) AS cnt
"""

LIST_NODES_OF_TYPE = """
MATCH (n:LineageNode {project_id: $pid, type: $type_key})
RETURN n
"""
```

- [ ] **Step 2: 创建 `backend/app/services/schema_service.py`**

```python
import json
import uuid
from datetime import datetime
from typing import Any

from app.cypher import schemas as q
from app.exceptions import ConflictError, NotFoundError
from app.repositories.graph_repo import GraphRepo
from app.services.ext_props import validate_ext_props


def _row_to_schema(node: dict) -> dict:
    data = dict(node)
    data["fields"] = json.loads(data.get("fields") or "[]")
    return data


def list_schemas(repo: GraphRepo, pid: int) -> list[dict]:
    rows = repo.run_read(q.LIST, pid=pid)
    return [_row_to_schema(r["s"]) for r in rows]


def get_schema(repo: GraphRepo, pid: int, type_key: str) -> dict:
    rows = repo.run_read(q.GET, pid=pid, type_key=type_key)
    if not rows:
        raise NotFoundError("schema 不存在", {"type_key": type_key})
    return _row_to_schema(rows[0]["s"])


def create_schema(
    repo: GraphRepo, pid: int, type_key: str, display_name: str, fields: list[dict]
) -> dict:
    existing = repo.run_read(q.GET, pid=pid, type_key=type_key)
    if existing:
        raise ConflictError("该 type_key 已存在", {"type_key": type_key})
    rows = repo.run_write(
        q.CREATE,
        id=str(uuid.uuid4()),
        pid=pid,
        type_key=type_key,
        display_name=display_name,
        fields=json.dumps(fields),
    )
    return _row_to_schema(rows[0]["s"])


def update_schema(
    repo: GraphRepo, pid: int, type_key: str, display_name: str | None, fields: list[dict] | None
) -> dict:
    current = get_schema(repo, pid, type_key)  # 404 if missing
    new_display = display_name if display_name is not None else current["display_name"]
    new_fields = fields if fields is not None else current["fields"]

    # 兼容性检查：新 fields 跑该 type 所有现有节点的 ext_props
    if fields is not None:
        node_rows = repo.run_read(q.LIST_NODES_OF_TYPE, pid=pid, type_key=type_key)
        conflicts = []
        for nr in node_rows:
            node = dict(nr["n"])
            ext = json.loads(node.get("ext_props") or "{}")
            try:
                validate_ext_props(new_fields, ext)
            except Exception as e:  # noqa: BLE001 — 收集为冲突明细
                conflicts.append(
                    {"node_id": node.get("id"), "name": node.get("name"), "error": str(e)}
                )
        if conflicts:
            raise ConflictError(
                "新 schema 与现有节点不兼容",
                {"conflicts": conflicts},
            )

    rows = repo.run_write(
        q.UPDATE,
        pid=pid,
        type_key=type_key,
        display_name=new_display,
        fields=json.dumps(new_fields),
    )
    return _row_to_schema(rows[0]["s"])


def delete_schema(repo: GraphRepo, pid: int, type_key: str) -> None:
    get_schema(repo, pid, type_key)  # 404 if missing
    cnt = repo.run_read(q.COUNT_NODES_OF_TYPE, pid=pid, type_key=type_key)[0]["cnt"]
    if cnt > 0:
        raise ConflictError("仍有节点使用该 type，无法删除", {"node_count": cnt})
    repo.run_write(q.DELETE, pid=pid, type_key=type_key)
```

> `ConflictError` 默认 code 是 `CONFLICT`。spec 提到的 `SCHEMA_CONFLICT`/`SCHEMA_INCOMPATIBLE`/`SCHEMA_IN_USE` 通过 details 区分；若要精确 code，可在 details 里带 `reason`。本实现用统一 `CONFLICT` + details 描述，保持与 Phase 2 一致（避免新增异常类）。

- [ ] **Step 3: 创建 `backend/app/routers/schemas.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import CreateSchemaRequest, SchemaResponse, UpdateSchemaRequest
from app.services import schema_service

router = APIRouter(prefix="/api/v1/projects/{pid}/schemas", tags=["schemas"])


@router.get("", response_model=list[SchemaResponse])
def list_schemas(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> list[SchemaResponse]:
    return schema_service.list_schemas(repo, ctx.project.id)


@router.post("", response_model=SchemaResponse, status_code=status.HTTP_201_CREATED)
def create_schema(
    payload: CreateSchemaRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> SchemaResponse:
    fields = [f.model_dump() for f in payload.fields]
    return schema_service.create_schema(
        repo, ctx.project.id, payload.type_key, payload.display_name, fields
    )


@router.get("/{type_key}", response_model=SchemaResponse)
def get_schema(
    type_key: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> SchemaResponse:
    return schema_service.get_schema(repo, ctx.project.id, type_key)


@router.put("/{type_key}", response_model=SchemaResponse)
def update_schema(
    type_key: str,
    payload: UpdateSchemaRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> SchemaResponse:
    fields = [f.model_dump() for f in payload.fields] if payload.fields is not None else None
    return schema_service.update_schema(
        repo, ctx.project.id, type_key, payload.display_name, fields
    )


@router.delete("/{type_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schema(
    type_key: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    repo: GraphRepoDep,
) -> None:
    schema_service.delete_schema(repo, ctx.project.id, type_key)
    return None
```

> `SchemaResponse` 用 `from_attributes` 不适用（service 返回 dict）。FastAPI 用 `response_model` 会对返回的 dict 做校验/序列化——service 返回的 dict 含 `id/type_key/display_name/fields/created_at/updated_at`，字段齐全，可直接通过。Neo4j `datetime()` 返回的是 neo4j.time.DateTime，`.data()` 后需能被 Pydantic 解析为 datetime——见 Step 5 验证；若不兼容，在 `_row_to_schema` 里 `.to_native()` 转换。

- [ ] **Step 4: `backend/app/main.py` 注册 schemas 路由**

在 members_router 注册之后追加：
```python
    from app.routers import schemas as schemas_router

    app.include_router(schemas_router.router)
```

- [ ] **Step 5: 写测试 `backend/tests/test_schema_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_create_and_get_schema(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/schemas",
        json={"type_key": "data_task", "display_name": "数据任务",
              "fields": [{"name": "engine", "label": "引擎", "type": "enum",
                          "options": ["spark"], "required": True}]},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 201
    assert r.json()["type_key"] == "data_task"
    r2 = client.get(f"/api/v1/projects/{p.id}/schemas/data_task", headers=_auth(seed, owner))
    assert r2.status_code == 200
    assert r2.json()["fields"][0]["name"] == "engine"


def test_duplicate_type_key_409(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    body = {"type_key": "t", "display_name": "T", "fields": []}
    client.post(f"/api/v1/projects/{p.id}/schemas", json=body, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/schemas", json=body, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_list_schemas(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    for tk in ["a", "b"]:
        client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": tk, "display_name": tk, "fields": []},
                    headers=_auth(seed, owner))
    r = client.get(f"/api/v1/projects/{p.id}/schemas", headers=_auth(seed, owner))
    assert {s["type_key"] for s in r.json()} == {"a", "b"}


def test_get_missing_schema_404(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.get(f"/api/v1/projects/{p.id}/schemas/nope", headers=_auth(seed, owner))
    assert r.status_code == 404


def test_update_schema_display_name(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "old", "fields": []},
                headers=_auth(seed, owner))
    r = client.put(f"/api/v1/projects/{p.id}/schemas/t",
                   json={"display_name": "new"}, headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["display_name"] == "new"


def test_delete_schema(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    r = client.delete(f"/api/v1/projects/{p.id}/schemas/t", headers=_auth(seed, owner))
    assert r.status_code == 204


def test_schema_write_requires_editor(client, seed):
    owner = seed.user("owner")
    viewer = seed.user("viewer")
    p = seed.project(owner)
    seed.member(p, viewer, "viewer")
    r = client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": "t", "display_name": "T", "fields": []},
                    headers=_auth(seed, viewer))
    assert r.status_code == 403


def test_schema_delete_requires_admin(client, seed):
    owner = seed.user("owner")
    editor = seed.user("editor")
    p = seed.project(owner)
    seed.member(p, editor, "editor")
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    r = client.delete(f"/api/v1/projects/{p.id}/schemas/t", headers=_auth(seed, editor))
    assert r.status_code == 403
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_schema_api.py -v`
Expected: 8 passed。若 datetime 序列化报错，在 `schema_service._row_to_schema` 里把 `created_at`/`updated_at` 用 `.to_native()` 转 Python datetime（neo4j.time.DateTime → datetime）。

- [ ] **Step 8: 全量回归**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿。

- [ ] **Step 9: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher backend/app/services/schema_service.py backend/app/routers/schemas.py backend/app/main.py backend/tests/conftest.py backend/tests/test_schema_api.py
git commit -m "feat: NodeTypeSchema CRUD（cypher+service+router）与兼容性检查"
```
（附 Co-Authored-By trailer。）

## Task 5: 节点 CRUD（cypher + service + router）

**Files:**
- Create: `backend/app/cypher/nodes.py`
- Create: `backend/app/services/node_service.py`
- Create: `backend/app/routers/nodes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_node_api.py`

- [ ] **Step 1: 创建 `backend/app/cypher/nodes.py`**

```python
CREATE = """
CREATE (n:LineageNode {
  id: $id, project_id: $pid, name: $name, type: $type, description: $description,
  owner: $owner, department: $department, system: $system, priority: $priority,
  tags: $tags, ext_props: $ext_props, is_critical: $is_critical,
  created_at: datetime(), updated_at: datetime(), created_by: $uid, updated_by: $uid
})
RETURN n
"""

GET = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
OPTIONAL MATCH (n)<-[:CHILD_OF]-(child:LineageNode)
RETURN n, parent.id AS parent_id, count(DISTINCT child) AS children_count
"""

UPDATE = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
SET n += $props, n.updated_at = datetime(), n.updated_by = $uid
WITH n
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
OPTIONAL MATCH (n)<-[:CHILD_OF]-(child:LineageNode)
RETURN n, parent.id AS parent_id, count(DISTINCT child) AS children_count
"""

DELETE = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
DETACH DELETE n
"""

# 列表：用可选过滤；None 参数表示该过滤不生效
LIST = """
MATCH (n:LineageNode {project_id: $pid})
WHERE ($type IS NULL OR n.type = $type)
  AND ($department IS NULL OR n.department = $department)
  AND ($system IS NULL OR n.system = $system)
  AND ($priority IS NULL OR n.priority = $priority)
  AND ($tag IS NULL OR $tag IN n.tags)
  AND ($name IS NULL OR toLower(n.name) CONTAINS toLower($name))
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
OPTIONAL MATCH (n)<-[:CHILD_OF]-(child:LineageNode)
WITH n, parent.id AS parent_id, count(DISTINCT child) AS children_count
WHERE ($parent_id IS NULL OR parent_id = $parent_id)
  AND ($has_parent IS NULL OR (parent_id IS NOT NULL) = $has_parent)
RETURN n, parent_id, children_count
ORDER BY n.name
"""

EXISTS = """
MATCH (n:LineageNode {project_id: $pid, id: $nid}) RETURN n.id AS id
"""
```

- [ ] **Step 2: 创建 `backend/app/services/node_service.py`**

```python
import json
import uuid
from typing import Any

from neo4j.exceptions import ConstraintError

from app.cypher import nodes as q
from app.cypher import schemas as sq
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.graph_repo import GraphRepo
from app.services.ext_props import validate_ext_props

_NODE_SCALARS = [
    "name", "description", "owner", "department", "system", "priority", "is_critical",
]


def _schema_fields(repo: GraphRepo, pid: int, type_key: str) -> list[dict]:
    rows = repo.run_read(sq.GET, pid=pid, type_key=type_key)
    if not rows:
        raise ValidationError("该 type 尚未定义 schema", {"type": type_key})
    return json.loads(dict(rows[0]["s"]).get("fields") or "[]")


def _row_to_node(row: dict) -> dict:
    node = dict(row["n"])
    node["ext_props"] = json.loads(node.get("ext_props") or "{}")
    node["tags"] = list(node.get("tags") or [])
    node["parent_id"] = row.get("parent_id")
    node["children_count"] = row.get("children_count", 0)
    return node


def create_node(repo: GraphRepo, pid: int, uid: int, payload: dict) -> dict:
    fields = _schema_fields(repo, pid, payload["type"])
    norm_ext = validate_ext_props(fields, payload.get("ext_props") or {})
    try:
        rows = repo.run_write(
            q.CREATE,
            id=str(uuid.uuid4()), pid=pid, uid=uid,
            name=payload["name"], type=payload["type"],
            description=payload.get("description"), owner=payload.get("owner"),
            department=payload.get("department"), system=payload.get("system"),
            priority=payload.get("priority"), tags=payload.get("tags") or [],
            ext_props=json.dumps(norm_ext), is_critical=payload.get("is_critical", False),
        )
    except ConstraintError:
        raise ConflictError("节点名称在项目内已存在", {"name": payload["name"]})
    # CREATE 不返回 parent/children，补默认
    node = dict(rows[0]["n"])
    node["ext_props"] = json.loads(node.get("ext_props") or "{}")
    node["tags"] = list(node.get("tags") or [])
    node["parent_id"] = None
    node["children_count"] = 0
    return node


def get_node(repo: GraphRepo, pid: int, nid: str) -> dict:
    rows = repo.run_read(q.GET, pid=pid, nid=nid)
    if not rows:
        raise NotFoundError("节点不存在", {"id": nid})
    return _row_to_node(rows[0])


def list_nodes(repo: GraphRepo, pid: int, filters: dict) -> list[dict]:
    rows = repo.run_read(
        q.LIST, pid=pid,
        type=filters.get("type"), department=filters.get("department"),
        system=filters.get("system"), priority=filters.get("priority"),
        tag=filters.get("tag"), name=filters.get("name"),
        parent_id=filters.get("parent_id"), has_parent=filters.get("has_parent"),
    )
    return [_row_to_node(r) for r in rows]


def update_node(repo: GraphRepo, pid: int, nid: str, uid: int, patch: dict) -> dict:
    current = get_node(repo, pid, nid)  # 404 if missing
    props: dict[str, Any] = {}
    for key in _NODE_SCALARS:
        if key in patch and patch[key] is not None:
            props[key] = patch[key]
    if "tags" in patch and patch["tags"] is not None:
        props["tags"] = patch["tags"]
    if "ext_props" in patch and patch["ext_props"] is not None:
        fields = _schema_fields(repo, pid, current["type"])
        props["ext_props"] = json.dumps(validate_ext_props(fields, patch["ext_props"]))
    try:
        rows = repo.run_write(q.UPDATE, pid=pid, nid=nid, uid=uid, props=props)
    except ConstraintError:
        raise ConflictError("节点名称在项目内已存在", {"name": patch.get("name")})
    return _row_to_node(rows[0])


def delete_node(repo: GraphRepo, pid: int, nid: str) -> None:
    get_node(repo, pid, nid)  # 404 if missing
    repo.run_write(q.DELETE, pid=pid, nid=nid)
```

> `n += $props` 是 Neo4j 的 map 合并赋值，只更新提供的键。`ext_props` 整体替换（PATCH 语义下传 ext_props 即全量替换该字段，符合"改节点同建节点校验"）。

- [ ] **Step 3: 创建 `backend/app/routers/nodes.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import CreateNodeRequest, NodeResponse, UpdateNodeRequest
from app.services import node_service

router = APIRouter(prefix="/api/v1/projects/{pid}/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeResponse])
def list_nodes(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    type: Annotated[str | None, Query()] = None,
    department: Annotated[str | None, Query()] = None,
    system: Annotated[str | None, Query()] = None,
    priority: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    parent_id: Annotated[str | None, Query()] = None,
    has_parent: Annotated[bool | None, Query()] = None,
) -> list[NodeResponse]:
    filters = {
        "type": type, "department": department, "system": system, "priority": priority,
        "tag": tag, "name": name, "parent_id": parent_id, "has_parent": has_parent,
    }
    return node_service.list_nodes(repo, ctx.project.id, filters)


@router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
def create_node(
    payload: CreateNodeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> NodeResponse:
    return node_service.create_node(repo, ctx.project.id, ctx.user.id, payload.model_dump())


@router.get("/{nid}", response_model=NodeResponse)
def get_node(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> NodeResponse:
    return node_service.get_node(repo, ctx.project.id, nid)


@router.patch("/{nid}", response_model=NodeResponse)
def update_node(
    nid: str,
    payload: UpdateNodeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> NodeResponse:
    return node_service.update_node(
        repo, ctx.project.id, nid, ctx.user.id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{nid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> None:
    node_service.delete_node(repo, ctx.project.id, nid)
    return None
```

> `model_dump(exclude_unset=True)` 让 PATCH 只带用户实际传的字段，避免把未传字段当成"设为 None"。

- [ ] **Step 4: `backend/app/main.py` 注册 nodes 路由**

在 schemas_router 注册之后追加：
```python
    from app.routers import nodes as nodes_router

    app.include_router(nodes_router.router)
```

- [ ] **Step 5: 写测试 `backend/tests/test_node_api.py`**

```python
def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _mk_schema(client, seed, p, owner, fields=None):
    client.post(
        f"/api/v1/projects/{p.id}/schemas",
        json={"type_key": "data_task", "display_name": "DT", "fields": fields or []},
        headers=_auth(seed, owner),
    )


def test_create_node_ok(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner,
               [{"name": "engine", "label": "引擎", "type": "enum",
                 "options": ["spark"], "required": True}])
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "ods", "type": "data_task", "ext_props": {"engine": "spark"}},
                    headers=_auth(seed, owner))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "ods"
    assert body["ext_props"]["engine"] == "spark"
    assert body["parent_id"] is None
    assert body["children_count"] == 0


def test_create_node_without_schema_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "x", "type": "unknown_type"},
                    headers=_auth(seed, owner))
    assert r.status_code == 422


def test_create_node_bad_ext_props_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner,
               [{"name": "engine", "label": "引擎", "type": "enum",
                 "options": ["spark"], "required": True}])
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "x", "type": "data_task", "ext_props": {"engine": "flink"}},
                    headers=_auth(seed, owner))
    assert r.status_code == 422


def test_node_name_conflict_409(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    body = {"name": "dup", "type": "data_task"}
    client.post(f"/api/v1/projects/{p.id}/nodes", json=body, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/nodes", json=body, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_get_and_update_node(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    nid = client.post(f"/api/v1/projects/{p.id}/nodes",
                      json={"name": "n", "type": "data_task"},
                      headers=_auth(seed, owner)).json()["id"]
    r = client.patch(f"/api/v1/projects/{p.id}/nodes/{nid}",
                     json={"description": "d", "priority": "P1"},
                     headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["description"] == "d"
    assert r.json()["priority"] == "P1"


def test_list_nodes_filter_by_type_and_name(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    for nm in ["alpha", "beta"]:
        client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": nm, "type": "data_task"}, headers=_auth(seed, owner))
    r = client.get(f"/api/v1/projects/{p.id}/nodes?name=alph", headers=_auth(seed, owner))
    assert {n["name"] for n in r.json()} == {"alpha"}
    r2 = client.get(f"/api/v1/projects/{p.id}/nodes?type=data_task", headers=_auth(seed, owner))
    assert {n["name"] for n in r2.json()} == {"alpha", "beta"}


def test_delete_node(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    nid = client.post(f"/api/v1/projects/{p.id}/nodes",
                      json={"name": "n", "type": "data_task"},
                      headers=_auth(seed, owner)).json()["id"]
    r = client.delete(f"/api/v1/projects/{p.id}/nodes/{nid}", headers=_auth(seed, owner))
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/projects/{p.id}/nodes/{nid}", headers=_auth(seed, owner))
    assert r2.status_code == 404


def test_node_write_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer")
    _mk_schema(client, seed, p, owner)
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "n", "type": "data_task"}, headers=_auth(seed, viewer))
    assert r.status_code == 403
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_node_api.py -v`
Expected: 8 passed。

- [ ] **Step 7: 全量回归**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿。

- [ ] **Step 8: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher/nodes.py backend/app/services/node_service.py backend/app/routers/nodes.py backend/app/main.py backend/tests/test_node_api.py
git commit -m "feat: 节点 CRUD（cypher+service+router）含 ext_props 校验与 name 唯一"
```
（附 Co-Authored-By trailer。）

## Task 6: 父子关系（设/解父、子节点/后代、成环预检）

**Files:**
- Modify: `backend/app/cypher/nodes.py`（加父子 Cypher）
- Modify: `backend/app/services/node_service.py`（加 set_parent/clear_parent/list_children/list_descendants）
- Modify: `backend/app/routers/nodes.py`（加 4 个父子端点）
- Test: `backend/tests/test_parent_api.py`

- [ ] **Step 1: 在 `backend/app/cypher/nodes.py` 末尾追加父子 Cypher**

```python
# 成环预检：parent 是否已是 nid 的后代（存在则设置会成环）
PARENT_WOULD_CYCLE = """
MATCH (parent:LineageNode {project_id: $pid, id: $parent_id})
      -[:CHILD_OF*1..]->(target:LineageNode {project_id: $pid, id: $nid})
RETURN count(*) > 0 AS would_cycle
"""

# 删旧父边 + 建新父边（单一父亲）
CLEAR_PARENT = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})-[r:CHILD_OF]->()
DELETE r
"""

SET_PARENT = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
MATCH (p:LineageNode {project_id: $pid, id: $parent_id})
CREATE (n)-[:CHILD_OF]->(p)
"""

LIST_CHILDREN = """
MATCH (parent:LineageNode {project_id: $pid, id: $nid})<-[:CHILD_OF]-(child:LineageNode)
OPTIONAL MATCH (child)<-[:CHILD_OF]-(gc:LineageNode)
RETURN child AS n, $nid AS parent_id, count(DISTINCT gc) AS children_count
ORDER BY child.name
"""

LIST_DESCENDANTS = """
MATCH (parent:LineageNode {project_id: $pid, id: $nid})<-[:CHILD_OF*1..]-(d:LineageNode)
OPTIONAL MATCH (d)-[:CHILD_OF]->(dp:LineageNode)
OPTIONAL MATCH (d)<-[:CHILD_OF]-(dc:LineageNode)
RETURN DISTINCT d AS n, dp.id AS parent_id, count(DISTINCT dc) AS children_count
ORDER BY d.name
"""
```

- [ ] **Step 2: 在 `backend/app/services/node_service.py` 末尾追加父子操作**

```python
def set_parent(repo: GraphRepo, pid: int, nid: str, parent_id: str) -> None:
    if parent_id == nid:
        raise ValidationError("节点不能将自己设为父节点", {"id": nid})
    # 两节点都须存在于本项目
    if not repo.run_read(q.EXISTS, pid=pid, nid=nid):
        raise NotFoundError("节点不存在", {"id": nid})
    if not repo.run_read(q.EXISTS, pid=pid, nid=parent_id):
        raise NotFoundError("父节点不存在", {"id": parent_id})
    cycle = repo.run_read(q.PARENT_WOULD_CYCLE, pid=pid, nid=nid, parent_id=parent_id)
    if cycle and cycle[0]["would_cycle"]:
        raise ValidationError("设置父节点会形成环", {"code": "PARENT_CYCLE"})
    repo.run_write(q.CLEAR_PARENT, pid=pid, nid=nid)  # 单一父亲：先清旧
    repo.run_write(q.SET_PARENT, pid=pid, nid=nid, parent_id=parent_id)


def clear_parent(repo: GraphRepo, pid: int, nid: str) -> None:
    if not repo.run_read(q.EXISTS, pid=pid, nid=nid):
        raise NotFoundError("节点不存在", {"id": nid})
    repo.run_write(q.CLEAR_PARENT, pid=pid, nid=nid)


def list_children(repo: GraphRepo, pid: int, nid: str) -> list[dict]:
    if not repo.run_read(q.EXISTS, pid=pid, nid=nid):
        raise NotFoundError("节点不存在", {"id": nid})
    return [_row_to_node(r) for r in repo.run_read(q.LIST_CHILDREN, pid=pid, nid=nid)]


def list_descendants(repo: GraphRepo, pid: int, nid: str) -> list[dict]:
    if not repo.run_read(q.EXISTS, pid=pid, nid=nid):
        raise NotFoundError("节点不存在", {"id": nid})
    return [_row_to_node(r) for r in repo.run_read(q.LIST_DESCENDANTS, pid=pid, nid=nid)]
```

> `PARENT_CYCLE` 用 `ValidationError`（422）携带 details.code 区分。注意 spec 提到 400，但 Phase 1 的 `ValidationError` 固定 422；为与既有体系一致用 422，details.code=PARENT_CYCLE 标识。自环/跨项目同样 422。

- [ ] **Step 3: 在 `backend/app/routers/nodes.py` 末尾追加 4 个端点**

先在文件顶部 import 补 `SetParentRequest`：把
```python
from app.schemas.graph import CreateNodeRequest, NodeResponse, UpdateNodeRequest
```
改为
```python
from app.schemas.graph import (
    CreateNodeRequest,
    NodeResponse,
    SetParentRequest,
    UpdateNodeRequest,
)
```
末尾追加：
```python
@router.post("/{nid}/parent", status_code=status.HTTP_204_NO_CONTENT)
def set_parent(
    nid: str,
    payload: SetParentRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> None:
    node_service.set_parent(repo, ctx.project.id, nid, payload.parent_id)
    return None


@router.delete("/{nid}/parent", status_code=status.HTTP_204_NO_CONTENT)
def clear_parent(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> None:
    node_service.clear_parent(repo, ctx.project.id, nid)
    return None


@router.get("/{nid}/children", response_model=list[NodeResponse])
def list_children(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> list[NodeResponse]:
    return node_service.list_children(repo, ctx.project.id, nid)


@router.get("/{nid}/descendants", response_model=list[NodeResponse])
def list_descendants(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> list[NodeResponse]:
    return node_service.list_descendants(repo, ctx.project.id, nid)
```

- [ ] **Step 4: 写测试 `backend/tests/test_parent_api.py`**

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


def test_set_and_get_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    parent = _mk_node(client, seed, p, owner, "parent")
    r = client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent",
                    json={"parent_id": parent}, headers=_auth(seed, owner))
    assert r.status_code == 204
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] == parent


def test_list_children_and_descendants(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")  # 顶
    b = _mk_node(client, seed, p, owner, "b")  # a 的子
    c = _mk_node(client, seed, p, owner, "c")  # b 的子
    client.post(f"/api/v1/projects/{p.id}/nodes/{b}/parent", json={"parent_id": a}, headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes/{c}/parent", json={"parent_id": b}, headers=_auth(seed, owner))
    children = client.get(f"/api/v1/projects/{p.id}/nodes/{a}/children", headers=_auth(seed, owner)).json()
    assert {n["name"] for n in children} == {"b"}
    desc = client.get(f"/api/v1/projects/{p.id}/nodes/{a}/descendants", headers=_auth(seed, owner)).json()
    assert {n["name"] for n in desc} == {"b", "c"}


def test_parent_cycle_rejected(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    client.post(f"/api/v1/projects/{p.id}/nodes/{b}/parent", json={"parent_id": a}, headers=_auth(seed, owner))
    # 把 a 的父设为 b → 成环
    r = client.post(f"/api/v1/projects/{p.id}/nodes/{a}/parent",
                    json={"parent_id": b}, headers=_auth(seed, owner))
    assert r.status_code == 422
    assert r.json()["error"]["details"].get("code") == "PARENT_CYCLE"


def test_self_parent_rejected(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    r = client.post(f"/api/v1/projects/{p.id}/nodes/{a}/parent",
                    json={"parent_id": a}, headers=_auth(seed, owner))
    assert r.status_code == 422


def test_reparent_single_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    p1 = _mk_node(client, seed, p, owner, "p1")
    p2 = _mk_node(client, seed, p, owner, "p2")
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": p1}, headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": p2}, headers=_auth(seed, owner))
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] == p2  # 单一父亲，换成 p2


def test_clear_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    parent = _mk_node(client, seed, p, owner, "parent")
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": parent}, headers=_auth(seed, owner))
    r = client.delete(f"/api/v1/projects/{p.id}/nodes/{child}/parent", headers=_auth(seed, owner))
    assert r.status_code == 204
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] is None


def test_delete_parent_orphans_child(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    parent = _mk_node(client, seed, p, owner, "parent")
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": parent}, headers=_auth(seed, owner))
    client.delete(f"/api/v1/projects/{p.id}/nodes/{parent}", headers=_auth(seed, owner))
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] is None  # 父删除后 child 变顶层，自身仍在
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_parent_api.py -v`
Expected: 7 passed。

- [ ] **Step 6: 全量回归**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/app/cypher/nodes.py backend/app/services/node_service.py backend/app/routers/nodes.py backend/tests/test_parent_api.py
git commit -m "feat: 父子 CHILD_OF 关系（设/解父、子节点/后代、成环预检）"
```
（附 Co-Authored-By trailer。）

## Task 7: 图端点权限矩阵 + DoD

**Files:**
- Test: `backend/tests/test_graph_permission_matrix.py`

覆盖 spec §5.11/§5.3：schema 写 editor+、schema 删 admin+、节点写 editor+、读 viewer+。

- [ ] **Step 1: 写 `backend/tests/test_graph_permission_matrix.py`**

```python
import pytest


def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _setup_caller(seed, p, owner, actor, role):
    if role != "owner":
        seed.member(p, actor, role)
        return actor
    return owner


# (角色, 建 schema POST, 建节点 POST, 删 schema DELETE) 期望状态码
# schema/node 写需 editor+；删 schema 需 admin+
MATRIX = [
    ("owner", 201, 201, 204),
    ("admin", 201, 201, 204),
    ("editor", 201, 201, 403),
    ("viewer", 403, 403, 403),
]


@pytest.mark.parametrize("role,schema_code,node_code,del_code", MATRIX, ids=[r[0] for r in MATRIX])
def test_graph_write_endpoints_by_role(client, seed, role, schema_code, node_code, del_code):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)

    # 建 schema（type_key 唯一，用角色名区分避免容器内冲突；图数据每测试已清空）
    tk = f"t_{role}"
    r = client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": tk, "display_name": "T", "fields": []},
                    headers=_auth(seed, caller))
    assert r.status_code == schema_code

    # 建节点（需 schema 先存在；用 owner 确保 schema 在，再用 caller 建节点）
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "shared", "display_name": "S", "fields": []},
                headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": f"n_{role}", "type": "shared"},
                    headers=_auth(seed, caller))
    assert r.status_code == node_code

    # 删 schema（删 shared；owner 先确保存在）
    r = client.delete(f"/api/v1/projects/{p.id}/schemas/shared", headers=_auth(seed, caller))
    # 若该角色建了节点（editor+），shared 可能被占用；为隔离删除权限，删一个空 type
    if del_code == 204:
        # 建一个无节点的空 type 再删，验证删除权限
        client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": "empty", "display_name": "E", "fields": []},
                    headers=_auth(seed, owner))
        r2 = client.delete(f"/api/v1/projects/{p.id}/schemas/empty", headers=_auth(seed, caller))
        assert r2.status_code == 204
    else:
        assert r.status_code == del_code


@pytest.mark.parametrize("role", [r[0] for r in MATRIX])
def test_graph_read_allows_all_members(client, seed, role):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)
    assert client.get(f"/api/v1/projects/{p.id}/schemas", headers=_auth(seed, caller)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, caller)).status_code == 200
```

> 删 schema 权限测试有占用态干扰，故 editor/viewer 行直接断言对 `shared`（可能被占用）的删除返回 403（权限在占用检查之前，editor 删 schema 本就 403）；owner/admin 行用一个无节点的 `empty` type 验证 204。

- [ ] **Step 2: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_graph_permission_matrix.py -v`
Expected: 8 passed（4 write + 4 read）。

- [ ] **Step 3: 全量回归 + DoD 验证**

Run: `cd backend && . .venv/bin/activate && pytest -q 2>&1 | tail -3`
Expected: 全绿（Phase 1+2+3A）。

- [ ] **Step 4: 对真实 Neo4j 验证约束脚本（DoD）**

Run:
```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8 && docker compose up -d neo4j
sleep 20  # 等 neo4j 起来
cd backend && . .venv/bin/activate && python -m scripts.init_neo4j_constraints
```
Expected: 打印 "Neo4j 约束与索引已就绪"，无报错。
然后核对：`docker compose exec neo4j cypher-shell -u neo4j -p neo4jpassword "SHOW CONSTRAINTS"` 应列出 4 个约束。

- [ ] **Step 5: Commit**

```bash
cd /Users/zyc/Data/App/obsidian/pawnZzz/tmp8
git add backend/tests/test_graph_permission_matrix.py
git commit -m "test: 图端点权限矩阵（schema/node × 角色）"
```
（附 Co-Authored-By trailer。）

## Phase 3A 完成标准（Definition of Done）

- [ ] 全量 `pytest` 绿（Phase 1+2+3A，无回归）。
- [ ] `python -m scripts.init_neo4j_constraints` 对真实 Neo4j 成功建 4 约束 + 3 索引。
- [ ] 完整流程可走通：建 schema → 建节点（ext_props 严格校验）→ 设父子 → 查子节点/后代 → 改节点 → 删节点（DETACH）。
- [ ] 权限符合 spec §5.3/§5.4/§5.11（schema 删 admin+、写 editor+、读 viewer+）。
- [ ] 错误响应符合 §8 信封（404/403/409/422）。
- [ ] name 项目内唯一（Neo4j 约束 + 409）、设父成环预检（422 PARENT_CYCLE）。

## 下一子项目预告（不在本计划内）

3B：依赖边 `:DEPENDS_ON` CRUD + 图查询/算法（上下游遍历、影响分析、关键路径、环检测、子图渲染），复用 3A 的 graph_repo / cypher/ 目录 / 节点模型，并补 NodeResponse 的 upstream_count/downstream_count。
