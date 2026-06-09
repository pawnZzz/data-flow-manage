from pydantic import BaseModel, Field


class PreviewRequest(BaseModel):
    sql: str = Field(min_length=1)
    dialect: str = "mysql"


class ParsedTable(BaseModel):
    name: str
    exists: bool
    node_id: str | None = None


class ParsedDependency(BaseModel):
    source: str
    target: str
    edge_type: str = "data_flow"


class PreviewResponse(BaseModel):
    tables: list[ParsedTable]
    dependencies: list[ParsedDependency]
    unrecognized: list[str]


class CommitTable(BaseModel):
    name: str = Field(min_length=1)
    type: str = "table"


class CommitDependency(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    edge_type: str = "data_flow"


class CommitRequest(BaseModel):
    tables: list[CommitTable] = []
    dependencies: list[CommitDependency] = []


class CommitResponse(BaseModel):
    created_nodes: int
    reused_nodes: int
    created_edges: int
    skipped_edges: int
