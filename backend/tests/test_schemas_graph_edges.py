import pytest
from pydantic import ValidationError

from app.schemas.graph import (
    CreateEdgeRequest,
    GraphNode,
    NodeResponse,
)


def test_create_edge_defaults():
    r = CreateEdgeRequest(source_id="a", target_id="b")
    assert r.edge_type == "data_flow"
    assert r.is_required is True
    assert r.strength == "strong"
    assert r.ext_props == {}


def test_create_edge_rejects_bad_edge_type():
    with pytest.raises(ValidationError):
        CreateEdgeRequest(source_id="a", target_id="b", edge_type="bogus")


def test_create_edge_rejects_bad_strength():
    with pytest.raises(ValidationError):
        CreateEdgeRequest(source_id="a", target_id="b", strength="medium")


def test_node_response_counts_default_zero():
    n = NodeResponse(
        id="n", project_id=1, name="x", type="t",
        tags=[], ext_props={}, is_critical=False,
        created_at="2026-06-09T00:00:00", updated_at="2026-06-09T00:00:00",
        created_by=1, updated_by=1, children_count=0,
    )
    assert n.upstream_count == 0
    assert n.downstream_count == 0


def test_graph_node_minimal():
    g = GraphNode(id="n", name="x", type="t", is_critical=False)
    assert g.priority is None
    assert g.parent_id is None
