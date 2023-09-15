from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr, constr


class UserBaseSchema(BaseModel):
    name: str
    email: str
    created_at: datetime = None
    updated_at: datetime = None

    class Config:
        orm_mode = True


class CreateUserSchema(UserBaseSchema):
    password: constr(min_length=8)
    passwordConfirm: str


class LoginUserSchema(BaseModel):
    email: EmailStr
    password: constr(min_length=8)


class UserResponseSchema(UserBaseSchema):
    id: str
    pass


class UserResponse(BaseModel):
    status: str
    user: UserResponseSchema


class ChatRoom(BaseModel):
    id: str
    name: str
    members: List[str] = []


class ChatMessage(BaseModel):
    sender: str
    text: str
    chat_room_id: str