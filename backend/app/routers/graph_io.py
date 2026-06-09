from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.graph_io import ExportResponse, ImportRequest, ImportResponse
from app.services import graph_io_service

router = APIRouter(prefix="/api/v1/projects/{pid}", tags=["graph-io"])


@router.get("/export", response_model=ExportResponse)
def export_graph(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    repo: GraphRepoDep,
) -> ExportResponse:
    return graph_io_service.export_graph(repo, ctx.project.id)


@router.post("/import", response_model=ImportResponse)
def import_graph(
    payload: ImportRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor, require_active=True))],
    repo: GraphRepoDep,
) -> ImportResponse:
    return graph_io_service.import_graph(repo, ctx.project.id, ctx.user.id, payload.model_dump())
