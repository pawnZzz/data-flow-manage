PURGE_NODES = """
MATCH (n:LineageNode {project_id: $pid})
DETACH DELETE n
RETURN count(n) AS deleted_nodes
"""

PURGE_SCHEMAS = """
MATCH (s:NodeTypeSchema {project_id: $pid})
DELETE s
RETURN count(s) AS deleted_schemas
"""
