import json

from app.config import get_settings
from app.cypher import graph as q
from app.cypher import inline_depth
from app.repositories.graph_repo import GraphRepo
from app.services.node_service import _row_to_node, get_node


def _coerce_edge(e: dict) -> dict:
    e = dict(e)
    e["ext_props"] = json.loads(e.get("ext_props") or "{}")
    created = e.get("created_at")
    if hasattr(created, "to_native"):
        e["created_at"] = created.to_native()
    return e


def _coerce_cycle(row: dict) -> dict:
    return {"nodes": row["nodes"], "edges": [_coerce_edge(e) for e in row["edges"]]}


def _traverse(repo: GraphRepo, pid: int, nid: str, direction: str, limit: int, offset: int) -> dict:
    get_node(repo, pid, nid)  # 404 if node missing
    list_q = q.UPSTREAM if direction == "upstream" else q.DOWNSTREAM
    count_q = q.UPSTREAM_COUNT if direction == "upstream" else q.DOWNSTREAM_COUNT
    rows = repo.run_read(inline_depth(list_q), pid=pid, nid=nid, limit=limit, offset=offset)
    total = repo.run_read(inline_depth(count_q), pid=pid, nid=nid)[0]["total"]
    return {"items": [_row_to_node(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


def upstream(repo: GraphRepo, pid: int, nid: str, limit: int, offset: int) -> dict:
    return _traverse(repo, pid, nid, "upstream", limit, offset)


def downstream(repo: GraphRepo, pid: int, nid: str, limit: int, offset: int) -> dict:
    return _traverse(repo, pid, nid, "downstream", limit, offset)


def impact(repo: GraphRepo, pid: int, nid: str) -> dict:
    get_node(repo, pid, nid)  # 404 if missing
    up_total = repo.run_read(inline_depth(q.UPSTREAM_COUNT), pid=pid, nid=nid)[0]["total"]
    down_total = repo.run_read(inline_depth(q.DOWNSTREAM_COUNT), pid=pid, nid=nid)[0]["total"]
    up_rows = repo.run_read(inline_depth(q.UPSTREAM), pid=pid, nid=nid, limit=up_total, offset=0)
    down_rows = repo.run_read(inline_depth(q.DOWNSTREAM), pid=pid, nid=nid, limit=down_total, offset=0)
    cycles = repo.run_read(inline_depth(q.NODE_CYCLES), pid=pid, nid=nid)
    return {
        "upstream": [_row_to_node(r) for r in up_rows],
        "downstream": [_row_to_node(r) for r in down_rows],
        "warnings": {"cycles": [_coerce_cycle(c) for c in cycles]},
    }


_CRITICAL_Q = {
    "impact": q.CRITICAL_IMPACT,
    "longest": q.CRITICAL_LONGEST,
    "manual": q.CRITICAL_MANUAL,
}


def _coerce_path(row: dict) -> dict:
    return {
        "nodes": row["nodes"],
        "edges": [_coerce_edge(e) for e in row["edges"]],
        "depth": row["depth"],
        "score": row.get("score"),
    }


def critical_paths(repo: GraphRepo, pid: int, mode: str, node_ids: list | None) -> dict:
    rows = repo.run_read(inline_depth(_CRITICAL_Q[mode]), pid=pid, node_ids=node_ids)
    return {"mode": mode, "paths": [_coerce_path(r) for r in rows]}


_SUBGRAPH_Q = {"upstream": q.SUBGRAPH_UP, "downstream": q.SUBGRAPH_DOWN, "both": q.SUBGRAPH_BOTH}


def _clamp_depth(d: int) -> int:
    return max(0, min(d, get_settings().max_traversal_depth))


def subgraph(repo: GraphRepo, pid: int, center: str | None, depth: int, direction: str) -> dict:
    # 两套深度占位符：__D__ 是请求深度（clamp 后 replace），__DEPTH__ 是 config 上限（inline_depth）
    if center is None:
        rows = repo.run_read(q.FULL_GRAPH, pid=pid)
    else:
        get_node(repo, pid, center)  # 404 if center missing
        cypher = _SUBGRAPH_Q[direction].replace("__D__", str(_clamp_depth(depth)))
        rows = repo.run_read(cypher, pid=pid, center_id=center)
    nodes = rows[0]["nodes"] if rows else []
    edges = [_coerce_edge(e) for e in (rows[0]["edges"] if rows else [])]
    has_cycle = repo.run_read(inline_depth(q.HAS_CYCLE), pid=pid)[0]["has"]
    return {
        "nodes": nodes, "edges": edges,
        "stats": {"node_count": len(nodes), "edge_count": len(edges), "has_cycle": has_cycle},
    }


def cycles(repo: GraphRepo, pid: int) -> list[dict]:
    rows = repo.run_read(inline_depth(q.PROJECT_CYCLES), pid=pid)
    return [_coerce_cycle(r) for r in rows]
