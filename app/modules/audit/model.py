from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TypeAlias

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType

AuditEnum: TypeAlias = type[AuditAction] | type[AuditOutcome] | type[AuditResourceType]


def _values(enum_class: AuditEnum) -> Sequence[str]:
    return [member.value for member in enum_class]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[AuditAction] = mapped_column(
        ENUM(
            AuditAction, name="audit_action", values_callable=_values, create_type=False
        ),
        nullable=False,
    )
    resource_type: Mapped[AuditResourceType] = mapped_column(
        ENUM(
            AuditResourceType,
            name="audit_resource_type",
            values_callable=_values,
            create_type=False,
        ),
        nullable=False,
    )
    resource_id: Mapped[int | None] = mapped_column()
    outcome: Mapped[AuditOutcome] = mapped_column(
        ENUM(
            AuditOutcome,
            name="audit_outcome",
            values_callable=_values,
            create_type=False,
        ),
        nullable=False,
    )
    reason_code: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "(outcome = 'failure' AND reason_code IS NOT NULL) OR "
            "(outcome = 'success' AND reason_code IS NULL)",
            name="ck_audit_events_failure_reason",
        ),
        CheckConstraint(
            "jsonb_typeof(details) = 'object' AND details - "
            "ARRAY['replayed', 'status', 'result'] = '{}'::jsonb",
            name="ck_audit_events_details_allowlist",
        ),
        Index(
            "ix_audit_events_actor_occurred_id", "actor_user_id", "occurred_at", "id"
        ),
        Index("ix_audit_events_actor_action", "actor_user_id", "action"),
    )
