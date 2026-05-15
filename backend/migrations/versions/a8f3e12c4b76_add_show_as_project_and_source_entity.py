"""add show_as_project to entities and source_entity_id/description to projects

Revision ID: a8f3e12c4b76
Revises: c3b5a7f2d1e4
Create Date: 2026-05-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8f3e12c4b76'
down_revision: Union[str, Sequence[str], None] = 'c3b5a7f2d1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('entities', sa.Column('show_as_project', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('projects', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('source_entity_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_projects_source_entity_id',
        'projects', 'entities',
        ['source_entity_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_projects_source_entity_id', 'projects', type_='foreignkey')
    op.drop_column('projects', 'source_entity_id')
    op.drop_column('projects', 'description')
    op.drop_column('entities', 'show_as_project')
