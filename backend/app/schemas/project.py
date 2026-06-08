from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    my_role: str


class AddMemberRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    role: str = Field(pattern="^(owner|admin|editor|viewer)$")

    @model_validator(mode="after")
    def _need_identifier(self) -> "AddMemberRequest":
        if not self.username and not self.email:
            raise ValueError("username 或 email 至少提供一个")
        return self


class ChangeRoleRequest(BaseModel):
    role: str = Field(pattern="^(owner|admin|editor|viewer)$")


class MemberResponse(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    role: str
    joined_at: datetime
