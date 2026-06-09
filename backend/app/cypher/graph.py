# 子图/环检测里把关系、节点投影成普通 map（ext_props/created_at 在 Python 再 coerce）。
# parent_id 用 pattern comprehension 取（节点至多一个 CHILD_OF 出边）。
GNODE = (
    "{id:x.id, name:x.name, type:x.type, priority:x.priority, "
    "is_critical:x.is_critical, parent_id: head([(x)-[:CHILD_OF]->(pp) | pp.id])}"
)
EDGE_FROM_REL = (
    "{id:r.id, project_id:startNode(r).project_id, source_id:startNode(r).id, "
    "target_id:endNode(r).id, edge_type:r.edge_type, description:r.description, "
    "is_required:r.is_required, strength:r.strength, ext_props:r.ext_props, "
    "created_at:r.created_at, created_by:r.created_by}"
)

# 遍历结果节点用「邻居计数」（省得每个结果再跑变长遍历）。m AS n 对齐 _row_to_node。
_TRAVERSE_RETURN = """
WITH DISTINCT m
OPTIONAL MATCH (m)-[:CHILD_OF]->(parent:LineageNode)
RETURN m AS n, parent.id AS parent_id,
  COUNT { (m)<-[:CHILD_OF]-(:LineageNode) } AS children_count,
  COUNT { (m)-[:DEPENDS_ON]->(:LineageNode) } AS upstream_count,
  COUNT { (m)<-[:DEPENDS_ON]-(:LineageNode) } AS downstream_count
ORDER BY m.name SKIP $offset LIMIT $limit
"""

UPSTREAM = (
    "MATCH (start:LineageNode {project_id: $pid, id: $nid})"
    "-[:DEPENDS_ON*1..__DEPTH__]->(m:LineageNode)" + _TRAVERSE_RETURN
)
DOWNSTREAM = (
    "MATCH (start:LineageNode {project_id: $pid, id: $nid})"
    "<-[:DEPENDS_ON*1..__DEPTH__]-(m:LineageNode)" + _TRAVERSE_RETURN
)
UPSTREAM_COUNT = """
MATCH (start:LineageNode {project_id: $pid, id: $nid})-[:DEPENDS_ON*1..__DEPTH__]->(m:LineageNode)
RETURN count(DISTINCT m) AS total
"""
DOWNSTREAM_COUNT = """
MATCH (start:LineageNode {project_id: $pid, id: $nid})<-[:DEPENDS_ON*1..__DEPTH__]-(m:LineageNode)
RETURN count(DISTINCT m) AS total
"""

# 某节点参与的环（impact 用）
NODE_CYCLES = (
    "MATCH path=(n:LineageNode {project_id: $pid, id: $nid})-[:DEPENDS_ON*1..__DEPTH__]->(n) "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges LIMIT 50"
)
