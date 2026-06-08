import json
import uuid

from app.cypher import schemas as q
from app.exceptions import ConflictError, NotFoundError
from app.repositories.graph_repo import GraphRepo
from app.services.ext_props import validate_ext_props


def _row_to_schema(node: dict) -> dict:
    data = dict(node)
    data["fields"] = json.loads(data.get("fields") or "[]")
    # neo4j.time.DateTime → Python datetime（Pydantic 不识别前者）
    for key in ("created_at", "updated_at"):
        value = data.get(key)
        if hasattr(value, "to_native"):
            data[key] = value.to_native()
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
            except Exception as e:  # noqa: BLE001 — 收集所有冲突节点
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
