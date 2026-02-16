"""Initial schema for leads, queue jobs, webhook dedupe, and audit events.

Revision ID: 20260216_0001
Revises:
Create Date: 2026-02-16 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260216_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("budget_range", sa.String(length=100), nullable=True),
        sa.Column("bhk_preference", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("interest_level", sa.String(length=20), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("call_id", sa.String(length=80), nullable=True),
        sa.Column("do_not_contact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dnc_reason", sa.String(length=250), nullable=True),
        sa.Column("dnc_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("call_id"),
    )
    op.create_index("ix_lead_phone", "lead", ["phone"], unique=False)
    op.create_index("ix_lead_status", "lead", ["status"], unique=False)
    op.create_index("ix_lead_call_id", "lead", ["call_id"], unique=False)
    op.create_index("ix_lead_do_not_contact", "lead", ["do_not_contact"], unique=False)
    op.create_index("ix_lead_created_at", "lead", ["created_at"], unique=False)

    op.create_table(
        "campaignjob",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=220), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["lead.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaignjob_lead_id", "campaignjob", ["lead_id"], unique=False)
    op.create_index("ix_campaignjob_status", "campaignjob", ["status"], unique=False)
    op.create_index("ix_campaignjob_scheduled_at", "campaignjob", ["scheduled_at"], unique=False)
    op.create_index("ix_campaignjob_lease_until", "campaignjob", ["lease_until"], unique=False)
    op.create_index("ix_campaignjob_created_at", "campaignjob", ["created_at"], unique=False)

    op.create_table(
        "processedwebhookevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("process_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_key", name="uq_provider_event_key"),
    )
    op.create_index("ix_processedwebhookevent_provider", "processedwebhookevent", ["provider"], unique=False)
    op.create_index("ix_processedwebhookevent_event_key", "processedwebhookevent", ["event_key"], unique=False)
    op.create_index("ix_processedwebhookevent_first_seen_at", "processedwebhookevent", ["first_seen_at"], unique=False)
    op.create_index("ix_processedwebhookevent_last_seen_at", "processedwebhookevent", ["last_seen_at"], unique=False)

    op.create_table(
        "auditevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("call_id", sa.String(length=80), nullable=True),
        sa.Column("details", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auditevent_event_type", "auditevent", ["event_type"], unique=False)
    op.create_index("ix_auditevent_source", "auditevent", ["source"], unique=False)
    op.create_index("ix_auditevent_lead_id", "auditevent", ["lead_id"], unique=False)
    op.create_index("ix_auditevent_call_id", "auditevent", ["call_id"], unique=False)
    op.create_index("ix_auditevent_created_at", "auditevent", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auditevent_created_at", table_name="auditevent")
    op.drop_index("ix_auditevent_call_id", table_name="auditevent")
    op.drop_index("ix_auditevent_lead_id", table_name="auditevent")
    op.drop_index("ix_auditevent_source", table_name="auditevent")
    op.drop_index("ix_auditevent_event_type", table_name="auditevent")
    op.drop_table("auditevent")

    op.drop_index("ix_processedwebhookevent_last_seen_at", table_name="processedwebhookevent")
    op.drop_index("ix_processedwebhookevent_first_seen_at", table_name="processedwebhookevent")
    op.drop_index("ix_processedwebhookevent_event_key", table_name="processedwebhookevent")
    op.drop_index("ix_processedwebhookevent_provider", table_name="processedwebhookevent")
    op.drop_table("processedwebhookevent")

    op.drop_index("ix_campaignjob_created_at", table_name="campaignjob")
    op.drop_index("ix_campaignjob_lease_until", table_name="campaignjob")
    op.drop_index("ix_campaignjob_scheduled_at", table_name="campaignjob")
    op.drop_index("ix_campaignjob_status", table_name="campaignjob")
    op.drop_index("ix_campaignjob_lead_id", table_name="campaignjob")
    op.drop_table("campaignjob")

    op.drop_index("ix_lead_created_at", table_name="lead")
    op.drop_index("ix_lead_do_not_contact", table_name="lead")
    op.drop_index("ix_lead_call_id", table_name="lead")
    op.drop_index("ix_lead_status", table_name="lead")
    op.drop_index("ix_lead_phone", table_name="lead")
    op.drop_table("lead")
