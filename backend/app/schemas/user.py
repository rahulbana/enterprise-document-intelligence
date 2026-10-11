# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Request/response shapes for user resources.

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    department_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class UserDepartmentsUpdate(BaseModel):
    department_ids: list[int]


class UserBulkStatusUpdate(BaseModel):
    user_ids: list[int] = Field(min_length=1)
    is_active: bool
