from pydantic import BaseModel
from datetime import datetime

class UserBase(BaseModel):
    email: str
    first_name: str
    last_name: str
    role: str = "user"  # "admin" or "user"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
