from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph_io import ExportResponse
from app.services import graph_io_service

router = APIRouter(prefix="/api/v1/projects/{pid}", tags=["graph-io"])


@router.get("/export", response_model=ExportResponse)
def export_graph(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> ExportResponse:
    return graph_io_service.export_graph(repo, ctx.project.id)
