from pydantic import BaseModel


class LoginRequest(BaseModel):
    # 登录只是查 DB 匹配字符串，不需要严格 email 格式（admin 创建时再校验）
    email: str
    password: str


class AdminUserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    app_scope: list[str]
    permissions: list[str]
    is_super_admin: bool


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: AdminUserOut


class HealthOut(BaseModel):
    status: str
