# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
"""add duration_ms to chat_messages

Revision ID: 17627f4d9cca
Revises: c5d4dccd3cec
Create Date: 2026-09-25 19:25:20.715189

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17627f4d9cca"
down_revision: str | None = "c5d4dccd3cec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "duration_ms")
