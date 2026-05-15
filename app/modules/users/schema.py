from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }