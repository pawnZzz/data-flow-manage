from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.deps import CurrentUser, DbSession, ProjectContext, require_role
from app.models import MemberRole, Project
from app.schemas.project import (
    CreateProjectRequest,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.services import project_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _to_response(project: Project, role: MemberRole) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        my_role=role.value,
    )


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    user: CurrentUser,
    db: DbSession,
    include_archived: Annotated[bool, Query()] = False,
) -> list[ProjectResponse]:
    rows = project_service.list_my_projects(db, user, include_archived=include_archived)
    return [_to_response(p, role) for p, role in rows]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: CreateProjectRequest, user: CurrentUser, db: DbSession
) -> ProjectResponse:
    project = project_service.create_project(db, user, payload.name, payload.description)
    # service inserts the creator as the owner membership
    return _to_response(project, MemberRole.owner)


@router.get("/{pid}", response_model=ProjectResponse)
def get_project(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
) -> ProjectResponse:
    return _to_response(ctx.project, ctx.membership.role)


@router.patch("/{pid}", response_model=ProjectResponse)
def update_project(
    payload: UpdateProjectRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin, require_active=True))],
    db: DbSession,
) -> ProjectResponse:
    project = project_service.update_project(
        db, ctx.user, ctx.project, name=payload.name, description=payload.description
    )
    return _to_response(project, ctx.membership.role)


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def archive_project(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.owner))],
    db: DbSession,
) -> None:
    project_service.archive_project(db, ctx.user, ctx.project)
    return None
