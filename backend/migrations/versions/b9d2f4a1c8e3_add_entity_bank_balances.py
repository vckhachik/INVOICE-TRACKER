"""add entity bank balances table

Revision ID: b9d2f4a1c8e3
Revises: a8f3e12c4b76
Create Date: 2026-06-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9d2f4a1c8e3'
down_revision: Union[str, Sequence[str], None] = 'a8f3e12c4b76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'entity_bank_balances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('balance_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='GBP'),
        sa.Column('balance_date', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('entry_type', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('updated_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_entity_bank_balances_entity_id', 'entity_bank_balances', ['entity_id'])


def downgrade() -> None:
    op.drop_index('ix_entity_bank_balances_entity_id', 'entity_bank_balances')
    op.drop_table('entity_bank_balances')
