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
    upstream_count: int = 0
    downstream_count: int = 0


class SetParentRequest(BaseModel):
    parent_id: str = Field(min_length=1)


EdgeType = Literal["trigger", "data_flow", "api_call", "custom"]
Strength = Literal["strong", "weak"]


class CreateEdgeRequest(BaseModel):
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    edge_type: EdgeType = "data_flow"
    description: str | None = None
    is_required: bool = True
    strength: Strength = "strong"
    ext_props: dict[str, Any] = {}


class UpdateEdgeRequest(BaseModel):
    edge_type: EdgeType | None = None
    description: str | None = None
    is_required: bool | None = None
    strength: Strength | None = None
    ext_props: dict[str, Any] | None = None


class EdgeResponse(BaseModel):
    id: str
    project_id: int
    source_id: str
    target_id: str
    edge_type: str
    description: str | None = None
    is_required: bool
    strength: str
    ext_props: dict[str, Any]
    created_at: datetime
    created_by: int


class EdgeWarnings(BaseModel):
    creates_cycle: bool = False


class CreateEdgeResponse(BaseModel):
    edge: EdgeResponse
    warnings: EdgeWarnings


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    priority: str | None = None
    is_critical: bool
    parent_id: str | None = None


class GraphStats(BaseModel):
    node_count: int
    edge_count: int
    has_cycle: bool


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[EdgeResponse]
    stats: GraphStats


class NodePage(BaseModel):
    items: list[NodeResponse]
    total: int
    limit: int
    offset: int


class CycleResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[EdgeResponse]


class ImpactResponse(BaseModel):
    upstream: list[NodeResponse]
    downstream: list[NodeResponse]
    warnings: dict


class PathItem(BaseModel):
    nodes: list[GraphNode]
    edges: list[EdgeResponse]
    depth: int
    score: int | None = None


class CriticalPathResponse(BaseModel):
    mode: str
    paths: list[PathItem]
