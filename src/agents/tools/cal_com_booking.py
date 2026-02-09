"""Cal.com API client for voice bot meeting booking."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Cal.com slots API version header (required for GET /slots)
CALCOM_SLOTS_API_VERSION = "2024-09-04"


def _require_calcom_config() -> None:
    if not settings.CALCOM_API_KEY or not settings.CALCOM_EVENT_TYPE_ID:
        raise ValueError(
            "Cal.com is not configured. Set CALCOM_API_KEY and CALCOM_EVENT_TYPE_ID in your environment."
        )


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse time string to (hour, minute). Accepts 14:00 or 2:00 PM."""
    time_str = time_str.strip().upper()
    if "AM" in time_str or "PM" in time_str:
        time_str_clean = time_str.replace(" ", "")
        t = datetime.strptime(time_str_clean, "%I:%M%p").time()
    else:
        t = datetime.strptime(time_str, "%H:%M").time()
    return t.hour, t.minute


def _build_start_utc_iso(date_str: str, time_str: str, timezone_str: str) -> str:
    """Build start datetime in the given timezone and return as UTC ISO string (e.g. 2024-08-13T09:00:00Z)."""
    date_str = date_str.strip()
    try:
        base_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Date must be YYYY-MM-DD, got: {date_str}")
    hour, minute = _parse_time(time_str)
    local_dt = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    tz = ZoneInfo(timezone_str)
    utc_dt = local_dt.replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_slot_time(iso_start: str, timezone: str = "Asia/Kolkata") -> str:
    """Format ISO start time for voice in the given timezone (e.g. 09:00 -> 9:00 AM).
    Cal.com returns slots in UTC; we convert to the user's timezone for display.
    """
    try:
        if "+" in iso_start or iso_start.endswith("Z"):
            dt_utc = datetime.fromisoformat(iso_start.replace("Z", "+00:00"))
        else:
            dt_utc = datetime.strptime(iso_start[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=ZoneInfo("UTC")
            )
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            tz = ZoneInfo("Asia/Kolkata")
        dt_local = dt_utc.astimezone(tz)
        h, m = dt_local.hour, dt_local.minute
        if h == 0:
            return f"12:{m:02d} AM"
        if h < 12:
            return f"{h}:{m:02d} AM"
        if h == 12:
            return f"12:{m:02d} PM"
        return f"{h - 12}:{m:02d} PM"
    except Exception:
        return iso_start[:16].replace("T", " ")


async def get_available_slots(
    start_date: str,
    end_date: str,
    timezone: str = "Asia/Kolkata",
) -> str:
    """Fetch available Cal.com slots for the given date range.

    Args:
        start_date: Start of range (YYYY-MM-DD).
        end_date: End of range (YYYY-MM-DD), inclusive.
        timezone: IANA timezone (e.g. Asia/Kolkata) to display slot times in. Default Asia/Kolkata.

    Returns:
        Human-readable summary of available slots per day for the agent to read to the user,
        or an error message.
    """
    _require_calcom_config()

    # Cal.com slots API expects startTime and endTime in ISO format for the range
    start_time = f"{start_date.strip()}T00:00:00"
    end_time = f"{end_date.strip()}T23:59:59"
    logger.info(
        "get_available_slots: request start_date=%s end_date=%s start_time=%s end_time=%s",
        start_date, end_date, start_time, end_time,
    )

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.CALCOM_BASE_URL.rstrip('/')}/slots",
            params={
                "eventTypeId": settings.CALCOM_EVENT_TYPE_ID,
                "start": start_time,
                "end": end_time,
            },
            headers={
                "Authorization": f"Bearer {settings.CALCOM_API_KEY}",
                "cal-api-version": settings.CALCOM_API_VERSION,
            },
            timeout=15.0,
        )

    if resp.status_code >= 400:
        try:
            err = resp.json()
            msg = err.get("message", err.get("error", resp.text))
        except Exception:
            msg = resp.text
        result = f"Could not fetch slots: {msg}"
        logger.warning(
            "get_available_slots: FAILED status=%s body=%s -> result=%s",
            resp.status_code, resp.text[:500], result,
        )
        return result

    data = resp.json()
    if data.get("status") != "success":
        result = "Could not fetch slots: unexpected response."
        logger.warning(
            "get_available_slots: unexpected response status=%s data=%s -> result=%s",
            data.get("status"), str(data)[:500], result,
        )
        return result

    slots_by_date = data.get("data") or {}
    if not slots_by_date:
        return f"No available slots between {start_date} and {end_date}."

    lines = []
    for date_key in sorted(slots_by_date.keys()):
        slots = slots_by_date[date_key]
        if not slots:
            continue
        times = [
            _format_slot_time(s.get("start", ""), timezone=timezone)
            for s in slots
            if s.get("start")
        ]
        if times:
            lines.append(f"On {date_key} available times are: {', '.join(times)}.")

    if not lines:
        result = f"No available slots between {start_date} and {end_date}."
        logger.info("get_available_slots: no slots found -> result=%s", result)
        return result

    result = " ".join(lines)
    logger.info("get_available_slots: SUCCESS -> result=%s", result)
    return result


