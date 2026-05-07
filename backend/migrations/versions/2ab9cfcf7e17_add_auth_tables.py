"""add_auth_tables

Revision ID: 2ab9cfcf7e17
Revises: 6cc5ec319b46
Create Date: 2026-04-17 11:46:52.451563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ab9cfcf7e17'
down_revision: Union[str, Sequence[str], None] = '6cc5ec319b46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=True),
    sa.Column('target_id', sa.String(length=50), nullable=True),
    sa.Column('event_metadata', sa.JSON(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_token', sa.String(length=128), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_active_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_token')
    )
    op.create_table('user_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_type', sa.String(length=20), nullable=False),
    sa.Column('token_hash', sa.String(length=255), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('approval_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('invoice_id', sa.Integer(), nullable=False),
    sa.Column('requested_by', sa.Integer(), nullable=False),
    sa.Column('requested_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
    sa.Column('resolved_by', sa.Integer(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('resolution_note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('users', sa.Column('full_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('must_reset_password', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('password_set_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('invited_by_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(None, 'users', 'users', ['invited_by_id'], ['id'])
    op.drop_column('users', 'name')


def downgrade() -> None:
    op.drop_constraint('users_email_key', 'users', type_='unique')
    op.add_column('users', sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_constraint('users_invited_by_id_fkey', 'users', type_='foreignkey')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'invited_by_id')
    op.drop_column('users', 'password_set_at')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
    op.drop_column('users', 'must_reset_password')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'full_name')
    op.drop_table('approval_requests')
    op.drop_table('user_tokens')
    op.drop_table('sessions')
    op.drop_table('audit_log')
