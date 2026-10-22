from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType


class AuditEventListQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    action: AuditAction | None = None
    resource_type: AuditResourceType | None = None
    resource_id: int | None = Field(default=None, ge=1)
    outcome: AuditOutcome | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None

    @field_validator("occurred_from", "occurred_to")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_combinations(self) -> "AuditEventListQuery":
        expected_resource = (
            AuditResourceType.PAYMENT
            if self.action.value.startswith("payment.")
            else AuditResourceType(self.action.value.split(".")[0])
        ) if self.action is not None else None
        if self.resource_id is not None and self.resource_type is None:
            raise ValueError("resource_id requires resource_type")
        if self.action is not None and self.resource_type not in (
            None,
            expected_resource,
        ):
            raise ValueError("unsupported action/resource combination")
        if self.occurred_from is not None and self.occurred_to is not None:
            if self.occurred_from > self.occurred_to:
                raise ValueError("occurred_from must not exceed occurred_to")
        return self


class AuditEventResponse(BaseModel):
    id: int
    action: AuditAction
    resource_type: AuditResourceType
    resource_id: int | None
    outcome: AuditOutcome
    reason_code: str | None
    details: dict[str, object]
    occurred_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("occurred_at")
    @classmethod
    def normalize_response_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
