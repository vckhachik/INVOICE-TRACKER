"""add recurring_invoices table

Revision ID: f1a2b3c4d5e6
Revises: b9d2f4a1c8e3
Create Date: 2026-06-26 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'b9d2f4a1c8e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recurring_invoices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('supplier_name_raw', sa.String(255), nullable=False),
        sa.Column('paying_entity_raw', sa.String(255), nullable=True),
        sa.Column('paying_entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('invoice_number_base', sa.String(255), nullable=False),
        sa.Column('gross_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('net_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False, server_default='GBP'),
        sa.Column('description', sa.Text(), nullable=True),
        # Scheduling
        sa.Column('frequency', sa.String(20), nullable=False),          # daily/weekly/monthly/yearly
        sa.Column('frequency_interval', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('day_of_month', sa.Integer(), nullable=True),         # 1-28, monthly only
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('max_occurrences', sa.Integer(), nullable=True),
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_due_date', sa.Date(), nullable=False),
        sa.Column('last_generated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        # Audit
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_recurring_invoices_next_due_date', 'recurring_invoices', ['next_due_date'])
    op.create_index('ix_recurring_invoices_is_active', 'recurring_invoices', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_recurring_invoices_is_active', 'recurring_invoices')
    op.drop_index('ix_recurring_invoices_next_due_date', 'recurring_invoices')
    op.drop_table('recurring_invoices')
