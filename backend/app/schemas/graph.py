from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FieldType = Literal["string", "number", "url", "enum", "bool"]


class SchemaFieldSpec(BaseModel):
    name: str = Field(min_length=1)
    label: str
    type: FieldType
    required: bool = False
    options: list[str] | None = None
    default: Any | None = None


class CreateSchemaRequest(BaseModel):
    type_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    fields: list[SchemaFieldSpec] = []


class UpdateSchemaRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    fields: list[SchemaFieldSpec] | None = None


class SchemaResponse(BaseModel):
    id: str
    type_key: str
    display_name: str
    fields: list[SchemaFieldSpec]
    created_at: datetime
    updated_at: datetime


_PRIORITY = r"^P[0-5]$"


class CreateNodeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=64)
    description: str | None = None
    owner: str | None = None
    department: str | None = None
    system: str | None = None
    priority: str | None = Field(default=None, pattern=_PRIORITY)
    tags: list[str] = []
    ext_props: dict[str, Any] = {}
    is_critical: bool = False


class UpdateNodeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    owner: str | None = None
    department: str | None = None
    system: str | None = None
    priority: str | None = Field(default=None, pattern=_PRIORITY)
    tags: list[str] | None = None
    ext_props: dict[str, Any] | None = None
    is_critical: bool | None = None


class NodeResponse(BaseModel):
    id: str
    project_id: int
    name: str
    type: str
    # Neo4j 不存储 null 属性，缺省键需有默认值才不会被当成必填
    description: str | None = None
    owner: str | None = None
    department: str | None = None
    system: str | None = None
    priority: str | None = None
    tags: list[str]
    ext_props: dict[str, Any]
    is_critical: bool
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int
    parent_id: str | None = None
    children_count: int


class SetParentRequest(BaseModel):
    parent_id: str = Field(min_length=1)
