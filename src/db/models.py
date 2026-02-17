"""SQLAlchemy models matching the conversation analysis ERD.
Used for Alembic metadata and reference; type-safe queries use sqlc-generated code.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def uuid7_hex() -> str:
    """Return a new UUID as hex string (use uuid4 for now; can switch to uuid7 later)."""
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=uuid7_hex
    )
    visitor_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_sessions: Mapped[int] = mapped_column(Integer, default=0)
    total_bookings: Mapped[int] = mapped_column(Integer, default=0)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")
    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user", uselist=False
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_intent_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    booked_before: Mapped[bool] = mapped_column(Boolean, default=False)
    last_visit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=uuid7_hex
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    booking_made: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending | in_progress | completed | failed
    analysis_version: Mapped[int] = mapped_column(Integer, default=1)
    r2_report_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    r2_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    analysis_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_analysis_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="sessions")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="session")
    analysis_result: Mapped["AnalysisResult | None"] = relationship(
        back_populates="session", uselist=False
    )

    __table_args__ = (Index("ix_sessions_user_id_analysis_status", "user_id", "analysis_status"),)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=uuid7_hex
    )
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    session: Mapped["Session"] = relationship(back_populates="bookings")
    user: Mapped["User"] = relationship(back_populates="bookings")

    __table_args__ = (
        Index("ix_bookings_user_id", "user_id"),
        Index("ix_bookings_session_id", "session_id"),
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=uuid7_hex
    )
    session_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False)
    lead_score: Mapped[float] = mapped_column(Float, nullable=False)
    intent_label: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    session: Mapped["Session"] = relationship(back_populates="analysis_result")
