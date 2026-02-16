"""Initial conversation analysis schema: users, sessions, bookings, analysis_results.

Revision ID: 20250216_001
Revises:
Create Date: 2025-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250216_001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_sessions", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_bookings", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("booking_made", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("analysis_status", sa.String(32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("analysis_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("r2_report_path", sa.String(512), nullable=True),
        sa.Column("r2_audio_path", sa.String(512), nullable=True),
        sa.Column("analysis_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_analysis_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_user_id_analysis_status", "sessions", ["user_id", "analysis_status"], unique=False)

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(32), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"], unique=False)
    op.create_index("ix_bookings_session_id", "bookings", ["session_id"], unique=False)

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(32), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=False),
        sa.Column("engagement_score", sa.Float(), nullable=False),
        sa.Column("lead_score", sa.Float(), nullable=False),
        sa.Column("intent_label", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("analysis_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("uq_analysis_results_session_id", "analysis_results", ["session_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_analysis_results_session_id", table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index("ix_bookings_session_id", table_name="bookings")
    op.drop_index("ix_bookings_user_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_sessions_user_id_analysis_status", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
