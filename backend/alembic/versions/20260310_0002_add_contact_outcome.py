"""Add lead contact outcome column.

Revision ID: 20260310_0002
Revises: 20260216_0001
Create Date: 2026-03-10 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260310_0002"
down_revision: Union[str, None] = "20260216_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lead", sa.Column("contact_outcome", sa.String(length=40), nullable=True))
    op.create_index("ix_lead_contact_outcome", "lead", ["contact_outcome"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lead_contact_outcome", table_name="lead")
    op.drop_column("lead", "contact_outcome")
