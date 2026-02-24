"""Phase 6D: Error-handling scenarios with mocked tools.

Tests for:
- Cal.com unavailable / returns 500
- get_available_slots returns "no slots"
- Invalid date/time/timezone inputs
- Booking tool returns failure
"""
import pytest

from livekit.agents import mock_tools

from src.agents.protfolio_agent import BookingUserData, PortfolioAssistant
from tests.helpers.session_factory import create_judge_llm, create_test_session


@pytest.mark.asyncio
async def test_calcom_unavailable_error() -> None:
    """Test that Cal.com unavailability is handled gracefully."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        # Mock get_available_slots to raise an exception (simulating Cal.com down)
        def mock_get_available_slots_error(
            start_date: str, end_date: str, timezone: str = "Asia/Kolkata"
        ) -> str:
            raise RuntimeError("Cal.com API returned 500")

        with mock_tools(
            PortfolioAssistant,
            {"get_available_slots": mock_get_available_slots_error},
        ):
            await session.run(user_input="")
            await session.run(user_input="I'd like to book a call")
            await session.run(user_input="My name is Alice")
            await session.run(user_input="alice@example.com")
            await session.run(user_input="How about next week?")

            result = await session.run(user_input="")

            # Should have an error message from the tool wrapper
            # The agent should respond with apology and fallback
            msg_event = result.expect.next_event().is_message(role="assistant")

            if judge_llm:
                await msg_event.judge(
                    judge_llm,
                    intent=(
                        "Should apologize once for booking system trouble. "
                        "Should explain briefly that the calendar system is having issues. "
                        "Should offer a simple fallback (like suggesting times manually or email follow-up). "
                        "Should be calm, not blame the user, and not loop endlessly."
                    ),
                )

            result.expect.no_more_events()


@pytest.mark.asyncio
async def test_no_slots_available() -> None:
    """Test that 'no slots' response is handled gracefully."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        def mock_get_current_datetime(timezone: str = "UTC") -> str:
            return "Current date: 2025-02-20 (Thursday). Current time: 14:00 UTC."

        def mock_get_available_slots_no_slots(
            start_date: str, end_date: str, timezone: str = "Asia/Kolkata"
        ) -> str:
            return f"No available slots between {start_date} and {end_date}."

        with mock_tools(
            PortfolioAssistant,
            {
                "get_current_datetime": mock_get_current_datetime,
                "get_available_slots": mock_get_available_slots_no_slots,
            },
        ):
            await session.run(user_input="")
            await session.run(user_input="I'd like to book a call")
            await session.run(user_input="My name is Alice")
            await session.run(user_input="alice@example.com")

            result = await session.run(user_input="How about next week?")

            # Should call get_current_datetime, then get_available_slots
            result.expect.next_event().is_function_call(name="get_current_datetime")
            result.expect.next_event().is_function_call_output()
            result.expect.next_event().is_function_call(name="get_available_slots")
            result.expect.next_event().is_function_call_output()

            # Agent should respond to "no slots" gracefully
            msg_event = result.expect.next_event().is_message(role="assistant")

            if judge_llm:
                await msg_event.judge(
                    judge_llm,
                    intent=(
                        "Should acknowledge that no slots are available. "
                        "Should offer alternatives like a different date range or email follow-up. "
                        "Should be helpful and not frustrated."
                    ),
                )

            result.expect.no_more_events()


