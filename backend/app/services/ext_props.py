from typing import Any

from app.exceptions import ValidationError


def validate_ext_props(
    schema_fields: list[dict], ext_props: dict[str, Any]
) -> dict[str, Any]:
    """按 schema fields 全面严格校验 ext_props，返回补好 default 的规范化结果。

    schema_fields: [{name, label, type, required, options?, default?}, ...]
    校验失败抛 ValidationError(422)，details 带字段名与原因。
    """
    field_by_name = {f["name"]: f for f in schema_fields}

    # 未知字段（schema 未定义）
    unknown = [k for k in ext_props if k not in field_by_name]
    if unknown:
        raise ValidationError(
            "ext_props 含未定义字段", {"unknown_fields": unknown}
        )

    result: dict[str, Any] = {}
    for field in schema_fields:
        name = field["name"]
        ftype = field["type"]
        required = field.get("required", False)
        present = name in ext_props

        if not present:
            if required:
                raise ValidationError(
                    f"缺少必填字段: {name}", {"field": name}
                )
            if "default" in field and field["default"] is not None:
                result[name] = field["default"]
            continue

        value = ext_props[name]
        _check_type(name, ftype, value, field.get("options"))
        result[name] = value

    return result


def _check_type(name: str, ftype: str, value: Any, options: list[str] | None) -> None:
    if ftype == "string":
        if not isinstance(value, str):
            _bad(name, "应为字符串")
    elif ftype == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _bad(name, "应为数字")
    elif ftype == "bool":
        if not isinstance(value, bool):
            _bad(name, "应为布尔值")
    elif ftype == "url":
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            _bad(name, "应为 http(s) URL")
    elif ftype == "enum":
        if not isinstance(value, str) or value not in (options or []):
            _bad(name, f"应为枚举值之一: {options}")
    else:
        _bad(name, f"未知字段类型: {ftype}")


def _bad(name: str, reason: str) -> None:
    raise ValidationError(f"字段 {name} {reason}", {"field": name, "reason": reason})
