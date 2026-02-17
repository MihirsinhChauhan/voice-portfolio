"""Add visitor_id and user_profiles for long-term memory.

Revision ID: 20260217_001
Revises: 20250216_001
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260217_001"
down_revision: Union[str, None] = "20250216_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Stable, cookie-backed visitor id (normalized to 32-char hex).
    op.add_column("users", sa.Column("visitor_id", sa.String(32), nullable=True))
    op.create_index("ix_users_visitor_id", "users", ["visitor_id"], unique=True)

    # Lightweight profile memory (high-signal fields only).
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("last_intent_type", sa.String(32), nullable=True),
        sa.Column("booked_before", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
    op.drop_index("ix_users_visitor_id", table_name="users")
    op.drop_column("users", "visitor_id")

