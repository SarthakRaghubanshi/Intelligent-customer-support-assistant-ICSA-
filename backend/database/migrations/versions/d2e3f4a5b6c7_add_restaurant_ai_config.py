"""add_restaurant_ai_config

Adds a JSON ai_config column to restaurants for per-tenant AI assistant settings
(enabled flag, greeting message, low-confidence escalation threshold).

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-11 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("restaurants") as batch_op:
        batch_op.add_column(sa.Column("ai_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("restaurants") as batch_op:
        batch_op.drop_column("ai_config")
