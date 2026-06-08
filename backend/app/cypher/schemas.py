LIST = """
MATCH (s:NodeTypeSchema {project_id: $pid})
RETURN s ORDER BY s.type_key
"""

GET = """
MATCH (s:NodeTypeSchema {project_id: $pid, type_key: $type_key})
RETURN s
"""

CREATE = """
CREATE (s:NodeTypeSchema {
  id: $id, project_id: $pid, type_key: $type_key, display_name: $display_name,
  fields: $fields, created_at: datetime(), updated_at: datetime()
})
RETURN s
"""

UPDATE = """
MATCH (s:NodeTypeSchema {project_id: $pid, type_key: $type_key})
SET s.display_name = $display_name, s.fields = $fields, s.updated_at = datetime()
RETURN s
"""

DELETE = """
MATCH (s:NodeTypeSchema {project_id: $pid, type_key: $type_key})
DELETE s
"""

COUNT_NODES_OF_TYPE = """
MATCH (n:LineageNode {project_id: $pid, type: $type_key})
RETURN count(n) AS cnt
"""

LIST_NODES_OF_TYPE = """
MATCH (n:LineageNode {project_id: $pid, type: $type_key})
RETURN n
"""
