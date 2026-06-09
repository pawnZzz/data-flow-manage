import json
import logging
import uuid
from typing import Any

from app.cypher import edges as q
from app.cypher import inline_depth
from app.cypher import nodes as nodes_q
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.graph_repo import GraphRepo

logger = logging.getLogger("app.audit")

_EDGE_SCALARS = ["edge_type", "description", "is_required", "strength"]


def _row_to_edge(edge: dict) -> dict:
    data = dict(edge)
    data["ext_props"] = json.loads(data.get("ext_props") or "{}")
    created = data.get("created_at")
    if hasattr(created, "to_native"):
        data["created_at"] = created.to_native()
    return data


def _node_exists(repo: GraphRepo, pid: int, nid: str) -> bool:
    return bool(repo.run_read(nodes_q.EXISTS, pid=pid, nid=nid))


def create_edge(repo: GraphRepo, pid: int, uid: int, payload: dict) -> dict:
    source_id, target_id = payload["source_id"], payload["target_id"]
    if source_id == target_id:
        raise ValidationError("边的两端不能是同一节点", {"code": "SELF_LOOP"})
    if not _node_exists(repo, pid, source_id):
        raise NotFoundError("源节点不存在", {"id": source_id})
    if not _node_exists(repo, pid, target_id):
        raise NotFoundError("目标节点不存在", {"id": target_id})

    rows = repo.run_write(
        q.CREATE_IF_ABSENT,
        pid=pid, id=str(uuid.uuid4()), source_id=source_id, target_id=target_id,
        edge_type=payload.get("edge_type", "data_flow"),
        description=payload.get("description"),
        is_required=payload.get("is_required", True),
        strength=payload.get("strength", "strong"),
        ext_props=json.dumps(payload.get("ext_props") or {}),
        uid=uid,
    )
    if not rows:
        raise ConflictError("两节点间已存在依赖边", {"code": "EDGE_EXISTS"})

    cycle = repo.run_read(inline_depth(q.CREATES_CYCLE), pid=pid, source_id=source_id)
    creates_cycle = bool(cycle and cycle[0]["creates_cycle"])
    edge = _row_to_edge(rows[0]["edge"])
    logger.info("edge.create pid=%s eid=%s by=%s", pid, edge["id"], uid)
    return {"edge": edge, "warnings": {"creates_cycle": creates_cycle}}


def get_edge(repo: GraphRepo, pid: int, eid: str) -> dict:
    rows = repo.run_read(q.GET, pid=pid, eid=eid)
    if not rows:
        raise NotFoundError("依赖边不存在", {"id": eid})
    return _row_to_edge(rows[0]["edge"])


def list_edges(repo: GraphRepo, pid: int, filters: dict) -> list[dict]:
    rows = repo.run_read(
        q.LIST, pid=pid,
        source_id=filters.get("source_id"), target_id=filters.get("target_id"),
        edge_type=filters.get("edge_type"),
    )
    return [_row_to_edge(r["edge"]) for r in rows]


def update_edge(repo: GraphRepo, pid: int, eid: str, uid: int, patch: dict) -> dict:
    get_edge(repo, pid, eid)  # 404 if missing
    props: dict[str, Any] = {}
    for key in _EDGE_SCALARS:
        if key in patch and patch[key] is not None:
            props[key] = patch[key]
    if "ext_props" in patch and patch["ext_props"] is not None:
        props["ext_props"] = json.dumps(patch["ext_props"])
    rows = repo.run_write(q.UPDATE, pid=pid, eid=eid, props=props)
    logger.info("edge.update pid=%s eid=%s by=%s", pid, eid, uid)
    return _row_to_edge(rows[0]["edge"])


def delete_edge(repo: GraphRepo, pid: int, eid: str, uid: int) -> None:
    rows = repo.run_write(q.DELETE, pid=pid, eid=eid)
    if not rows or rows[0]["deleted"] == 0:
        raise NotFoundError("依赖边不存在", {"id": eid})
    logger.info("edge.delete pid=%s eid=%s by=%s", pid, eid, uid)
