"""add_product_to_audit_logs

Revision ID: a1b2c3d4e5f6
Revises: 68ace53522bf
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '68ace53522bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'audit_logs',
        sa.Column('product', sa.String(length=50), nullable=False, server_default='armorclaude')
    )
    op.create_index('ix_audit_logs_product', 'audit_logs', ['product'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_product', table_name='audit_logs')
    op.drop_column('audit_logs', 'product')
