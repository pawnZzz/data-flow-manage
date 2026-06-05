from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.mysql import get_session
from app.exceptions import AuthError
from app.models import User
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
