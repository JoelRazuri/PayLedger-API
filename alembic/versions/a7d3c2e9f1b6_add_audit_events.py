"""add immutable audit events

Revision ID: a7d3c2e9f1b6
Revises: f4c4e8a1d5f3
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7d3c2e9f1b6"
down_revision: str | Sequence[str] | None = "f4c4e8a1d5f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

audit_action = postgresql.ENUM(
    "payment.create",
    "payment.process",
    "payment.cancel",
    "external_transaction.ingest",
    "reconciliation.execute",
    name="audit_action",
    create_type=False,
)
audit_resource_type = postgresql.ENUM(
    "payment",
    "external_transaction",
    "reconciliation",
    name="audit_resource_type",
    create_type=False,
)
audit_outcome = postgresql.ENUM(
    "success", "failure", name="audit_outcome", create_type=False
)

def upgrade() -> None:
    for enum in (audit_action, audit_resource_type, audit_outcome):
        enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("resource_type", audit_resource_type, nullable=False),
        sa.Column("resource_id", sa.Integer()),
        sa.Column("outcome", audit_outcome, nullable=False),
        sa.Column("reason_code", sa.String(length=100)),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "(outcome = 'failure' AND reason_code IS NOT NULL) OR "
            "(outcome = 'success' AND reason_code IS NULL)",
            name="ck_audit_events_failure_reason",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(details) = 'object' AND details - "
            "ARRAY['replayed', 'status', 'result'] = '{}'::jsonb",
            name="ck_audit_events_details_allowlist",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_actor_occurred_id",
        "audit_events",
        ["actor_user_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_audit_events_actor_action", "audit_events", ["actor_user_id", "action"]
    )
    op.execute(
        "CREATE FUNCTION reject_audit_event_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'audit events are immutable' USING ERRCODE = "
        "'55000'; END; $$ LANGUAGE plpgsql;"
    )
    op.execute(
        "CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON "
        "audit_events FOR EACH ROW EXECUTE FUNCTION "
        "reject_audit_event_mutation();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION reject_audit_event_mutation()")
    op.drop_index("ix_audit_events_actor_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_occurred_id", table_name="audit_events")
    op.drop_table("audit_events")
    for enum in (audit_outcome, audit_resource_type, audit_action):
        enum.drop(op.get_bind(), checkfirst=True)
