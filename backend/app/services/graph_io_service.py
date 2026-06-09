import logging

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
