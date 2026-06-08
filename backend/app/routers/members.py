from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.deps import DbSession, ProjectContext, require_role
from app.exceptions import NotFoundError
from app.models import MemberRole, ProjectMember, User
from app.schemas.project import AddMemberRequest, ChangeRoleRequest, MemberResponse
from app.services import member_service

router = APIRouter(prefix="/api/v1/projects/{pid}/members", tags=["members"])


def _to_member_response(db: Session, membership: ProjectMember) -> MemberResponse:
    user = db.get(User, membership.user_id)
    if user is None:
        raise NotFoundError(f"用户 {membership.user_id} 不存在")
    return MemberResponse(
        user_id=membership.user_id,
        username=user.username,
        display_name=user.display_name,
        role=membership.role.value,
        joined_at=membership.joined_at,
    )


@router.get("", response_model=list[MemberResponse])
def list_members(
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.viewer))],
    db: DbSession,
) -> list[MemberResponse]:
    members = member_service.list_members(db, ctx.project.id)
    return [_to_member_response(db, m) for m in members]


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: AddMemberRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    db: DbSession,
) -> MemberResponse:
    membership = member_service.add_member(
        db,
        actor_role=ctx.membership.role,
        actor=ctx.user,
        project=ctx.project,
        username=payload.username,
        email=payload.email,
        role=payload.role,
    )
    return _to_member_response(db, membership)


@router.patch("/{uid}", response_model=MemberResponse)
def change_role(
    uid: int,
    payload: ChangeRoleRequest,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    db: DbSession,
) -> MemberResponse:
    membership = member_service.change_role(
        db,
        actor_role=ctx.membership.role,
        actor=ctx.user,
        project=ctx.project,
        target_user_id=uid,
        new_role=payload.role,
    )
    return _to_member_response(db, membership)


@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    uid: int,
    ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))],
    db: DbSession,
) -> None:
    member_service.remove_member(
        db,
        actor_role=ctx.membership.role,
        actor=ctx.user,
        project=ctx.project,
        target_user_id=uid,
    )
    return None
