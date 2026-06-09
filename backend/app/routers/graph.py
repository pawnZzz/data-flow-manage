from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph import CriticalPathRequest, CriticalPathResponse
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
