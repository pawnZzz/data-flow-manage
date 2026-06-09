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
            # ConflictError=边已存在(EDGE_EXISTS)；ValidationError=自环(SELF_LOOP)。两者都视作跳过。
            skipped_edges += 1

    logger.info(
        "sql_import.commit pid=%s by=%s created_nodes=%s reused_nodes=%s "
        "created_edges=%s skipped_edges=%s",
        pid, uid, created_nodes, reused_nodes, created_edges, skipped_edges,
    )
    return {"created_nodes": created_nodes, "reused_nodes": reused_nodes,
            "created_edges": created_edges, "skipped_edges": skipped_edges}
