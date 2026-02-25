"""Add MCP authentication fields

Revision ID: 20260207_add_mcp_auth
Revises:
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260207_add_mcp_auth'
down_revision = None  # Update this to your last migration ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add MCP authentication fields to mcp_configs table
    op.add_column('mcp_configs', sa.Column('auth_type', sa.String(50), nullable=True))
    op.add_column('mcp_configs', sa.Column('auth_token', sa.Text(), nullable=True))
    op.add_column('mcp_configs', sa.Column('auth_header_name', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('mcp_configs', 'auth_header_name')
    op.drop_column('mcp_configs', 'auth_token')
    op.drop_column('mcp_configs', 'auth_type')
