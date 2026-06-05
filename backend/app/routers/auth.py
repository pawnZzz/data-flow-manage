from fastapi import APIRouter, Request, status

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.exceptions import PermissionDenied
from app.rate_limit import limiter
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
)
from app.security import create_access_token
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> UserResponse:
    if not get_settings().allow_registration:
        raise PermissionDenied("当前不允许注册")
    user = auth_service.register(
        db, payload.username, payload.email, payload.password, payload.display_name
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = auth_service.authenticate(db, payload.username, payload.password)
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: CurrentUser) -> None:
    # 无状态 JWT：前端丢弃 token 即可。此处仅作为受保护端点占位（后续接审计）。
    return None


@router.get("/me", response_model=UserResponse)
def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(payload: UpdateMeRequest, current_user: CurrentUser, db: DbSession) -> UserResponse:
    user = auth_service.update_profile(db, current_user, payload.display_name)
    return UserResponse.model_validate(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest, current_user: CurrentUser, db: DbSession
) -> None:
    auth_service.change_password(db, current_user, payload.old_password, payload.new_password)
    return None
