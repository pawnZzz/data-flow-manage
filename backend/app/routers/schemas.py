from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import CreateSchemaRequest, SchemaResponse, UpdateSchemaRequest
from app.services import schema_service

router = APIRouter(prefix="/api/v1/projects/{pid}/schemas", tags=["schemas"])


@router.get("", response_model=list[SchemaResponse])
def list_schemas(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> list[SchemaResponse]:
    return schema_service.list_schemas(repo, ctx.project.id)


@router.post("", response_model=SchemaResponse, status_code=status.HTTP_201_CREATED)
def create_schema(
    payload: CreateSchemaRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor, require_active=True))],
    repo: GraphRepoDep,
) -> SchemaResponse:
    fields = [f.model_dump() for f in payload.fields]
    return schema_service.create_schema(
        repo, ctx.project.id, payload.type_key, payload.display_name, fields
    )


@router.get("/{type_key}", response_model=SchemaResponse)
def get_schema(
    type_key: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> SchemaResponse:
    return schema_service.get_schema(repo, ctx.project.id, type_key)


@router.put("/{type_key}", response_model=SchemaResponse)
def update_schema(
    type_key: str,
    payload: UpdateSchemaRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor, require_active=True))],
    repo: GraphRepoDep,
) -> SchemaResponse:
    fields = [f.model_dump() for f in payload.fields] if payload.fields is not None else None
    return schema_service.update_schema(
        repo, ctx.project.id, type_key, payload.display_name, fields
    )


@router.delete("/{type_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schema(
    type_key: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin, require_active=True))],
    repo: GraphRepoDep,
) -> None:
    schema_service.delete_schema(repo, ctx.project.id, type_key)
    return None
