from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class SetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class UserDTO(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    ok: bool = True
    user: UserDTO
    session_token: str


class MeResponse(BaseModel):
    user: UserDTO
    permissions: list


class OkResponse(BaseModel):
    ok: bool = True
    message: str = None