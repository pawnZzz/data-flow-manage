import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.models import MemberRole, Project, ProjectMember, User

logger = logging.getLogger("app.audit")


def list_members(db: Session, project_id: int) -> list[ProjectMember]:
    return list(
        db.scalars(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        ).all()
    )


def _get_membership(db: Session, project_id: int, user_id: int) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )


def _count_owners(db: Session, project_id: int) -> int:
    return len(
        [m for m in list_members(db, project_id) if m.role == MemberRole.owner]
    )


def add_member(
    db: Session,
    *,
    actor_role: MemberRole,
    actor: User,
    project: Project,
    username: str | None,
    email: str | None,
    role: str,
) -> ProjectMember:
    new_role = MemberRole(role)
    if new_role == MemberRole.owner and actor_role != MemberRole.owner:
        raise PermissionDenied("只有 owner 能添加 owner 角色")

    stmt = select(User)
    if username:
        stmt = stmt.where(User.username == username)
    else:
        stmt = stmt.where(User.email == email)
    target = db.scalar(stmt)
    if target is None:
        raise NotFoundError("用户不存在")

    if _get_membership(db, project.id, target.id) is not None:
        raise ConflictError("该用户已是项目成员", {"user_id": target.id})

    membership = ProjectMember(project_id=project.id, user_id=target.id, role=new_role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    logger.info(
        "member.add actor=%s project=%s target_user=%s role=%s",
        actor.id, project.id, target.id, new_role.value,
    )
    return membership


def change_role(
    db: Session,
    *,
    actor_role: MemberRole,
    actor: User,
    project: Project,
    target_user_id: int,
    new_role: str,
) -> ProjectMember:
    role = MemberRole(new_role)
    membership = _get_membership(db, project.id, target_user_id)
    if membership is None:
        raise NotFoundError("成员不存在")

    involves_owner = membership.role == MemberRole.owner or role == MemberRole.owner
    if involves_owner and actor_role != MemberRole.owner:
        raise PermissionDenied("只有 owner 能变更 owner 角色")

    if (
        membership.role == MemberRole.owner
        and role != MemberRole.owner
        and _count_owners(db, project.id) <= 1
    ):
        raise ConflictError("不能降级项目唯一的 owner")

    old = membership.role.value
    membership.role = role
    db.add(membership)
    db.commit()
    logger.info(
        "member.update_role actor=%s project=%s target_user=%s role=%s->%s",
        actor.id, project.id, target_user_id, old, role.value,
    )
    return membership


def remove_member(
    db: Session,
    *,
    actor_role: MemberRole,
    actor: User,
    project: Project,
    target_user_id: int,
) -> None:
    membership = _get_membership(db, project.id, target_user_id)
    if membership is None:
        raise NotFoundError("成员不存在")
    if membership.role == MemberRole.owner:
        raise PermissionDenied("不能移除 owner")
    db.delete(membership)
    db.commit()
    logger.info(
        "member.remove actor=%s project=%s target_user=%s",
        actor.id, project.id, target_user_id,
    )
