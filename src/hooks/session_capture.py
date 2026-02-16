"""
Session end capture: upload session report to R2 and persist session + user in DB.
Used as on_session_end callback for the LiveKit agent server.
"""
from __future__ import annotations

import asyncio
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
) -> None:
    """Run R2 upload and DB writes in a thread (sync)."""
    from src.config.settings import settings
    from src.db.connection import get_engine
    from src.db.sqlc import SessionsQuerier, UsersQuerier
    from src.db.sqlc.sessions import InsertSessionParams
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
    with engine.connect() as conn:
        with conn.begin():
            users = UsersQuerier(conn)
            sessions_querier = SessionsQuerier(conn)
            user_id = str(uuid.uuid4()).replace("-", "")[:32]
            if participant_identity and _identity_looks_like_email(participant_identity):
                email, name = participant_identity.strip(), None
            else:
                email = f"anon-{job_id}@session.local"
                name = None
            user = users.upsert_user_by_email(id=user_id, email=email, name=name)
            if user:
                user_id = user.id
            users.increment_user_session_count(id=user_id)

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
                    booking_made=False,
                    analysis_version=1,
                    r2_report_path=r2_path,
                    r2_audio_path=None,
                )
            )
    logger.info(
        "Session capture: report=%s user_id=%s session_id=%s",
        r2_key, user_id, job_id,
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

    await asyncio.to_thread(
        _capture_sync,
        report_dict,
        r2_key,
        job_id,
        room_name,
        participant_identity,
        started_at,
        duration,
    )
