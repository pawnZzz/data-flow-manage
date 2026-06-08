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
OPTIONAL MATCH (n)<-[:CHILD_OF]-(child:LineageNode)
RETURN n, parent.id AS parent_id, count(DISTINCT child) AS children_count
"""

UPDATE = """
MATCH (n:LineageNode {project_id: $pid, id: $nid})
SET n += $props, n.updated_at = datetime(), n.updated_by = $uid
WITH n
OPTIONAL MATCH (n)-[:CHILD_OF]->(parent:LineageNode)
OPTIONAL MATCH (n)<-[:CHILD_OF]-(child:LineageNode)
RETURN n, parent.id AS parent_id, count(DISTINCT child) AS children_count
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
RETURN n, parent_id, children_count
ORDER BY n.name
"""

EXISTS = """
MATCH (n:LineageNode {project_id: $pid, id: $nid}) RETURN n.id AS id
"""
