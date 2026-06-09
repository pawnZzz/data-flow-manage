from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import GraphRepoDep, ProjectContext, require_role
from app.models import MemberRole
from app.schemas.sql_import import (
    CommitRequest,
    CommitResponse,
    PreviewRequest,
    PreviewResponse,
)
from app.services import sql_import_service

router = APIRouter(prefix="/api/v1/projects/{pid}/sql-import", tags=["sql-import"])


@router.post("/preview", response_model=PreviewResponse)
def preview(
    payload: PreviewRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> PreviewResponse:
    return sql_import_service.preview(repo, ctx.project.id, payload.sql, payload.dialect)


@router.post("/commit", response_model=CommitResponse)
def commit(
    payload: CommitRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.editor))],
    repo: GraphRepoDep,
) -> CommitResponse:
    return sql_import_service.commit(repo, ctx.project.id, ctx.user.id, payload.model_dump())
