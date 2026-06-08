from neo4j import Driver

# spec §4.4 约束与索引；IF NOT EXISTS 保证幂等
_DDL_STATEMENTS = [
    "CREATE CONSTRAINT lineage_node_id_unique IF NOT EXISTS "
    "FOR (n:LineageNode) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT lineage_node_name_unique IF NOT EXISTS "
    "FOR (n:LineageNode) REQUIRE (n.project_id, n.name) IS UNIQUE",
    "CREATE INDEX lineage_node_project_type IF NOT EXISTS "
    "FOR (n:LineageNode) ON (n.project_id, n.type)",
    "CREATE INDEX lineage_node_dept_system IF NOT EXISTS "
    "FOR (n:LineageNode) ON (n.project_id, n.department, n.system)",
    "CREATE INDEX lineage_node_priority IF NOT EXISTS "
    "FOR (n:LineageNode) ON (n.project_id, n.priority)",
    "CREATE CONSTRAINT schema_id_unique IF NOT EXISTS "
    "FOR (s:NodeTypeSchema) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT schema_type_unique_per_project IF NOT EXISTS "
    "FOR (s:NodeTypeSchema) REQUIRE (s.project_id, s.type_key) IS UNIQUE",
]


def init_constraints(driver: Driver) -> None:
    """幂等施加 Neo4j 约束与索引。"""
    with driver.session() as session:
        # DDL 走自动提交事务；IF NOT EXISTS 保证幂等
        for stmt in _DDL_STATEMENTS:
            session.run(stmt)