async def create_calcom_booking(
    *,
    attendee_name: str,
    attendee_email: str,
    timezone: str,
    start: str,
    notes: str | None = None,
) -> str:
    """Create a booking via Cal.com API v2 (POST /bookings).

    Uses attendee (name, email, timeZone), start (ISO UTC), eventTypeId.
    Do not send lengthInMinutes for event types with a single fixed duration.
    """
    _require_calcom_config()

    # Do not send lengthInMinutes - Cal.com event types with a single fixed duration reject it
    payload = {
        "eventTypeId": int(settings.CALCOM_EVENT_TYPE_ID),
        "start": start,
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": timezone,
            "language": "en",
        },
    }
    if notes:
        payload["metadata"] = {"notes": notes}

    booking_api_version = getattr(
        settings, "CALCOM_BOOKING_API_VERSION", "2024-08-13"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.CALCOM_BASE_URL.rstrip('/')}/bookings",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.CALCOM_API_KEY}",
                "Content-Type": "application/json",
                "cal-api-version": booking_api_version,
            },
            timeout=15.0,
        )

    if resp.status_code >= 400:
        try:
            err = resp.json()
            msg = err.get("message", err.get("error", resp.text))
        except Exception:
            msg = resp.text
        result = f"Booking failed: {msg}"
        logger.warning(
            "create_calcom_booking: FAILED status=%s body=%s -> result=%s",
            resp.status_code, resp.text[:500], result,
        )
        return result

    data = resp.json()
    booking = data.get("booking", data)
    start_time = booking.get("startTime") or start
    result = f"Meeting booked successfully for {start_time}. Confirmation has been sent to {attendee_email}."
    logger.info("create_calcom_booking: SUCCESS -> result=%s", result)
    return result


async def book_meeting(
    attendee_name: str,
    attendee_email: str,
    date: str,
    time_slot: str,
    timezone: str = "UTC",
    notes: str | None = None,
) -> str:
    """Book a meeting with the founder via Cal.com. Use after the user has chosen a slot from the available options.

    Args:
        attendee_name: Full name of the person booking.
        attendee_email: Email for the booking confirmation.
        date: Date in YYYY-MM-DD format (e.g. 2025-02-10).
        time_slot: Time (e.g. 14:00 or 2:00 PM).
        timezone: IANA timezone (e.g. America/New_York, Europe/London). Default UTC.
        notes: Optional notes for the meeting.

    Returns:
        Success or error message string.
    """
    logger.info(
        "book_meeting: request attendee=%s email=%s date=%s time_slot=%s timezone=%s",
        attendee_name, attendee_email, date, time_slot, timezone,
    )
    try:
        start_utc = _build_start_utc_iso(date, time_slot, timezone)
    except ValueError as e:
        result = f"Invalid date or time: {e}"
        logger.warning("book_meeting: validation failed -> result=%s", result)
        return result
    except Exception as e:
        result = f"Invalid timezone or time: {e}"
        logger.warning("book_meeting: validation failed -> result=%s", result)
        return result

    return await create_calcom_booking(
        attendee_name=attendee_name,
        attendee_email=attendee_email,
        timezone=timezone,
        start=start_utc,
        notes=notes,
    )
