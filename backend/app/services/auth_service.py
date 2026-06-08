from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import AuthError, ConflictError
from app.models import User, UserStatus
from app.security import hash_password, verify_password


def register(
    db: Session, username: str, email: str, password: str, display_name: str | None
) -> User:
    exists = db.scalar(
        select(User).where((User.username == username) | (User.email == email))
    )
    if exists:
        field = "username" if exists.username == username else "email"
        raise ConflictError("用户名或邮箱已存在", {"field": field})

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("用户名或密码错误")
    if user.status == UserStatus.disabled:
        raise AuthError("账号已禁用")
    return user


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise AuthError("原密码错误")
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()


def update_profile(db: Session, user: User, display_name: str | None) -> User:
    if display_name is not None:
        user.display_name = display_name
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
