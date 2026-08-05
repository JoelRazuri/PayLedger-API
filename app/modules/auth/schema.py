from pydantic import BaseModel, Field

from app.modules.users.schema import UserInput


class RegisterRequest(UserInput):
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
