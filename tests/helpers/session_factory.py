"""Test helper: factory to start AgentSession with PortfolioAssistant and optional judge LLM.

Supports two modes:
- offline mode: deterministic assertions only (no LLM judge)
- eval mode: enables judge() when an API key is available (GROQ_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY)

Provider priority (for BOTH session and judge LLMs):
1. GROQ_API_KEY (if set) -> uses groq.LLM
2. GOOGLE_API_KEY (if set) -> uses google.LLM
3. OPENAI_API_KEY (if set) -> uses openai.responses.LLM

Env loading:
- Mirrors src/main.py by loading .env.local if present, so tests see the same keys
  as the running agent server (e.g. GOOGLE_API_KEY for Gemini).
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from livekit.agents import AgentSession, llm as llm_module

from src.agents.protfolio_agent import BookingUserData, PortfolioAssistant

# Load local env the same way src/main.py does, so tests pick up GEMINI / GROQ / OPENAI keys.
if os.path.exists(".env.local"):
    load_dotenv(".env.local")


def _get_judge_provider() -> str | None:
    """Detect which LLM provider API key is available.

    Returns:
        Provider name: "groq", "google", "openai", or None if no key found.
    """
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    # Prefer explicit GOOGLE_API_KEY for Gemini; also allow Vertex via GOOGLE_APPLICATION_CREDENTIALS
    if os.getenv("GOOGLE_API_KEY"):
        return "google"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None


def _is_eval_mode() -> bool:
    """Check if eval mode is enabled (requires any LLM API key)."""
    return _get_judge_provider() is not None


@asynccontextmanager
async def create_test_session(
    userdata: BookingUserData | None = None,
) -> AsyncIterator[AgentSession]:
    """Create an AgentSession for testing with PortfolioAssistant.

    Args:
        userdata: Optional BookingUserData to initialize the session with.
                  If None, creates a fresh BookingUserData instance.

    Yields:
        AgentSession configured with PortfolioAssistant and a test LLM.
    """
    provider = _get_judge_provider()

    # If no API key at all, we could still theoretically run with a dummy model,
    # but for now require at least one provider for behavioral tests.
    if not provider:
        raise RuntimeError(
            "No LLM API key found for tests. Set one of GROQ_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY."
        )

    if provider == "groq":
        from livekit.plugins import groq

        async with groq.LLM(model="openai/gpt-oss-20b") as llm:
            async with AgentSession(
                llm=llm, userdata=userdata or BookingUserData()
            ) as session:
                await session.start(PortfolioAssistant())
                yield session
    elif provider == "google":
        from livekit.plugins import google

        async with google.LLM(model="gemini-2.5-flash") as llm:
            async with AgentSession(
                llm=llm, userdata=userdata or BookingUserData()
            ) as session:
                await session.start(PortfolioAssistant())
                yield session
    elif provider == "openai":
        from livekit.plugins import openai

        async with openai.responses.LLM(model="gpt-4o-mini") as llm:
            async with AgentSession(
                llm=llm, userdata=userdata or BookingUserData()
            ) as session:
                await session.start(PortfolioAssistant())
                yield session
    else:
        raise RuntimeError(f"Unknown LLM provider in tests: {provider!r}")


@asynccontextmanager
async def create_judge_llm() -> AsyncIterator[llm_module.LLM | None]:
    """Create an LLM instance for judge() evaluations, if eval mode is enabled.

    Supports multiple providers (priority order):
    - GROQ_API_KEY -> uses groq.LLM with llama-3.3-70b-versatile
    - GOOGLE_API_KEY -> uses google.LLM with gemini-1.5-flash
    - OPENAI_API_KEY -> uses openai.responses.LLM with gpt-4o-mini

    Yields:
        LLM instance if eval mode is enabled (API key present), None otherwise.
    """
    provider = _get_judge_provider()
    if not provider:
        yield None
        return

    if provider == "groq":
        try:
            from livekit.plugins import groq

            async with groq.LLM(
                model="llama-3.3-70b-versatile", temperature=0
            ) as llm:
                yield llm
        except ImportError:
            raise ImportError(
                "GROQ plugin not installed. Install with: uv add 'livekit-agents[groq]~=1.3'"
            )
    elif provider == "google":
        try:
            from livekit.plugins import google

            async with google.LLM(
                model="gemini-2.5-flash", temperature=0
            ) as llm:
                yield llm
        except ImportError:
            raise ImportError(
                "Google plugin not installed. Install with: uv add 'livekit-agents[google]~=1.3'"
            )
    elif provider == "openai":
        try:
            from livekit.plugins import openai

            async with openai.responses.LLM(
                model="gpt-4o-mini", temperature=0
            ) as llm:
                yield llm
        except ImportError:
            raise ImportError(
                "OpenAI plugin not installed. Install with: uv add 'livekit-agents[openai]~=1.3'"
            )
    else:
        yield None


def skip_if_no_judge() -> bool:
    """Check if judge LLM is available (for pytest.mark.skipif)."""
    return not _is_eval_mode()
