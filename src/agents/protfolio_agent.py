import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from livekit.agents import Agent, function_tool, llm, RunContext

from src.agents.prompts.v2 import PORTFOLIO_ASSISTANT_INSTRUCTIONS
from src.agents.tools.cal_com_booking import _build_start_utc_iso
from src.agents.tools.cal_com_booking import book_meeting as calcom_book_meeting
from src.agents.tools.cal_com_booking import get_available_slots as calcom_get_available_slots

logger = logging.getLogger(__name__)


class ConversationState:
    GREETING = "GREETING"
    DISCOVER_INTENT = "DISCOVER_INTENT"
    VALUE_EXCHANGE = "VALUE_EXCHANGE"
    OPTIONAL_DEPTH = "OPTIONAL_DEPTH"
    SOFT_CTA = "SOFT_CTA"
    BOOKING_COLLECT_NAME_AND_EMAIL = "BOOKING_COLLECT_NAME_AND_EMAIL"
    BOOKING_TIME_RANGE = "BOOKING_TIME_RANGE"
    BOOKING_PICK_SLOT = "BOOKING_PICK_SLOT"
    BOOKING_CONFIRM_BOOKING = "BOOKING_CONFIRM_BOOKING"
    WARM_CLOSE = "WARM_CLOSE"
    RECOVERY = "RECOVERY"
    END = "END"


class IntentType:
    UNKNOWN = "UNKNOWN"
    EXPLORER = "EXPLORER"
    HIRING = "HIRING"
    FOUNDER = "FOUNDER"


def _text(msg: llm.ChatMessage | None) -> str:
    """User text from the message; falls back to audio transcript when strings are not yet materialized."""
    if not msg:
        return ""
    direct = (msg.text_content or "").strip()
    if direct:
        return direct
    parts: list[str] = []
    for c in getattr(msg, "content", None) or []:
        if isinstance(c, str) and c.strip():
            parts.append(c.strip())
            continue
        tr = getattr(c, "transcript", None)
        if isinstance(tr, str) and tr.strip():
            parts.append(tr.strip())
    s = " ".join(parts).strip()
    if s:
        return s
    ex = getattr(msg, "extra", None)
    if isinstance(ex, dict):
        for k in ("transcript", "user_transcript", "text"):
            v = ex.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _user_text_for_turn(turn_ctx: llm.ChatContext, new_message: llm.ChatMessage | None) -> str:
    """Best-effort user line for routing; also reads context if the new message is not fully materialized."""
    t = _normalize_stt_text(_text(new_message)) if new_message else ""
    if t:
        return t
    for it in reversed(turn_ctx.items):
        if getattr(it, "type", None) == "message" and getattr(it, "role", None) == "user":
            t2 = _normalize_stt_text(_text(it))  # type: ignore[arg-type]
            if t2:
                return t2
    return ""


def _normalize_stt_text(s: str) -> str:
    """STT and clients may use curly apostrophes; normalize for reliable keyword and phrase checks."""
    if not s:
        return s
    return s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')


def _classify_intent(user_text: str) -> str:
    t = user_text.lower()
    if any(k in t for k in ("hiring", "interview", "role", "position", "candidate", "recruit")):
        return IntentType.HIRING
    if any(
        k in t
        for k in (
            "startup",
            "founder",
            "cofounder",
            "cto",
            "fundraising",
            "seed",
            "series",
            "building",
            "product",
            "users",
            "customers",
        )
    ):
        return IntentType.FOUNDER
    return IntentType.EXPLORER


def _is_depth_request(user_text: str) -> bool:
    t = user_text.lower()
    return any(
        k in t
        for k in (
            "details",
            "go deeper",
            "deep dive",
            "tell me more",
            "how does",
            "walk me through",
            "architecture",
            "design",
            "why",
            "approach",
            "thinking",
            "decision",
            "tradeoff",
            "trade-off",
        )
    )


def _expresses_confusion(user_text: str) -> bool:
    t = (user_text or "").lower()
    return any(
        k in t
        for k in (
            "don't understand",
            "do not understand",
            "confused",
            "what are you saying",
            "what do you mean",
            "not sure what you",
            "doesn't make sense",
            "does not make sense",
        )
    )


def _is_high_intent(user_text: str) -> bool:
    """Signals interest or next-step fit — not the same as stating 'we are hiring' (use \\b for hire)."""
    t = user_text.lower()
    if re.search(r"\bhire\b", t):
        return True
    if any(
        k in t
        for k in (
            "need someone",
            "this is interesting",
            "sounds like",
            "sounds good",
            "can he",
            "would he",
            "work together",
        )
    ):
        return True
    return bool(re.search(r"\bfit\b", t))


def _is_short_filler_utterance(user_text: str) -> bool:
    """Very short or backchannel phrasing: steer to RECOVERY instead of default VALUE."""
    t = (user_text or "").strip()
    if not t or len(t.split()) > 2:
        return False
    tl = t.lower()
    if _wants_end(tl) or _wants_booking(tl) or _is_depth_request(tl) or _is_high_intent(tl):
        return False
    if _classify_intent_short(tl) is not None:
        return False
    return True


def _classify_intent_short(t: str) -> str | None:
    """Strong 1-2 word signals so hiring/founder can be detected without turn-count gating."""
    if any(
        k in t
        for k in (
            "hiring",
            "hire",
            "interview",
            "recruit",
            "recruiter",
            "candidate",
        )
    ):
        return IntentType.HIRING
    if any(k in t for k in ("founder", "startup", "cofounder", "cto", "seed", "series")):
        return IntentType.FOUNDER
    return None


def _wants_end(user_text: str) -> bool:
    t = user_text.lower()
    return any(
        k in t
        for k in (
            "bye",
            "goodbye",
            "good bye",
            "end the call",
            "end this call",
            "end call",
            "hang up",
            "that's all",
            "that is all",
            "we are done",
            "we're done",
        )
    )


def _wants_booking(user_text: str) -> bool:
    t = user_text.lower()
    return any(k in t for k in ("book", "schedule", "set up a call", "calendly", "calendar", "meeting"))


def _build_memory_context(userdata: "BookingUserData") -> str | None:
    """Layer 3: optional, soft memory context (kept intentionally non-creepy)."""
    # Primary source: precomputed memory_hint, typically hydrated from long-term profile memory.
    if userdata.memory_hint:
        hint = userdata.memory_hint.strip()
        if hint:
            return (
                "Memory context (use lightly, with uncertainty hedges; never quote verbatim). "
                "Use this to shape tone and what you emphasize, not as a script.\n"
                f"- {hint}"
            )

    # Fallback: derive a very small amount of context from session-level fields.
    bits: list[str] = []

    # Intent: helpful for framing questions, but keep it soft.
    if getattr(userdata, "intent_type", IntentType.UNKNOWN) != IntentType.UNKNOWN:
        bits.append(
            "From earlier in the conversation, they seem to be this intent type "
            f"(not certain): {userdata.intent_type}."
        )

    # Booking history: only a light nudge, never pressure.
    if getattr(userdata, "booked_before", False):
        bits.append(
            "It looks like they may have booked a call with Mihir before. "
            "If you mention this, hedge with phrases like 'if I remember right' "
            "and do not be intense or salesy about it."
        )

    # Company/domain are high-value but optional; use only if present.
    company = getattr(userdata, "company", None)
    domain = getattr(userdata, "domain", None)
    if company or domain:
        detail_parts: list[str] = []
        if company:
            detail_parts.append(f"company: {company}")
        if domain:
            detail_parts.append(f"domain or area: {domain}")
        bits.append(
            "They have previously shared a bit about their background; "
            + ", ".join(detail_parts)
            + ". Use this only when directly relevant, and never quote past turns verbatim."
        )

    if not bits:
        return None

    return (
        "Memory context (use lightly, with uncertainty hedges; never quote verbatim). "
        "Use this to shape tone and what you emphasize, not as a script.\n"
        + "\n".join(f"- {b}" for b in bits)
    )


def _user_indicated_concrete_role_or_stack(user_text: str) -> bool:
    """True when the user has likely said enough for a direct founder reply without clarifying Q."""
    t = (user_text or "").lower()
    if len(t.split()) < 4:
        return False
    return any(
        k in t
        for k in (
            "backend",
            "systems",
            "engineer",
            "infrastructure",
            "infra",
            "devops",
            "sre",
            "full stack",
            "fullstack",
            "staff",
        )
    )


def _build_state_instruction(userdata: "BookingUserData", last_user_text: str = "") -> str:
    """Layer 2: per-turn instruction based on the current state."""
    base = (
        "HIGHEST PRIORITY FOR THIS TURN: If anything below conflicts with the general system persona, "
        "follow this block for this turn only.\n\n"
        "Voice output contract:\n"
        "- plain text only\n"
        "- 1 to 3 sentences by default\n"
        "- at most 1 question\n"
        "- calm, not salesy\n"
        "- no lists, markdown, emojis, or code\n"
    )

    state = userdata.state or ConversationState.DISCOVER_INTENT
    intent = userdata.intent_type or IntentType.UNKNOWN

    if state == ConversationState.DISCOVER_INTENT:
        if intent == IntentType.FOUNDER:
            return (
                f"You are in state: {state}. Intent: {intent}.\n"
                f"{base}\n"
                "Goal: They are a founder evaluating an engineer. Mihir is not a co-founder. "
                "Respond directly to what they are looking for or building first, then briefly "
                "connect Mihir's experience to that context. Do not force a generic introduction "
                "before addressing their need. Only ask what they're building or what problem "
                "they're solving if they have not yet indicated a role, stack, or problem area. "
                "CRITICAL: Do NOT ask for their name, email, or contact information. Do NOT call "
                "set_name, set_email, or any booking tools. Do NOT offer to schedule a call yet. "
                "Stay focused on fit and substance."
            )
        return (
            f"You are in state: {state}. Intent guess: {intent}.\n"
            f"{base}\n"
            "Goal for this turn: warmly discover why they're here. Ask one simple question if needed."
        )

    if state == ConversationState.VALUE_EXCHANGE:
        if intent == IntentType.FOUNDER:
            if _user_indicated_concrete_role_or_stack(last_user_text):
                return (
                    f"You are in state: {state}. Intent: {intent}.\n"
                    f"{base}\n"
                    "NON-NEGOTIABLE: You are Melvin. For Mihir's work use third person only (Mihir has, he builds) — never "
                    "'I have built' or 'I've worked' for his career; those imply you are Mihir. Do not end with a question. In two to three very short "
                    "sentences: acknowledge what they need or are building, then name how Mihir fits (backend/ "
                    "systems, Go or Python, ownership, shipping). No generic filler. "
                    "CRITICAL: No name, email, contact, or booking tools. No scheduling offer unless they "
                    "explicitly asked to book or meet."
                )
            return (
                f"You are in state: {state}. Intent: {intent}.\n"
                f"{base}\n"
                "NON-NEGOTIABLE: The first sentence MUST begin with the word 'Mihir' and state plainly that he is "
                "a hands-on engineer (backend/systems) or how he works; then you may add one specific question about "
                "what they are building or what 'technical help' means. Do not use 'I'd love' or a mirror-only opener. "
                "CRITICAL: No name, email, contact, or booking tools. No meeting offer unless they ask."
            )
        return (
            f"You are in state: {state}. Intent: {intent}.\n"
            f"{base}\n"
            "Goal for this turn: answer what was asked directly and concisely. "
            "Do NOT end with a question. Do NOT ask 'what else would you like to know?' or similar. "
            "Let the user steer. Respond, then wait."
        )

    if state == ConversationState.OPTIONAL_DEPTH:
        return (
            f"You are in state: {state}. Intent: {intent}.\n"
            f"{base}\n"
            "Goal for this turn: go deeper only on what they asked, avoid info-dumping, then check if that helps."
        )

    if state == ConversationState.SOFT_CTA:
        return (
            f"You are in state: {state}. Intent: {intent}.\n"
            f"{base}\n"
            "This state OVERRIDES any generic instruction to collect name and email. You are NOT in the "
            "booking collection step. FORBIDDEN in this state: any tool calls (set_name, set_email, "
            "get_available_slots, book_meeting, get_current_datetime). If they want to book formally, they should say book or schedule. "
            "Goal: mention a short call with Mihir as a possible next step, once, in a light way. "
            "Spoken only — do not collect PII, do not call any tools, do not ask for contact details, "
            "do not use phrasing that leads to name or email. "
            "Example: 'If you want to go deeper, a short call with Mihir is an option — just say the word.'"
        )

    if state == ConversationState.BOOKING_COLLECT_NAME_AND_EMAIL:
        return (
            f"You are in booking state: {state}. You do not have the user's name and email stored yet.\n"
            f"{base}\n"
            "CRITICAL: Do NOT call get_available_slots, book_meeting, or get_current_datetime in this turn. "
            "CRITICAL: Do NOT infer, guess, or make up names or emails. Only call set_name and set_email "
            "if the user's message explicitly contains both their full name AND email address. "
            "If the user has NOT provided both name and email in this message, do not call ANY tools; "
            "reply once and explain that names and addresses are hard to get right by voice alone, so they "
            "should TYPE their full name and email in the text or chat field (not only say them out loud). "
            "Ask them to put both on one or two lines so nothing is garbled. "
            "You must collect name and email BEFORE showing available slots. "
            "Always ask for BOTH name and email together in a single request."
        )

    if state == ConversationState.BOOKING_TIME_RANGE:
        return (
            f"You are in booking state: {state}.\n"
            f"{base}\n"
            "CRITICAL: Do NOT call get_available_slots or book_meeting in this turn. "
            "Your only job is to ask the user for a date range (or a couple days) and their timezone. "
            "Example: 'When would you like to meet? Do you have a date range in mind?' "
            "Wait for the user to provide a date range before calling get_available_slots."
        )

    if state == ConversationState.BOOKING_PICK_SLOT:
        return (
            f"You are in booking state: {state}.\n"
            f"{base}\n"
            "Goal for this turn: call get_available_slots for the range, then offer a few options simply."
        )

    if state == ConversationState.BOOKING_CONFIRM_BOOKING:
        return (
            f"You are in booking state: {state}.\n"
            f"{base}\n"
            "Goal for this turn: restate date/time/timezone and ask for final confirmation before calling book_meeting."
        )

    if state == ConversationState.WARM_CLOSE:
        return (
            f"You are in state: {state}.\n"
            f"{base}\n"
            "Goal for this turn: a clear closing — thank them, wish them well, or say a short line like you’re glad "
            "they stopped by. Add a light closing line (e.g. take care, all the best, looking forward to the call if "
            "relevant). Do not start new topics or push booking. Keep it 1-3 short sentences, calm and human."
        )

    if state == ConversationState.RECOVERY:
        return (
            f"You are in state: {state}.\n"
            f"{base}\n"
            "NON-NEGOTIABLE: The first four words of your reply MUST be exactly: 'Sorry if that was confusing' "
            "unless the user turn was empty or silent, in which case start with: 'I'm still here' then continue. "
            "After that, one plain sentence: Mihir is a hands-on backend and systems engineer, and you help explain his work. "
            "End with one concrete next option the listener can take — a topic, project, or kind of role fit. "
            "Do not skip the required opener above."
        )

    if state == ConversationState.END:
        return (
            f"You are in state: {state}.\n"
            f"{base}\n"
            "Goal for this turn: a final goodbye — short, warm, and conclusive. Thank them, say goodbye, or wish them a "
            "good day. Do not introduce new topics, questions, or booking. One to three brief sentences is enough."
        )

    return (
        f"You are in state: {state}. Intent: {intent}.\n"
        f"{base}\n"
        "Goal for this turn: keep it helpful, brief, and move the conversation forward."
    )


@dataclass
class BookingDetails:
    scheduled_time_utc_iso: str  # ISO UTC datetime of the meeting
    timezone: str                # IANA timezone for the attendee


@dataclass
class BookingUserData:
    """Stored profile for the current session (used when booking meetings)."""
    name: str | None = None
    email: str | None = None
    # Optional profile-style memory captured within the session. These may be
    # hydrated from / written back to long-term user profile storage.
    company: str | None = None
    domain: str | None = None
    booked_before: bool = False
    # Phase 3: explicit conversation state tracking
    state: str = ConversationState.GREETING
    intent_type: str = IntentType.UNKNOWN
    booking_offer_count: int = 0
    turn_count: int = 0
    # Phase 3 hook point for Phase 1 memory. Keep this soft & optional.
    memory_hint: str | None = None
    # Populated on successful booking for DB persistence.
    booking_details: BookingDetails | None = None


class PortfolioAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=PORTFOLIO_ASSISTANT_INSTRUCTIONS)
        self._end_requested: bool = False

    async def on_enter(self) -> None:
        # Phase 3: move initial greeting into the agent lifecycle hook.
        self.session.userdata.state = ConversationState.GREETING  # type: ignore[attr-defined]
        await self.session.generate_reply(
            instructions=(
                "You must output exactly the following text, word for word, with no additions, "
                "changes, or paraphrasing: Hi, I'm Melvin. I help explain Mihir's work and connect "
                "people with him. What brought you here today?"
            )
        )
        self.session.userdata.state = ConversationState.DISCOVER_INTENT  # type: ignore[attr-defined]

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        # Phase 3: lightweight routing to update state/intent, then inject Layer 2 + Layer 3.
        ud: BookingUserData = self.session.userdata  # type: ignore[assignment]
        user_text = _user_text_for_turn(turn_ctx, new_message)

        if user_text and _wants_end(user_text):
            ud.state = ConversationState.END
            self._end_requested = True

        ud.turn_count += 1

        if user_text:
            words = user_text.split()
            if len(words) >= 3:
                ud.intent_type = _classify_intent(user_text)
            else:
                short = _classify_intent_short(user_text.lower())
                if short is not None:
                    ud.intent_type = short

        # Do not change state once we've reached END.
        if ud.state == ConversationState.END:
            turn_ctx.add_message(
                role="developer", content=_build_state_instruction(ud, user_text)
            )
            mem = _build_memory_context(ud)
            if mem:
                turn_ctx.add_message(role="developer", content=mem)
            if self._end_requested:
                asyncio.create_task(self._close_after_delay())
            return

        # Booking takes precedence when user explicitly requests it.
        booking_states = {
            ConversationState.BOOKING_COLLECT_NAME_AND_EMAIL,
            ConversationState.BOOKING_TIME_RANGE,
            ConversationState.BOOKING_PICK_SLOT,
            ConversationState.BOOKING_CONFIRM_BOOKING,
        }

        if _wants_booking(user_text):
            if not ud.name or not ud.email:
                ud.state = ConversationState.BOOKING_COLLECT_NAME_AND_EMAIL
            elif ud.name and ud.email:
                # Only transition to TIME_RANGE if we have both name and email
                # This ensures we ask for time range in the NEXT turn after collecting email
                ud.state = ConversationState.BOOKING_TIME_RANGE
        else:
            # Keep booking substates sticky unless the user clearly abandons.
            if ud.state in booking_states:
                pass
            else:
                if not user_text:
                    ud.state = ConversationState.RECOVERY
                elif _expresses_confusion(user_text):
                    ud.state = ConversationState.RECOVERY
                elif _is_depth_request(user_text):
                    ud.state = ConversationState.OPTIONAL_DEPTH
                elif _is_short_filler_utterance(user_text):
                    ud.state = ConversationState.RECOVERY
                elif user_text and ud.intent_type == IntentType.HIRING:
                    ud.state = ConversationState.VALUE_EXCHANGE
                elif ud.state in (
                    ConversationState.GREETING,
                    ConversationState.DISCOVER_INTENT,
                ) and ud.turn_count <= 1:
                    ud.state = ConversationState.DISCOVER_INTENT
                else:
                    ud.state = ConversationState.VALUE_EXCHANGE

                # Soft CTA: when the user shows clear interest or alignment, once — not time-based.
                if (
                    user_text
                    and _is_high_intent(user_text)
                    and ud.booking_offer_count < 1
                    and ud.intent_type != IntentType.FOUNDER
                    and ud.state
                    in (
                        ConversationState.DISCOVER_INTENT,
                        ConversationState.VALUE_EXCHANGE,
                        ConversationState.OPTIONAL_DEPTH,
                    )
                ):
                    ud.state = ConversationState.SOFT_CTA
                    ud.booking_offer_count += 1

        # Layer 2: state instruction (developer message, ephemeral for this turn)
        turn_ctx.add_message(role="developer", content=_build_state_instruction(ud, user_text))

        # Layer 3: memory context (developer message, ephemeral)
        mem = _build_memory_context(ud)
        if mem:
            turn_ctx.add_message(role="developer", content=mem)

    async def _close_after_delay(self, delay: float = 1.0) -> None:
        await asyncio.sleep(delay)
        try:
            await self.session.aclose()
        except Exception as e:
            logger.warning("PortfolioAssistant: failed to close session: %s", e)

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
        description="Call this ONLY when the user has explicitly provided their full name in their text or message (ideally typed). Do NOT infer or guess names. Store it for the booking.",
    )
    async def set_name(self, context: RunContext[BookingUserData], value: str) -> str:
        """Store the user's name. Call ONLY when the user gave their full name in what they wrote or said—prefer typed text for accuracy.
        Args:
            value: The full name the user provided. Do NOT infer or make up names.
        """
        context.userdata.name = value.strip()
        result = f"Got it, I have your name as {context.userdata.name}."
        logger.info("set_name: value=%s -> result=%s", value, result)
        return result

    @function_tool(
        name="set_email",
        description="Call this ONLY when the user has explicitly provided their email in their text or message (ideally typed). Do NOT infer or guess emails. Store it for the booking.",
    )
    async def set_email(self, context: RunContext[BookingUserData], value: str) -> str:
        """Store the user's email. Call ONLY when the user gave their email in what they wrote or said—prefer typed text.
        Args:
            value: The email the user provided. Do NOT infer or make up emails.
        """
        context.userdata.email = value.strip()
        if context.userdata.state == ConversationState.BOOKING_COLLECT_NAME_AND_EMAIL:
            # Transition to TIME_RANGE so next turn asks for time range
            context.userdata.state = ConversationState.BOOKING_TIME_RANGE
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
        """Get available meeting slots from Cal.com for a date range. Only call this AFTER you have collected the user's name and email. Do not call this if you are in BOOKING_COLLECT_NAME_AND_EMAIL state. Call this when the user wants to book a meeting and you already have their name and email, so you can tell them which times are free before they choose.
        Args:
            start_date: Start of range in YYYY-MM-DD format (e.g. 2025-02-10).
            end_date: End of range in YYYY-MM-DD format (e.g. 2025-02-16).
            timezone: IANA timezone for the user (e.g. Asia/Kolkata for India). Use Asia/Kolkata if user is in India or timezone unknown.
        """
        try:
            result = await calcom_get_available_slots(
                start_date=start_date,
                end_date=end_date,
                timezone=timezone,
            )
            logger.info(
                "get_available_slots: start_date=%s end_date=%s timezone=%s -> result=%s",
                start_date,
                end_date,
                timezone,
                result,
            )
            return result
        except Exception as e:  # pragma: no cover - defensive, should be rare
            # Phase 4: error-safe behavior. The tool should never crash the agent;
            # instead, return guidance that leads to a calm, single apology and a fallback.
            logger.warning("get_available_slots: cal.com error: %s", e, exc_info=True)
            return (
                "ERROR: get_available_slots failed due to a booking system or configuration issue. "
                "When you respond to the user, briefly apologize once, explain that the booking "
                "system is having trouble, and offer a simple fallback like suggesting a couple "
                "of days and times they can mention, or letting them follow up over email instead."
            )

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
        try:
            result = await calcom_book_meeting(
                attendee_name=name,
                attendee_email=email,
                date=date,
                time_slot=time_slot,
                timezone=timezone,
                notes=notes or None,
            )
        except Exception as e:  # pragma: no cover - defensive, should be rare
            # Phase 4: error-safe behavior for booking failures.
            logger.warning("book_meeting: cal.com error: %s", e, exc_info=True)
            return (
                "ERROR: book_meeting failed due to a booking system or configuration issue. "
                "When you respond to the user, apologize once, explain that the calendar system "
                "is not responding correctly, and suggest a clear fallback such as sharing a "
                "preferred time window or following up via email instead of booking live."
            )

        # Booking succeeded/failed is expressed in the underlying tool's message.
        # Detect clear success to update memory + state.
        if "Meeting booked successfully" in (result or ""):
            context.userdata.booked_before = True
            context.userdata.state = ConversationState.WARM_CLOSE
            try:
                utc_iso = _build_start_utc_iso(date, time_slot, timezone)
                context.userdata.booking_details = BookingDetails(
                    scheduled_time_utc_iso=utc_iso,
                    timezone=timezone,
                )
            except Exception as e:
                logger.warning("book_meeting: could not build BookingDetails: %s", e)
        else:
            # Even when booking fails, do not loop endlessly in booking states.
            # Let the assistant move toward a warm close or alternative suggestion.
            context.userdata.state = ConversationState.WARM_CLOSE

        logger.info(
            "book_meeting: attendee=%s date=%s time_slot=%s -> result=%s",
            name,
            date,
            time_slot,
            result,
        )
        return result