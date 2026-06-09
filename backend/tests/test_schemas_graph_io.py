import pytest
from pydantic import ValidationError

from app.schemas.graph_io import ExportNode, ImportRequest


def test_export_node_defaults():
    n = ExportNode(name="dw.t", type="t")
    assert n.parent is None
    assert n.tags == [] and n.ext_props == {} and n.is_critical is False


def test_export_node_requires_name():
    with pytest.raises(ValidationError):
        ExportNode(name="", type="t")


def test_import_request_defaults_empty():
    r = ImportRequest()
    assert r.schemas == [] and r.nodes == [] and r.edges == []
