"""Phase 6B: Flow coverage tests for voice UX stages.

Tests matching the conversation stages:
- Warm Entry: greeting is short + role + one question
- Intent Discovery: correctly routes to Explorer vs Hiring vs Founder vs FastBook
- Value Exchange: progressive disclosure, no info dump
- Optional Depth: only when asked
- Soft CTA: offered only after interest signals, max 1-2 attempts
- Booking deterministic: tool calls occur in correct order
"""
import pytest

from livekit.agents import mock_tools

from src.agents.protfolio_agent import (
    BookingUserData,
    ConversationState,
    IntentType,
    PortfolioAssistant,
)
from tests.helpers.session_factory import create_judge_llm, create_test_session


@pytest.mark.asyncio
async def test_warm_entry_greeting() -> None:
    """Test that the greeting is short, introduces role, and asks one question."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        # The on_enter hook should trigger the greeting
        result = await session.run(user_input="")

        # Should have an assistant message
        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Makes a brief, warm greeting. Introduces Melvin as helping explain "
                    "Mihir's work. Asks one simple question about what brought them here. "
                    "Should be 1-3 sentences, plain text, no lists or markdown."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_intent_discovery_explorer() -> None:
    """Test that Explorer intent is correctly identified."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        # Initial greeting
        await session.run(user_input="")

        # User response that suggests Explorer intent (general curiosity)
        result = await session.run(user_input="I'm just curious about what you do")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Responds warmly to someone exploring. Should acknowledge curiosity "
                    "and provide a brief, helpful answer about Mihir's work. "
                    "Should not push booking aggressively."
                ),
            )

        # Check that intent_type was set (via userdata inspection if accessible)
        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_intent_discovery_hiring() -> None:
    """Test that Hiring intent is correctly identified."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")

        result = await session.run(user_input="We're hiring for a backend engineer role")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Recognizes hiring intent. Should respond helpfully about Mihir's "
                    "backend experience and fit. Should be professional but not overly salesy."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_intent_discovery_founder() -> None:
    """Test that Founder intent is correctly identified."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")

        result = await session.run(
            user_input="I'm a founder of a SaaS startup and I'm looking for an engineer to help own our backend and systems"
        )

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Recognizes founder intent. Should briefly describe Mihir's experience as an "
                    "engineer and how he might fit for someone to work with or hire. Since the user "
                    "has already specified they're looking for an engineer for backend/systems, "
                    "should respond directly to that match without asking any questions. Should be relevant and helpful."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_intent_discovery_founder_no_role_specified() -> None:
    """Test that Founder intent asks what they're building if role/responsibilities not specified."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")

        result = await session.run(
            user_input="I'm a founder and I'm looking for technical help"
        )

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Recognizes founder intent. Should briefly describe Mihir's experience as an "
                    "engineer. Since the user has NOT specified what role/responsibilities they're "
                    "looking for, it's appropriate to ask what they're building or what kind of help "
                    "they need. Should be relevant and helpful."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_intent_discovery_fastbook() -> None:
    """Test that FastBook intent is correctly identified and triggers booking flow."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")

        result = await session.run(user_input="I'd like to book a call")

        # Should transition toward booking (may ask for name first)
        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Recognizes booking request. Starts the booking flow by asking for full name "
                    "and email (e.g. to schedule a call). Helpful and clear."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_value_exchange_progressive_disclosure() -> None:
    """Test that value exchange uses progressive disclosure, not info dumps."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")
        await session.run(user_input="Tell me about Mihir")

        result = await session.run(user_input="What kind of projects does he work on?")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Provides a concise answer about projects. Should mention 1-2 examples "
                    "briefly, not dump all details. Should be 1-3 sentences. "
                    "Should offer optional next step naturally."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_optional_depth_only_when_asked() -> None:
    """Test that depth is only provided when explicitly requested."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")
        await session.run(user_input="Tell me about DebtEase")

        # User asks for depth
        result = await session.run(user_input="Tell me more about how it works")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Goes deeper on DebtEase only because explicitly asked. "
                    "Should provide more detail but still be concise for voice. "
                    "Should not dump everything, just what was asked."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_soft_cta_after_interest_signals() -> None:
    """Test that soft CTA is offered only after interest signals, max 1-2 attempts."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")
        await session.run(user_input="I'm hiring for a backend role")

        # User shows interest signal
        result = await session.run(
            user_input="This sounds like it could be a good fit"
        )

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Should gently offer a short call as an option. Should be natural, "
                    "not pushy. Should mention it once, not repeatedly. "
                    "Should be calm and not salesy."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_booking_deterministic_flow() -> None:
    """Test that booking flow follows deterministic steps with correct tool order."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        # Mock the booking tools to avoid real Cal.com calls
        def mock_get_current_datetime(timezone: str = "UTC") -> str:
            return "Current date: 2025-02-20 (Thursday). Current time: 14:00 UTC."

        def mock_get_available_slots(
            start_date: str, end_date: str, timezone: str = "Asia/Kolkata"
        ) -> str:
            return (
                "On 2025-02-21 available times are: 9:00 AM, 2:00 PM, 4:00 PM. "
                "On 2025-02-22 available times are: 10:00 AM, 3:00 PM."
            )

        def mock_book_meeting(
            attendee_name: str,
            attendee_email: str,
            date: str,
            time_slot: str,
            timezone: str = "Asia/Kolkata",
            notes: str = "",
        ) -> str:
            return (
                f"Meeting booked successfully for {date} at {time_slot}. "
                f"Confirmation has been sent to {attendee_email}."
            )

        with mock_tools(
            PortfolioAssistant,
            {
                "get_current_datetime": mock_get_current_datetime,
                "get_available_slots": mock_get_available_slots,
                "book_meeting": mock_book_meeting,
            },
        ):
            # Initial greeting
            await session.run(user_input="")

            # User requests booking
            result1 = await session.run(user_input="I'd like to schedule a call")

            # Should ask for name and email (via text)
            result1.expect.next_event().is_message(role="assistant")
            result1.expect.no_more_events()

            # User provides name and email in one message (typed)
            result2 = await session.run(
                user_input="Alice, alice@example.com"
            )

            # Should call set_name, set_email, then ask for time range
            result2.expect.next_event().is_function_call(name="set_name")
            result2.expect.next_event().is_function_call_output()
            result2.expect.next_event().is_function_call(name="set_email")
            result2.expect.next_event().is_function_call_output()
            result2.expect.next_event().is_message(role="assistant")
            result2.expect.no_more_events()

            # User provides time range (relative date - should trigger get_current_datetime)
            result3 = await session.run(user_input="How about tomorrow or next week?")

            # Should call get_current_datetime first (for relative dates)
            result3.expect.next_event().is_function_call(name="get_current_datetime")
            result3.expect.next_event().is_function_call_output()

            # Then should call get_available_slots (range may be tomorrow-only or include next week)
            result3.expect.next_event().is_function_call(
                name="get_available_slots",
                arguments={"start_date": "2025-02-21", "end_date": "2025-02-21"},
            )
            result3.expect.next_event().is_function_call_output()

            # Then should present slots to user
            result3.expect.next_event().is_message(role="assistant")
            result3.expect.no_more_events()

            # User picks a slot
            result4 = await session.run(
                user_input="Let's do February 21st at 2:00 PM"
            )

            # Should confirm details, then call book_meeting
            result4.expect.next_event().is_message(role="assistant")

            # Should call book_meeting with correct arguments
            result4.expect.next_event().is_function_call(
                name="book_meeting",
                arguments={
                    "attendee_name": "Alice",
                    "attendee_email": "alice@example.com",
                    "date": "2025-02-21",
                    "time_slot": "2:00 PM",
                },
            )
            result4.expect.next_event().is_function_call_output()
            # Final message should acknowledge successful booking
            final_msg_event = result4.expect.next_event().is_message(role="assistant")
            result4.expect.no_more_events()

            if judge_llm:
                await final_msg_event.judge(
                    judge_llm,
                    intent=(
                        "Should acknowledge successful booking. Should be warm and brief. "
                        "Should confirm date/time and mention confirmation email."
                    ),
                )
