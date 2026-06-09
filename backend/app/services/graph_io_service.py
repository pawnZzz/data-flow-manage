import logging

from app.cypher import nodes as nq
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories.graph_repo import GraphRepo
from app.services import edge_service, node_service, schema_service

logger = logging.getLogger("app.audit")

_NODE_KEYS = [
    "name", "type", "description", "owner", "department", "system",
    "priority", "tags", "ext_props", "is_critical",
]
_NODE_DEFAULTS = {"tags": [], "ext_props": {}, "is_critical": False}
_EDGE_KEYS = ["edge_type", "description", "is_required", "strength", "ext_props"]
# 非空字段的兜底，与 _NODE_DEFAULTS 对称：防 Neo4j 漏存稀疏属性时 ExportEdge 校验失败
_EDGE_DEFAULTS = {"edge_type": "data_flow", "is_required": True, "strength": "strong", "ext_props": {}}


def export_graph(repo: GraphRepo, pid: int) -> dict:
    schemas = schema_service.list_schemas(repo, pid)
    nodes_raw = node_service.list_nodes(repo, pid, {})
    edges_raw = edge_service.list_edges(repo, pid, {})
    id2name = {n["id"]: n["name"] for n in nodes_raw}

    nodes = []
    for n in sorted(nodes_raw, key=lambda x: x["name"]):
        item = {k: n.get(k, _NODE_DEFAULTS.get(k)) for k in _NODE_KEYS}
        item["parent"] = id2name.get(n["parent_id"]) if n.get("parent_id") else None
        nodes.append(item)

    edges = []
    for e in edges_raw:
        item = {k: e.get(k, _EDGE_DEFAULTS.get(k)) for k in _EDGE_KEYS}
        item["source"] = id2name[e["source_id"]]
        item["target"] = id2name[e["target_id"]]
        edges.append(item)

    return {"schemas": schemas, "nodes": nodes, "edges": edges}


def _find_id(repo: GraphRepo, pid: int, name: str) -> str | None:
    rows = repo.run_read(nq.GET_BY_NAME, pid=pid, name=name)
    return rows[0]["id"] if rows else None


def import_graph(repo: GraphRepo, pid: int, uid: int, payload: dict) -> dict:
    """合并导入全图：schemas→nodes→parents→edges，按名复用、冲突跳过。

    非事务、尽力而为：中途失败已写入的留存；因合并语义幂等，可安全重导。
    """
    created_schemas = reused_schemas = 0
    created_nodes = reused_nodes = set_parents = 0
    created_edges = skipped_edges = 0
    name_to_id: dict[str, str] = {}

    for s in payload["schemas"]:
        try:
            schema_service.get_schema(repo, pid, s["type_key"])
            reused_schemas += 1
        except NotFoundError:
            schema_service.create_schema(repo, pid, s["type_key"], s["display_name"], s["fields"])
            created_schemas += 1

    for n in payload["nodes"]:
        existing = _find_id(repo, pid, n["name"])
        if existing:
            name_to_id[n["name"]] = existing
            reused_nodes += 1
            continue
        node = node_service.create_node(repo, pid, uid, {
            "name": n["name"], "type": n["type"], "description": n["description"],
            "owner": n["owner"], "department": n["department"], "system": n["system"],
            "priority": n["priority"], "tags": n["tags"], "ext_props": n["ext_props"],
            "is_critical": n["is_critical"],
        })
        name_to_id[n["name"]] = node["id"]
        created_nodes += 1

    for n in payload["nodes"]:
        if not n.get("parent"):
            continue
        child = name_to_id.get(n["name"]) or _find_id(repo, pid, n["name"])
        parent = name_to_id.get(n["parent"]) or _find_id(repo, pid, n["parent"])
        if not child or not parent:
            continue
        try:
            node_service.set_parent(repo, pid, child, parent)
            set_parents += 1
        except (ValidationError, NotFoundError):
            pass

    for e in payload["edges"]:
        sid = name_to_id.get(e["source"]) or _find_id(repo, pid, e["source"])
        tid = name_to_id.get(e["target"]) or _find_id(repo, pid, e["target"])
        if not sid or not tid:
            skipped_edges += 1
            continue
        try:
            edge_service.create_edge(repo, pid, uid, {
                "source_id": sid, "target_id": tid, "edge_type": e["edge_type"],
                "description": e["description"], "is_required": e["is_required"],
                "strength": e["strength"], "ext_props": e["ext_props"],
            })
            created_edges += 1
        except (ConflictError, ValidationError):
            skipped_edges += 1

    logger.info("graph.import pid=%s by=%s created_nodes=%s created_edges=%s",
                pid, uid, created_nodes, created_edges)
    return {
        "created_schemas": created_schemas, "reused_schemas": reused_schemas,
        "created_nodes": created_nodes, "reused_nodes": reused_nodes,
        "set_parents": set_parents,
        "created_edges": created_edges, "skipped_edges": skipped_edges,
    }
