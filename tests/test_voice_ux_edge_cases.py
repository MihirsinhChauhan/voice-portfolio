"""Phase 6C: Edge case tests for voice UX.

Tests for:
- Silence / empty transcript: gentle nudge or abort generation
- Confusion: apology + simpler restatement
- Interruption: acknowledges "I might have spoken too long" and shortens
- Just testing: polite, no booking push
"""
import pytest

from tests.helpers.session_factory import create_judge_llm, create_test_session


@pytest.mark.asyncio
async def test_silence_empty_transcript() -> None:
    """Test that silence/empty transcript gets a gentle nudge."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")

        # Empty or very short input
        result = await session.run(user_input="")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Should gently nudge or acknowledge silence. Should be brief and helpful. "
                    "Should not be frustrated or pushy. May ask a simple question to re-engage."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_confusion_apology_restatement() -> None:
    """Test that confusion triggers apology and simpler restatement."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")

        # User expresses confusion
        result = await session.run(user_input="I don't understand what you're saying")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Should apologize briefly. Should restate the gist in simpler terms. "
                    "Should offer one clear next option. Should be calm and helpful."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_interruption_acknowledgment() -> None:
    """Test that interruption is acknowledged gracefully."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")
        await session.run(user_input="Tell me everything about Mihir")

        # User interrupts (simulated by short response during long explanation)
        result = await session.run(user_input="Wait, stop")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Should acknowledge the interruption gracefully. May mention "
                    "'I might have spoken too long' or similar. Should be brief going forward. "
                    "Should not be defensive."
                ),
            )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_just_testing_polite_no_push() -> None:
    """Test that 'just testing' gets a polite response without booking push."""
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        await session.run(user_input="")

        result = await session.run(user_input="I'm just testing this out")

        msg_event = result.expect.next_event().is_message(role="assistant")

        if judge_llm:
            await msg_event.judge(
                judge_llm,
                intent=(
                    "Should respond politely. Should not push booking or be salesy. "
                    "Should be helpful but low-pressure. May acknowledge testing is fine."
                ),
            )

        result.expect.no_more_events()
