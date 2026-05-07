from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(pattern="^(partner|finance)$")


class UpdateUserRequest(BaseModel):
    full_name: str = Field(default=None, min_length=1, max_length=255)
    role: str = Field(default=None, pattern="^(partner|finance)$")


class UserListItem(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime = None
    created_at: datetime

    class Config:
        from_attributes = True