@pytest.mark.asyncio
async def test_invalid_date_time_error() -> None:
    """Test that invalid date/time inputs are handled gracefully."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        def mock_get_available_slots(
            start_date: str, end_date: str, timezone: str = "Asia/Kolkata"
        ) -> str:
            # Simulate invalid date format error
            if not start_date or len(start_date) != 10:
                return "ERROR: Invalid date format. Date must be YYYY-MM-DD."
            return (
                "On 2025-02-21 available times are: 9:00 AM, 2:00 PM. "
                "On 2025-02-22 available times are: 10:00 AM."
            )

        def mock_book_meeting(
            attendee_name: str,
            attendee_email: str,
            date: str,
            time_slot: str,
            timezone: str = "Asia/Kolkata",
            notes: str = "",
        ) -> str:
            # Simulate invalid time format
            if ":" not in time_slot and "AM" not in time_slot.upper() and "PM" not in time_slot.upper():
                return "ERROR: Invalid time format. Time must be HH:MM or X:XX AM/PM."
            return (
                f"Meeting booked successfully for {date} at {time_slot}. "
                f"Confirmation has been sent to {attendee_email}."
            )

        with mock_tools(
            PortfolioAssistant,
            {
                "get_available_slots": mock_get_available_slots,
                "book_meeting": mock_book_meeting,
            },
        ):
            await session.run(user_input="")
            await session.run(user_input="I'd like to book a call")
            await session.run(user_input="My name is Alice")
            await session.run(user_input="alice@example.com")

            # User provides invalid date format
            result = await session.run(user_input="How about tomorrow?")

            # Should handle gracefully
            msg_event = result.expect.next_event().is_message(role="assistant")

            if judge_llm:
                await msg_event.judge(
                    judge_llm,
                    intent=(
                        "Should handle date parsing gracefully. Should ask for clarification "
                        "or suggest a specific date format if needed. Should be helpful."
                    ),
                )

            result.expect.no_more_events()


@pytest.mark.asyncio
async def test_booking_failure_recovery() -> None:
    """Test that booking failure is handled gracefully with fallback."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        def mock_get_current_datetime(timezone: str = "UTC") -> str:
            return "Current date: 2025-02-20 (Thursday). Current time: 14:00 UTC."

        def mock_get_available_slots(
            start_date: str, end_date: str, timezone: str = "Asia/Kolkata"
        ) -> str:
            return "On 2025-02-21 available times are: 2:00 PM."

        def mock_book_meeting_failure(
            attendee_name: str,
            attendee_email: str,
            date: str,
            time_slot: str,
            timezone: str = "Asia/Kolkata",
            notes: str = "",
        ) -> str:
            # Simulate booking failure (e.g., slot already taken, API error)
            return "Booking failed: The selected time slot is no longer available."

        with mock_tools(
            PortfolioAssistant,
            {
                "get_current_datetime": mock_get_current_datetime,
                "get_available_slots": mock_get_available_slots,
                "book_meeting": mock_book_meeting_failure,
            },
        ):
            await session.run(user_input="")
            await session.run(user_input="I'd like to book a call")
            await session.run(user_input="My name is Alice")
            await session.run(user_input="alice@example.com")
            await session.run(user_input="How about February 21st?")

            # Should call get_available_slots and present options
            result1 = await session.run(user_input="")
            result1.expect.next_event().is_function_call(name="get_available_slots")
            result1.expect.next_event().is_function_call_output()
            result1.expect.next_event().is_message(role="assistant")
            result1.expect.no_more_events()

            # User picks a slot
            result2 = await session.run(user_input="2:00 PM works")

            # Should call book_meeting, which will fail
            result2.expect.next_event().is_function_call(name="book_meeting")
            result2.expect.next_event().is_function_call_output()

            # Agent should respond to failure gracefully
            msg_event = result2.expect.next_event().is_message(role="assistant")

            if judge_llm:
                await msg_event.judge(
                    judge_llm,
                    intent=(
                        "Should acknowledge the booking failure. Should apologize once. "
                        "Should explain the issue (slot unavailable). "
                        "Should offer a clear fallback (different time, email follow-up, etc.). "
                        "Should not loop endlessly or blame the user. Should transition toward warm close."
                    ),
                )

            result2.expect.no_more_events()


@pytest.mark.asyncio
async def test_missing_calcom_config_error() -> None:
    """Test that missing Cal.com config is handled gracefully."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        # Mock to simulate missing config (ValueError from _require_calcom_config)
        def mock_get_available_slots_config_error(
            start_date: str, end_date: str, timezone: str = "Asia/Kolkata"
        ) -> str:
            raise ValueError(
                "Cal.com is not configured. Set CALCOM_API_KEY and CALCOM_EVENT_TYPE_ID."
            )

        with mock_tools(
            PortfolioAssistant,
            {"get_available_slots": mock_get_available_slots_config_error},
        ):
            await session.run(user_input="")
            await session.run(user_input="I'd like to book a call")
            await session.run(user_input="My name is Alice")
            await session.run(user_input="alice@example.com")

            result = await session.run(user_input="How about next week?")

            # Should handle config error gracefully
            msg_event = result.expect.next_event().is_message(role="assistant")

            if judge_llm:
                await msg_event.judge(
                    judge_llm,
                    intent=(
                        "Should acknowledge booking system issue. Should apologize once. "
                        "Should offer a fallback (email follow-up, manual scheduling). "
                        "Should not expose technical details about missing config to user."
                    ),
                )

            result.expect.no_more_events()
