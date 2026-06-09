from typing import Any

from pydantic import BaseModel, Field

from app.schemas.graph import SchemaFieldSpec


class ExportSchema(BaseModel):
    type_key: str
    display_name: str
    fields: list[SchemaFieldSpec] = []


class ExportNode(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    description: str | None = None
    owner: str | None = None
    department: str | None = None
    system: str | None = None
    priority: str | None = None
    tags: list[str] = []
    ext_props: dict[str, Any] = {}
    is_critical: bool = False
    parent: str | None = None


class ExportEdge(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    edge_type: str = "data_flow"
    description: str | None = None
    is_required: bool = True
    strength: str = "strong"
    ext_props: dict[str, Any] = {}


class ExportResponse(BaseModel):
    schemas: list[ExportSchema]
    nodes: list[ExportNode]
    edges: list[ExportEdge]


class ImportRequest(BaseModel):
    schemas: list[ExportSchema] = []
    nodes: list[ExportNode] = []
    edges: list[ExportEdge] = []


class ImportResponse(BaseModel):
    created_schemas: int
    reused_schemas: int
    created_nodes: int
    reused_nodes: int
    set_parents: int
    created_edges: int
    skipped_edges: int
