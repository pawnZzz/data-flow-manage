from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import (
    CriticalPathRequest,
    CriticalPathResponse,
    CycleResponse,
    GraphResponse,
)
from app.services import graph_service

router = APIRouter(prefix="/api/v1/projects/{pid}", tags=["graph"])


@router.post("/critical-paths", response_model=CriticalPathResponse)
def critical_paths(
    payload: CriticalPathRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> CriticalPathResponse:
    return graph_service.critical_paths(
        repo, ctx.project.id, payload.mode, payload.node_ids
    )


@router.get("/graph", response_model=GraphResponse)
def get_subgraph(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
    center: Annotated[str | None, Query()] = None,
    depth: Annotated[int, Query(ge=0, le=50)] = 2,
    direction: Annotated[Literal["upstream", "downstream", "both"], Query()] = "both",
) -> GraphResponse:
    return graph_service.subgraph(repo, ctx.project.id, center, depth, direction)


@router.get("/cycles", response_model=list[CycleResponse])
def get_cycles(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> list[CycleResponse]:
    return graph_service.cycles(repo, ctx.project.id)
