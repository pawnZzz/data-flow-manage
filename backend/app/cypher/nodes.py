CREATE = """
CREATE (n:LineageNode {
  id: $id, project_id: $pid, name: $name, type: $type, description: $description,
  owner: $owner, department: $department, system: $system, priority: $priority,
  tags: $tags, ext_props: $ext_props, is_critical: $is_critical,
  created_at: datetime(), updated_at: datetime(), created_by: $uid, updated_by: $uid
})
RETURN n
"""

GET = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
RETURN n, parent.id AS parent_id,
  COUNT { (n)<-[:CHILD_OF]-(:LineageNode) } AS children_count,
  COUNT { MATCH (n)-[:DEPENDS_ON*1..__DEPTH__]->(m:LineageNode) RETURN DISTINCT m } AS upstream_count,
  COUNT { MATCH (n)<-[:DEPENDS_ON*1..__DEPTH__]-(m:LineageNode) RETURN DISTINCT m } AS downstream_count
"""

UPDATE = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
SET n += $props, n.updated_at = datetime(), n.updated_by = $uid
WITH n
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
RETURN n, parent.id AS parent_id,
  COUNT { (n)<-[:CHILD_OF]-(:LineageNode) } AS children_count,
  COUNT { (n)-[:DEPENDS_ON]->(:LineageNode) } AS upstream_count,
  COUNT { (n)<-[:DEPENDS_ON]-(:LineageNode) } AS downstream_count
"""

DELETE = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
DETACH DELETE n
"""

# 列表：用可选过滤；None 参数表示该过滤不生效
LIST = """
MATCH (n:LineageNode {project_id: $pid})
WHERE ($type IS NULL OR n.type = $type)
  AND ($department IS NULL OR n.department = $department)
  AND ($system IS NULL OR n.system = $system)
  AND ($priority IS NULL OR n.priority = $priority)
  AND ($tag IS NULL OR $tag IN n.tags)
  AND ($name IS NULL OR toLower(n.name) CONTAINS toLower($name))
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
OPTIONAL MATCH (n)<-[:CHILD_OF]-(child:LineageNode)
WITH n, parent.id AS parent_id, count(DISTINCT child) AS children_count
WHERE ($parent_id IS NULL OR parent_id = $parent_id)
  AND ($has_parent IS NULL OR (parent_id IS NOT NULL) = $has_parent)
RETURN n, parent_id, children_count,
  COUNT { (n)-[:DEPENDS_ON]->(:LineageNode) } AS upstream_count,
  COUNT { (n)<-[:DEPENDS_ON]-(:LineageNode) } AS downstream_count
ORDER BY n.name
"""

EXISTS = """
MATCH (n:LineageNode {project_id: $pid, id: $nid}) RETURN n.id AS id
"""

GET_BY_NAME = """
MATCH (n:LineageNode {project_id: $pid, name: $name}) RETURN n.id AS id
"""

# 成环预检：parent 是否已是 nid 的后代（存在则设置会成环）
PARENT_WOULD_CYCLE = """
MATCH (parent:LineageNode {project_id: $pid, id: $parent_id})
      -[:CHILD_OF*1..]->(target:LineageNode {project_id: $pid, id: $nid})
RETURN count(*) > 0 AS would_cycle
"""

# 删旧父边 + 建新父边（单一父亲）
CLEAR_PARENT = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})-[r:CHILD_OF]->()
DELETE r
"""

SET_PARENT = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
MATCH (p:LineageNode {project_id: $pid, id: $parent_id})
CREATE (n)-[:CHILD_OF]->(p)
"""

LIST_CHILDREN = """
MATCH (parent:LineageNode {project_id: $pid, id: $nid})<-[:CHILD_OF]-(child:LineageNode)
OPTIONAL MATCH (child)<-[:CHILD_OF]-(gc:LineageNode)
RETURN child AS n, $nid AS parent_id, count(DISTINCT gc) AS children_count
ORDER BY child.name
"""

LIST_DESCENDANTS = """
MATCH (parent:LineageNode {project_id: $pid, id: $nid})<-[:CHILD_OF*1..]-(d:LineageNode)
OPTIONAL MATCH (d)-[:CHILD_OF]->(dp:LineageNode)
OPTIONAL MATCH (d)<-[:CHILD_OF]-(dc:LineageNode)
RETURN DISTINCT d AS n, dp.id AS parent_id, count(DISTINCT dc) AS children_count
ORDER BY d.name
"""
