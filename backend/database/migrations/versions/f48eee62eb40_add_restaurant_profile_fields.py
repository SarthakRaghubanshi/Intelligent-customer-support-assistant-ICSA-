"""add_restaurant_profile_fields

Revision ID: f48eee62eb40
Revises: 18878dd1dc6c
Create Date: 2026-06-17 01:45:02.527294

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f48eee62eb40'
down_revision: Union[str, Sequence[str], None] = '18878dd1dc6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('restaurants', sa.Column('contact_email', sa.String(length=255), nullable=True))
    op.add_column('restaurants', sa.Column('business_hours', sa.JSON(), nullable=True))
    op.add_column('restaurants', sa.Column('delivery_available', sa.Boolean(), server_default=sa.text('1'), nullable=False))
    op.add_column('restaurants', sa.Column('delivery_notes', sa.String(length=500), nullable=True))
    op.add_column('restaurants', sa.Column('status_message', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('restaurants') as batch_op:
        batch_op.drop_column('status_message')
        batch_op.drop_column('delivery_notes')
        batch_op.drop_column('delivery_available')
        batch_op.drop_column('business_hours')
        batch_op.drop_column('contact_email')
