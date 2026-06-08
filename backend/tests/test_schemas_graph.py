import pytest
from pydantic import ValidationError

from app.schemas.graph import CreateNodeRequest, CreateSchemaRequest, SchemaFieldSpec


def test_field_spec_defaults():
    f = SchemaFieldSpec(name="sla", label="SLA", type="string")
    assert f.required is False
    assert f.options is None


def test_create_schema_ok():
    r = CreateSchemaRequest(
        type_key="data_task",
        display_name="数据任务",
        fields=[SchemaFieldSpec(name="engine", label="引擎", type="enum", options=["spark"])],
    )
    assert r.fields[0].type == "enum"


def test_create_node_priority_pattern():
    with pytest.raises(ValidationError):
        CreateNodeRequest(name="n", type="t", priority="P9")


def test_create_node_priority_optional():
    r = CreateNodeRequest(name="n", type="t")
    assert r.priority is None
    assert r.tags == []
    assert r.ext_props == {}
    assert r.is_critical is False
