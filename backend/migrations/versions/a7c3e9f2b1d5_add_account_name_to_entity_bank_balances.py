"""add account_name to entity_bank_balances

Revision ID: a7c3e9f2b1d5
Revises: f1a2b3c4d5e6
Create Date: 2026-07-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7c3e9f2b1d5'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('entity_bank_balances', sa.Column('account_name', sa.String(255), nullable=True))
    # Backfill existing rows: account_name = entity_name + ' ' + currency
    op.execute("""
        UPDATE entity_bank_balances eb
        SET account_name = e.name || ' ' || eb.currency
        FROM entities e
        WHERE eb.entity_id = e.id AND eb.account_name IS NULL
    """)


def downgrade() -> None:
    op.drop_column('entity_bank_balances', 'account_name')
