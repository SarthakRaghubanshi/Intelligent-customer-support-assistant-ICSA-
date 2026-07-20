"""add cuisine, delivery_zones, order contact_phone, audit_logs

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-11 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("restaurants") as batch_op:
        batch_op.add_column(sa.Column("cuisine", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("delivery_zones", sa.JSON(), nullable=True))

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("contact_phone", sa.String(length=50), nullable=True))

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("restaurant_id", sa.String(length=36), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_restaurant_id"), "audit_logs", ["restaurant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_restaurant_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("contact_phone")
    with op.batch_alter_table("restaurants") as batch_op:
        batch_op.drop_column("delivery_zones")
        batch_op.drop_column("cuisine")
