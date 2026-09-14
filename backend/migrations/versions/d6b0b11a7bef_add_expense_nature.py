"""add expense_nature to invoices and recurring_invoices

Revision ID: d6b0b11a7bef
Revises: a7c3e9f2b1d5
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6b0b11a7bef'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9f2b1d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'invoices',
        sa.Column('expense_nature', sa.String(length=20), nullable=False, server_default='invoice'),
    )
    op.create_check_constraint(
        'ck_invoices_expense_nature',
        'invoices',
        "expense_nature IN ('invoice', 'accrual')",
    )

    op.add_column(
        'recurring_invoices',
        sa.Column('expense_nature', sa.String(length=20), nullable=False, server_default='invoice'),
    )
    op.create_check_constraint(
        'ck_recurring_invoices_expense_nature',
        'recurring_invoices',
        "expense_nature IN ('invoice', 'accrual')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_recurring_invoices_expense_nature', 'recurring_invoices', type_='check')
    op.drop_column('recurring_invoices', 'expense_nature')

    op.drop_constraint('ck_invoices_expense_nature', 'invoices', type_='check')
    op.drop_column('invoices', 'expense_nature')
