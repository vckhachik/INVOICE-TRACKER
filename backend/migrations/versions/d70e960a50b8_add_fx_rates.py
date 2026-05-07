"""add_fx_rates

Revision ID: d70e960a50b8
Revises: 2ab9cfcf7e17
Create Date: 2026-04-17 14:38:17.250613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd70e960a50b8'
down_revision: Union[str, Sequence[str], None] = '2ab9cfcf7e17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('fx_rates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('from_currency', sa.String(length=10), nullable=False),
    sa.Column('to_currency', sa.String(length=10), nullable=False, server_default='GBP'),
    sa.Column('rate', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=True, server_default='manual'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('fx_rates')
