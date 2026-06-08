from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.mysql import get_session
from app.db.neo4j import get_driver
from app.repositories.graph_repo import GraphRepo
from app.exceptions import AuthError, NotFoundError, PermissionDenied
from app.models import MemberRole, Project, ProjectMember, User
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_session)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None:
        raise AuthError("缺少认证凭证")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AuthError("无效或过期的 token")
    user = db.scalar(select(User).where(User.id == int(user_id)))
    if user is None:
        raise AuthError("用户不存在")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass(frozen=True)
class ProjectContext:
    project: Project
    membership: ProjectMember
    user: User


def require_role(min_role: MemberRole) -> Callable[..., "ProjectContext"]:
    def dep(
        pid: Annotated[int, Path()],
        user: CurrentUser,
        db: DbSession,
    ) -> ProjectContext:
        project = db.get(Project, pid)
        if project is None:
            raise NotFoundError("项目不存在")
        membership = db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == pid,
                ProjectMember.user_id == user.id,
            )
        )
        if membership is None:
            raise PermissionDenied("非项目成员")
        if membership.role.level < min_role.level:
            raise PermissionDenied("权限不足")
        return ProjectContext(project=project, membership=membership, user=user)

    return dep


def get_graph_repo() -> GraphRepo:
    return GraphRepo(get_driver())


GraphRepoDep = Annotated[GraphRepo, Depends(get_graph_repo)]
