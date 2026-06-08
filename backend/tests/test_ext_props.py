import pytest

from app.exceptions import ValidationError
from app.services.ext_props import validate_ext_props

FIELDS = [
    {"name": "engine", "label": "引擎", "type": "enum", "options": ["spark", "hive"], "required": True},
    {"name": "sla", "label": "SLA", "type": "string", "required": False},
    {"name": "retries", "label": "重试", "type": "number", "required": False, "default": 0},
    {"name": "doc", "label": "文档", "type": "url", "required": False},
]


def test_missing_required_raises():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {})


def test_enum_out_of_options_raises():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "flink"})


def test_unknown_field_raises():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "spark", "bogus": 1})


def test_url_prefix_validated():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "spark", "doc": "not-a-url"})


def test_number_type_checked():
    with pytest.raises(ValidationError):
        validate_ext_props(FIELDS, {"engine": "spark", "retries": "three"})


def test_default_filled_when_absent():
    out = validate_ext_props(FIELDS, {"engine": "spark"})
    assert out["retries"] == 0  # default 填入
    assert out["engine"] == "spark"
    assert "sla" not in out  # 非 required 无 default 不填


def test_valid_full():
    out = validate_ext_props(
        FIELDS,
        {"engine": "hive", "sla": "4h", "retries": 3, "doc": "https://x/y"},
    )
    assert out["sla"] == "4h"
    assert out["retries"] == 3
