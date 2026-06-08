import pytest
from neo4j.exceptions import ClientError

from app.db.neo4j_constraints import init_constraints


def test_init_constraints_idempotent(neo4j_driver):
    init_constraints(neo4j_driver)
    init_constraints(neo4j_driver)


# `graph` 仅用于触发每测试的图清理（副作用）
def test_node_id_unique_enforced(graph, neo4j_driver):
    with neo4j_driver.session() as s:
        s.run("CREATE (:LineageNode {id:'dup', project_id:1, name:'a'})")
        with pytest.raises(ClientError):
            s.run("CREATE (:LineageNode {id:'dup', project_id:1, name:'b'})")


# `graph` 仅用于触发每测试的图清理（副作用）
def test_node_name_unique_per_project(graph, neo4j_driver):
    with neo4j_driver.session() as s:
        s.run("CREATE (:LineageNode {id:'n1', project_id:1, name:'same'})")
        with pytest.raises(ClientError):
            s.run("CREATE (:LineageNode {id:'n2', project_id:1, name:'same'})")
        s.run("CREATE (:LineageNode {id:'n3', project_id:2, name:'same'})")
