# 边响应统一投影：关系本身不存 project_id/source/target，从两端节点取
_EDGE = """{
  id: r.id, project_id: s.project_id, source_id: s.id, target_id: t.id,
  edge_type: r.edge_type, description: r.description, is_required: r.is_required,
  strength: r.strength, ext_props: r.ext_props, created_at: r.created_at,
  created_by: r.created_by
}"""

# 条件创建：两端点须存在且尚无 (s)->(t) 边，否则返回 0 行
CREATE_IF_ABSENT = """
MATCH (s:LineageNode {project_id: $pid, id: $source_id})
MATCH (t:LineageNode {project_id: $pid, id: $target_id})
WHERE NOT (s)-[:DEPENDS_ON]->(t)
CREATE (s)-[r:DEPENDS_ON {
  id: $id, edge_type: $edge_type, description: $description,
  is_required: $is_required, strength: $strength, ext_props: $ext_props,
  created_at: datetime(), created_by: $uid
}]->(t)
RETURN __EDGE__ AS edge
""".replace("__EDGE__", _EDGE)

# 建边后判是否成环：s 能否沿出边回到自身
CREATES_CYCLE = """
MATCH (s:LineageNode {project_id: $pid, id: $source_id})
RETURN EXISTS { MATCH (s)-[:DEPENDS_ON*1..__DEPTH__]->(s) } AS creates_cycle
"""

GET = """
MATCH (s:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(t:LineageNode)
RETURN __EDGE__ AS edge
""".replace("__EDGE__", _EDGE)

LIST = """
MATCH (s:LineageNode {project_id: $pid})-[r:DEPENDS_ON]->(t:LineageNode)
WHERE ($source_id IS NULL OR s.id = $source_id)
  AND ($target_id IS NULL OR t.id = $target_id)
  AND ($edge_type IS NULL OR r.edge_type = $edge_type)
RETURN __EDGE__ AS edge
ORDER BY r.created_at
""".replace("__EDGE__", _EDGE)

UPDATE = """
MATCH (s:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(t:LineageNode)
SET r += $props
RETURN __EDGE__ AS edge
""".replace("__EDGE__", _EDGE)

DELETE = """
MATCH (:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(:LineageNode)
DELETE r
RETURN count(r) AS deleted
"""

EXISTS = """
MATCH (:LineageNode {project_id: $pid})-[r:DEPENDS_ON {id: $eid}]->(:LineageNode)
RETURN r.id AS id
"""
