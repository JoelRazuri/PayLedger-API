from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class UserInput(BaseModel):
    email: EmailStr
    full_name: str

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_full_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized_name = value.strip()

        if len(normalized_name) < 2:
            raise ValueError("El nombre completo debe tener al menos 2 caracteres")

        if len(normalized_name) > 255:
            raise ValueError("El nombre completo no puede superar los 255 caracteres")

        return normalized_name


class UserCreate(UserInput):
    pass


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }
