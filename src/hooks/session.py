import re

from livekit import agents, rtc
from livekit.agents import AgentSession, room_io
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from src.agents.protfolio_agent import (
    BookingUserData,
    ConversationState,
    PortfolioAssistant,
)


def _custom_text_input_handler(
    session: AgentSession, event: room_io.TextInputEvent
) -> None:
    """Normalize typed booking details before routing to the LLM."""
    message = (event.text or "").strip()
    if not message:
        return

    userdata = session.userdata
    if (
        isinstance(userdata, BookingUserData)
        and userdata.state == ConversationState.BOOKING_COLLECT_NAME_AND_EMAIL
    ):
        # If the user typed a compact string like "Alice, alice@example.com",
        # rewrite it to explicit fields so extraction is deterministic.
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", message)
        if email_match:
            email = email_match.group(0).strip()
            name = message[: email_match.start()].strip(" ,:-")
            if name:
                message = f"My full name is {name} and my email is {email}."

    session.interrupt()
    session.generate_reply(user_input=message)


async def portfolio_agent_handler(ctx: agents.JobContext):
    session = AgentSession(
        stt="assemblyai/universal-streaming-multilingual",
        llm="openai/gpt-4o-mini",
        # tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        tts="inworld/inworld-tts-1.5-mini",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
        userdata=BookingUserData(),
    )

    await session.start(
        room=ctx.room,
        agent=PortfolioAssistant(),
        room_options=room_io.RoomOptions(
            text_input=room_io.TextInputOptions(
                text_input_cb=_custom_text_input_handler
            ),
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            ),
        ),
    )