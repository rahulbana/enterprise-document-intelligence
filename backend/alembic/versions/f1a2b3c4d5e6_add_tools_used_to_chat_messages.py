# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
"""add tools_used_json to chat_messages

Revision ID: f1a2b3c4d5e6
Revises: a334921169b9
Create Date: 2026-09-27 23:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "a334921169b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("tools_used_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "tools_used_json")
