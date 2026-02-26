"""
Session end capture: upload session report to R2 and persist session + user in DB.
Used as on_session_end callback for the LiveKit agent server.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from livekit.agents import JobContext

from src.utils.logging import logger

# Optional dependencies: only use when configured
def _report_to_dict(report):
    """Build JSON-serializable dict from SessionReport (include started_at/duration)."""
    d = report.to_dict()
    if getattr(report, "started_at", None) is not None:
        d["started_at"] = report.started_at
    if getattr(report, "duration", None) is not None:
        d["duration"] = report.duration
    return d


def _identity_looks_like_email(identity: str) -> bool:
    return bool(identity and re.match(r"^[^@]+@[^@]+\.[^@]+$", identity.strip()))


def _normalize_visitor_id(identity: str) -> tuple[str | None, bool]:
    """
    Normalize a participant identity into a stable 32-char hex visitor id.

    Preferred formats:
    - UUID (any valid uuid string) -> uuid.hex
    - 32-char hex
    Fallback:
    - sha256(identity)[:32] (still stable, but indicates frontend mismatch)
    """
    s = (identity or "").strip()
    if not s:
        return None, False

    try:
        return uuid.UUID(s).hex, False
    except Exception:
        pass

    if re.fullmatch(r"[a-fA-F0-9]{32}", s):
        return s.lower(), False

    # Stable fallback for unexpected identity formats.
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32], True


def _get_participant_identity(ctx: JobContext) -> str | None:
    """Return first remote participant identity, or None if room empty."""
    try:
        for p in ctx.room.remote_participants.values():
            return p.identity or None
    except Exception:
        pass
    return None


def _capture_sync(
    report_dict: dict,
    r2_key: str,
    job_id: str,
    room_name: str,
    participant_identity: str | None,
    started_at_ts: float | None,
    duration_sec: float | None,
    conv_name: str | None = None,
    conv_email: str | None = None,
    booking_details=None,
) -> None:
    """Run R2 upload and DB writes in a thread (sync)."""
    from src.config.settings import settings
    from src.db.connection import get_engine
    from src.db.sqlc import BookingsQuerier, SessionsQuerier, UserProfilesQuerier, UsersQuerier
    from src.db.sqlc.bookings import InsertBookingParams
    from src.db.sqlc.sessions import InsertSessionParams
    from src.db.sqlc.user_profiles import UpsertUserProfileParams
    from src.storage import r2 as storage_r2

    # 1) Upload report to R2
    if settings.R2_ENDPOINT and settings.R2_BUCKET and settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY:
        try:
            storage_r2.upload_bytes(
                r2_key,
                json.dumps(report_dict, default=str).encode("utf-8"),
                content_type="application/json",
            )
        except Exception as e:
            logger.warning("Session capture: R2 upload failed for %s: %s", r2_key, e)

    # 2) Persist user + session in DB
    if not settings.DATABASE_URL:
        return
    try:
        engine = get_engine()
    except RuntimeError:
        return
    visitor_id: str | None = None
    # Simple heuristic: check if a successful booking message appears anywhere
    # in the session report. This lets us mark both the session row and the
    # long-term user profile as "booked_before" without wiring a separate
    # channel from the agent.
    report_text = ""
    try:
        report_text = json.dumps(report_dict, default=str)
    except Exception:
        report_text = str(report_dict)
    booking_made = "Meeting booked successfully" in report_text

    with engine.connect() as conn:
        with conn.begin():
            users = UsersQuerier(conn)
            profiles = UserProfilesQuerier(conn)
            sessions_querier = SessionsQuerier(conn)
            bookings_querier = BookingsQuerier(conn)
            user_id = uuid.uuid4().hex[:32]

            email: str | None = None
            name: str | None = None

            if participant_identity:
                if _identity_looks_like_email(participant_identity):
                    email = participant_identity.strip()
                else:
                    visitor_id, used_hash = _normalize_visitor_id(participant_identity)
                    if visitor_id and used_hash:
                        logger.warning(
                            "Session capture: participant identity not uuid/hex; hashed to visitor_id. identity=%r",
                            participant_identity,
                        )

            # Prefer conversation-collected name/email over identity heuristics.
            if conv_name:
                name = conv_name
            if conv_email:
                email = conv_email

            if visitor_id:
                user = users.upsert_user_by_visitor_id(id=user_id, visitor_id=visitor_id, email=email, name=name)
            else:
                # Fallback to email-based identity (or per-session anon email if missing).
                if not email:
                    email = f"anon-{job_id}@session.local"
                user = users.upsert_user_by_email(id=user_id, email=email, name=name)

            if user:
                user_id = user.id
            users.increment_user_session_count(id=user_id)
            profiles.upsert_user_profile(
                UpsertUserProfileParams(
                    user_id=user_id,
                    company=None,
                    domain=None,
                    last_intent_type=None,
                    # Phase 5: mark users as having booked at least once when
                    # we detect a successful booking in the session report.
                    booked_before=booking_made or None,
                )
            )

            if started_at_ts is not None:
                started_at = datetime.fromtimestamp(started_at_ts, tz=timezone.utc)
            else:
                started_at = datetime.now(timezone.utc)
            ended_at = None
            if started_at_ts is not None and duration_sec is not None:
                ended_at = datetime.fromtimestamp(started_at_ts + duration_sec, tz=timezone.utc)
            duration_int = int(duration_sec) if duration_sec is not None else None
            r2_path = r2_key if (settings.R2_ENDPOINT and settings.R2_BUCKET) else None
            sessions_querier.insert_session(
                InsertSessionParams(
                    id=job_id,
                    user_id=user_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_sec=duration_int,
                    # Phase 5: persist whether a booking was made in this session.
                    booking_made=booking_made,
                    analysis_version=1,
                    r2_report_path=r2_path,
                    r2_audio_path=None,
                )
            )

            if booking_made:
                users.increment_user_booking_count(id=user_id)
                if booking_details is not None:
                    try:
                        scheduled_dt = datetime.fromisoformat(
                            booking_details.scheduled_time_utc_iso.replace("Z", "+00:00")
                        )
                        bookings_querier.insert_booking(
                            InsertBookingParams(
                                id=uuid.uuid4().hex[:32],
                                session_id=job_id,
                                user_id=user_id,
                                scheduled_time=scheduled_dt,
                                timezone=booking_details.timezone,
                                status="scheduled",
                            )
                        )
                    except Exception as e:
                        logger.warning("Session capture: failed to insert booking row: %s", e)
    logger.info(
        "Session capture: report=%s user_id=%s session_id=%s visitor_id=%s",
        r2_key, user_id, job_id, visitor_id,
    )


async def on_session_end(ctx: JobContext) -> None:
    """
    Called when the agent session ends. Uploads session report to R2 and
    creates/updates user + session rows in the DB (when DATABASE_URL and R2 are set).
    """
    try:
        report = ctx.make_session_report()
    except Exception as e:
        logger.warning("Session capture: make_session_report failed: %s", e)
        return
    job_id = getattr(report, "job_id", "") or "unknown"
    room_name = getattr(report, "room", "") or getattr(report, "room_id", "") or "unknown"
    room_name_safe = re.sub(r"[^a-zA-Z0-9_-]", "_", room_name)[:128]
    r2_key = f"reports/{room_name_safe}/{job_id}.json"
    report_dict = _report_to_dict(report)
    started_at = getattr(report, "started_at", None)
    duration = getattr(report, "duration", None)
    participant_identity = _get_participant_identity(ctx)

    # Extract name/email/booking_details collected during the conversation.
    conv_name: str | None = None
    conv_email: str | None = None
    booking_details = None
    try:
        ud = ctx.primary_session.userdata
        conv_name = getattr(ud, "name", None)
        conv_email = getattr(ud, "email", None)
        booking_details = getattr(ud, "booking_details", None)
    except Exception as e:
        logger.warning("Session capture: could not read userdata: %s", e)

    await asyncio.to_thread(
        _capture_sync,
        report_dict,
        r2_key,
        job_id,
        room_name,
        participant_identity,
        started_at,
        duration,
        conv_name,
        conv_email,
        booking_details,
    )
