"""create_escalation_events

Revision ID: a1b2c3d4e5f6
Revises: 8d0040269b1c
Create Date: 2026-06-20 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8d0040269b1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('escalation_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('conversation_id', sa.String(length=36), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('assigned_to', sa.String(length=36), nullable=True),
    sa.Column('resolution_summary', sa.Text(), nullable=True),
    sa.Column('resolved_by', sa.String(length=36), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('claimed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_escalation_events_conversation_id'), 'escalation_events', ['conversation_id'], unique=True)
    op.create_index(op.f('ix_escalation_events_status'), 'escalation_events', ['status'], unique=False)
    op.create_index(op.f('ix_escalation_events_priority'), 'escalation_events', ['priority'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_escalation_events_priority'), table_name='escalation_events')
    op.drop_index(op.f('ix_escalation_events_status'), table_name='escalation_events')
    op.drop_index(op.f('ix_escalation_events_conversation_id'), table_name='escalation_events')
    op.drop_table('escalation_events')
