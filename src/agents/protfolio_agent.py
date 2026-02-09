import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from livekit.agents import Agent, function_tool, RunContext

from src.agents.prompts import PORTFOLIO_ASSISTANT_INSTRUCTIONS

logger = logging.getLogger(__name__)
from src.agents.tools.cal_com_booking import book_meeting as calcom_book_meeting
from src.agents.tools.cal_com_booking import get_available_slots as calcom_get_available_slots


@dataclass
class BookingUserData:
    """Stored profile for the current session (used when booking meetings)."""
    name: str | None = None
    email: str | None = None


class PortfolioAssistant(Agent):
    def __init__(self) -> None:
        instructions = (
            PORTFOLIO_ASSISTANT_INSTRUCTIONS
            + f"\n\n--------------------------------\nDATE AND TIME\n--------------------------------\n"
            f"For natural language like \"tomorrow\", \"next Monday\", or \"this week\", call get_current_datetime first "
            f"(optionally with the user's timezone, e.g. Asia/Kolkata if they said they're in India). "
            f"Use the result to compute the correct YYYY-MM-DD for get_available_slots and book_meeting."
        )
        super().__init__(instructions=instructions)

    @function_tool(
        name="get_current_datetime",
        description="Get the current date and time. Call this when the user says things like 'tomorrow', 'next Monday', 'this week', or asks what day/time it is, so you can compute correct dates for booking.",
    )
    async def get_current_datetime(
        self, context: RunContext[BookingUserData], timezone: str = "UTC"
    ) -> str:
        """Return the current date and time. Use when resolving relative dates like tomorrow or next Monday.
        Args:
            timezone: Optional IANA timezone (e.g. Asia/Kolkata, America/New_York) to show time in that zone.
        """
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            tz = ZoneInfo("UTC")
        now = datetime.now(tz=tz)
        result = (
            f"Current date: {now.strftime('%Y-%m-%d')} ({now.strftime('%A')}). "
            f"Current time: {now.strftime('%H:%M')} {timezone}."
        )
        logger.info("get_current_datetime: timezone=%s -> result=%s", timezone, result)
        return result

    @function_tool(
        name="set_name",
        description="Call this when the user has provided their full name. Store it for the booking.",
    )
    async def set_name(self, context: RunContext[BookingUserData], value: str) -> str:
        """Store the user's name for the current session. Call when the user says their name.
        Args:
            value: The full name the user provided.
        """
        context.userdata.name = value.strip()
        result = f"Got it, I have your name as {context.userdata.name}."
        logger.info("set_name: value=%s -> result=%s", value, result)
        return result

    @function_tool(
        name="set_email",
        description="Call this when the user has provided their email address. Store it for the booking.",
    )
    async def set_email(self, context: RunContext[BookingUserData], value: str) -> str:
        """Store the user's email for the current session. Call when the user says their email.
        Args:
            value: The email address the user provided.
        """
        context.userdata.email = value.strip()
        result = f"Got it, I have your email as {context.userdata.email}."
        logger.info("set_email: value=%s -> result=%s", value, result)
        return result

    @function_tool()
    async def get_available_slots(
        self,
        context: RunContext[BookingUserData],
        start_date: str,
        end_date: str,
        timezone: str = "Asia/Kolkata",
    ) -> str:
        """Get available meeting slots from Cal.com for a date range. Call this first when the user wants to book a meeting, so you can tell them which times are free before they choose.
        Args:
            start_date: Start of range in YYYY-MM-DD format (e.g. 2025-02-10).
            end_date: End of range in YYYY-MM-DD format (e.g. 2025-02-16).
            timezone: IANA timezone for the user (e.g. Asia/Kolkata for India). Use Asia/Kolkata if user is in India or timezone unknown.
        """
        result = await calcom_get_available_slots(
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
        )
        logger.info(
            "get_available_slots: start_date=%s end_date=%s timezone=%s -> result=%s",
            start_date, end_date, timezone, result,
        )
        return result

    @function_tool()
    async def book_meeting(
        self,
        context: RunContext[BookingUserData],
        attendee_name: str,
        attendee_email: str,
        date: str,
        time_slot: str,
            timezone: str = "Asia/Kolkata",
        notes: str = "",
    ) -> str:
        """Book a meeting with the founder using Cal.com. Use this only after the user has chosen a date and time from the available slots you showed them. Use stored name and email from set_name/set_email when the user already provided them; otherwise pass them here.
        Args:
            attendee_name: Full name of the person booking. Use stored name from session if already set.
            attendee_email: Email for the booking confirmation. Use stored email from session if already set.
            date: Date for the meeting in YYYY-MM-DD format (e.g. 2025-02-10).
            time_slot: Time for the meeting (e.g. 14:00 or 2:00 PM). Must be one of the slots returned by get_available_slots.
            timezone: IANA timezone for the attendee (e.g. America/New_York, Asia/Kolkata). Use UTC if not provided.
            notes: Optional notes or reason for the meeting.
        """
        name = (attendee_name or "").strip() or (context.userdata.name or "")
        email = (attendee_email or "").strip() or (context.userdata.email or "")
        if not name or not email:
            missing = []
            if not name:
                missing.append("name")
            if not email:
                missing.append("email")
            result = f"Cannot book yet: please ask the user for their {', '.join(missing)} and call set_name or set_email first."
            logger.info("book_meeting: skipped (missing %s) -> result=%s", missing, result)
            return result
        result = await calcom_book_meeting(
            attendee_name=name,
            attendee_email=email,
            date=date,
            time_slot=time_slot,
            timezone=timezone,
            notes=notes or None,
        )
        logger.info(
            "book_meeting: attendee=%s date=%s time_slot=%s -> result=%s",
            name, date, time_slot, result,
        )
        return result