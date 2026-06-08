from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import CreateNodeRequest, NodeResponse, UpdateNodeRequest
from app.services import node_service

router = APIRouter(prefix="/api/v1/projects/{pid}/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeResponse])
def list_nodes(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    type: Annotated[str | None, Query()] = None,
    department: Annotated[str | None, Query()] = None,
    system: Annotated[str | None, Query()] = None,
    priority: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    parent_id: Annotated[str | None, Query()] = None,
    has_parent: Annotated[bool | None, Query()] = None,
) -> list[NodeResponse]:
    filters = {
        "type": type, "department": department, "system": system, "priority": priority,
        "tag": tag, "name": name, "parent_id": parent_id, "has_parent": has_parent,
    }
    return node_service.list_nodes(repo, ctx.project.id, filters)


@router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
def create_node(
    payload: CreateNodeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> NodeResponse:
    return node_service.create_node(repo, ctx.project.id, ctx.user.id, payload.model_dump())


@router.get("/{nid}", response_model=NodeResponse)
def get_node(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> NodeResponse:
    return node_service.get_node(repo, ctx.project.id, nid)


@router.patch("/{nid}", response_model=NodeResponse)
def update_node(
    nid: str,
    payload: UpdateNodeRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> NodeResponse:
    return node_service.update_node(
        repo, ctx.project.id, nid, ctx.user.id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{nid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(
    nid: str,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> None:
    node_service.delete_node(repo, ctx.project.id, nid)
    return None
