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


def _coerce_datetimes(node: dict) -> None:
    # neo4j.time.DateTime → Python datetime（Pydantic 不识别前者）
    for key in ("created_at", "updated_at"):
        value = node.get(key)
        if hasattr(value, "to_native"):
            node[key] = value.to_native()


def _row_to_node(row: dict) -> dict:
    node = dict(row["n"])
    node["ext_props"] = json.loads(node.get("ext_props") or "{}")
    node["tags"] = list(node.get("tags") or [])
    node["parent_id"] = row.get("parent_id")
    node["children_count"] = row.get("children_count", 0)
    _coerce_datetimes(node)
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
    _coerce_datetimes(node)
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
