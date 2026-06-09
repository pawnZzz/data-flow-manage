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

# 模式 1：下游影响面最大的节点 → 取其最深下游链（score=影响面）
CRITICAL_IMPACT = (
    "MATCH (n:LineageNode {project_id: $pid}) "
    "OPTIONAL MATCH (n)<-[:DEPENDS_ON*1..__DEPTH__]-(d:LineageNode) "
    "WITH n, count(DISTINCT d) AS impact ORDER BY impact DESC LIMIT 1 "
    "MATCH path = (n)<-[:DEPENDS_ON*1..__DEPTH__]-(leaf:LineageNode) "
    "WHERE NOT (leaf)<-[:DEPENDS_ON]-() "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges, "
    "length(path) AS depth, impact AS score ORDER BY depth DESC LIMIT 1"
)

# 模式 2：DAG 最长链 top5（无入边起点 → 无出边终点）
CRITICAL_LONGEST = (
    "MATCH path = (start:LineageNode {project_id: $pid})"
    "-[:DEPENDS_ON*1..__DEPTH__]->(end:LineageNode) "
    "WHERE NOT ()-[:DEPENDS_ON]->(start) AND NOT (end)-[:DEPENDS_ON]->() "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges, "
    "length(path) AS depth, null AS score ORDER BY depth DESC LIMIT 5"
)

# 子图收集后回捞内部边的公共尾部
_SUBGRAPH_TAIL = (
    "WITH collect(DISTINCT n) AS ns "
    "UNWIND ns AS node "
    "OPTIONAL MATCH (node)-[r:DEPENDS_ON]->(other:LineageNode) WHERE other IN ns "
    "WITH ns, collect(DISTINCT r) AS rels "
    "RETURN [x IN ns | " + GNODE + "] AS nodes, "
    "[r IN rels | " + EDGE_FROM_REL + "] AS edges"
)

# __D__ 为 clamp 后的请求深度（服务层 replace）
SUBGRAPH_BOTH = (
    "MATCH (center:LineageNode {project_id: $pid, id: $center_id}) "
    "CALL { WITH center MATCH (center)-[:DEPENDS_ON*0..__D__]->(n:LineageNode) RETURN n "
    "UNION WITH center MATCH (center)<-[:DEPENDS_ON*0..__D__]-(n:LineageNode) RETURN n } "
    + _SUBGRAPH_TAIL
)
SUBGRAPH_UP = (
    "MATCH (center:LineageNode {project_id: $pid, id: $center_id}) "
    "MATCH (center)-[:DEPENDS_ON*0..__D__]->(n:LineageNode) " + _SUBGRAPH_TAIL
)
SUBGRAPH_DOWN = (
    "MATCH (center:LineageNode {project_id: $pid, id: $center_id}) "
    "MATCH (center)<-[:DEPENDS_ON*0..__D__]-(n:LineageNode) " + _SUBGRAPH_TAIL
)
FULL_GRAPH = (
    "MATCH (n:LineageNode {project_id: $pid}) " + _SUBGRAPH_TAIL
)

# 注：环检测受 __DEPTH__ 上限约束，超过 max_traversal_depth 跳的超长环不计
HAS_CYCLE = (
    "RETURN EXISTS { MATCH (n:LineageNode {project_id: $pid})"
    "-[:DEPENDS_ON*1..__DEPTH__]->(n) } AS has"
)
PROJECT_CYCLES = (
    "MATCH path=(n:LineageNode {project_id: $pid})-[:DEPENDS_ON*1..__DEPTH__]->(n) "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges LIMIT 50"
)

# 模式 3：手动关键节点两两 shortestPath。node_ids 给定则用之，否则用 is_critical
CRITICAL_MANUAL = (
    "MATCH (a:LineageNode {project_id: $pid}) "
    "MATCH (b:LineageNode {project_id: $pid}) "
    "WHERE a.id <> b.id AND "
    "(($node_ids IS NULL AND a.is_critical AND b.is_critical) OR "
    " ($node_ids IS NOT NULL AND a.id IN $node_ids AND b.id IN $node_ids)) "
    "MATCH path = shortestPath((a)-[:DEPENDS_ON*1..__DEPTH__]->(b)) "
    "RETURN [x IN nodes(path) | " + GNODE + "] AS nodes, "
    "[r IN relationships(path) | " + EDGE_FROM_REL + "] AS edges, "
    "length(path) AS depth, null AS score ORDER BY depth DESC LIMIT 5"
)
