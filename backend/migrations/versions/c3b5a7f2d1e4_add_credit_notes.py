"""add credit_notes and credit_note_links tables

Revision ID: c3b5a7f2d1e4
Revises: eaab0afde50e
Create Date: 2026-05-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3b5a7f2d1e4'
down_revision: Union[str, Sequence[str], None] = 'eaab0afde50e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'credit_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('invoice_files.id'), nullable=True),
        sa.Column('supplier_name_raw', sa.String(), nullable=True),
        sa.Column('paying_entity_raw', sa.String(), nullable=True),
        sa.Column('paying_entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('credit_number', sa.String(), nullable=True),
        sa.Column('credit_date', sa.Date(), nullable=True),
        sa.Column('gross_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('vat_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('net_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('currency', sa.String(), nullable=True, server_default='GBP'),
        sa.Column('ocr_status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('extraction_status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('review_status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('is_approved_to_pay', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('is_paid', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('is_legacy', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'credit_note_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('credit_note_id', sa.Integer(), sa.ForeignKey('credit_notes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=True),
        sa.Column('allocated_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('credit_note_links')
    op.drop_table('credit_notes')
