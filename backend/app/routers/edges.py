from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import (
    CreateEdgeRequest,
    CreateEdgeResponse,
    EdgeResponse,
    UpdateEdgeRequest,
)
from app.services import edge_service

router = APIRouter(prefix="/api/v1/projects/{pid}/edges", tags=["edges"])


@router.get("", response_model=list[EdgeResponse])
def list_edges(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    source_id: Annotated[str | None, Query()] = None,
    target_id: Annotated[str | None, Query()] = None,
    edge_type: Annotated[str | None, Query()] = None,
) -> list[EdgeResponse]:
    filters = {"source_id": source_id, "target_id": target_id, "edge_type": edge_type}
    return edge_service.list_edges(repo, ctx.project.id, filters)


@router.post("", response_model=CreateEdgeResponse, status_code=status.HTTP_201_CREATED)
def create_edge(
    payload: CreateEdgeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> CreateEdgeResponse:
    return edge_service.create_edge(repo, ctx.project.id, ctx.user.id, payload.model_dump())


@router.get("/{eid}", response_model=EdgeResponse)
def get_edge(
    eid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> EdgeResponse:
    return edge_service.get_edge(repo, ctx.project.id, eid)


@router.patch("/{eid}", response_model=EdgeResponse)
def update_edge(
    eid: str,
    payload: UpdateEdgeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> EdgeResponse:
    return edge_service.update_edge(
        repo, ctx.project.id, eid, ctx.user.id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{eid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edge(
    eid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> None:
    edge_service.delete_edge(repo, ctx.project.id, eid, ctx.user.id)
    return None
