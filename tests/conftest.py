"""Pytest configuration and fixtures for voice UX tests.

Includes rate limiting support for Groq free tier (8000 TPM limit).
"""
import asyncio
import os
from typing import Generator

import pytest

from dotenv import load_dotenv

# Load .env.local if present (same as main.py and session_factory)
if os.path.exists(".env.local"):
    load_dotenv(".env.local")


def _is_using_groq() -> bool:
    """Check if tests are using Groq API (free tier has 8000 TPM limit)."""
    return bool(os.getenv("GROQ_API_KEY"))


def _get_groq_delay_seconds() -> float:
    """Get delay between tests when using Groq (to avoid rate limits).

    Default: 3.0 seconds (conservative for Groq free tier 8000 TPM limit).
    Override via GROQ_TEST_DELAY_SECONDS env var (set to 0 to disable delay).

    Rationale:
    - Groq free tier: 8000 TPM (tokens per minute)
    - Each test uses multiple LLM calls (session + judge); spacing them out
      avoids bursting past the limit. 3s between tests keeps usage well under 8000 TPM.
    """
    delay_str = os.getenv("GROQ_TEST_DELAY_SECONDS", "5.0")
    try:
        return max(0.0, float(delay_str))
    except ValueError:
        return 3.0


@pytest.fixture(autouse=True)
def groq_rate_limit_delay() -> Generator[None, None, None]:
    """Add delay between tests when using Groq to avoid rate limits.

    This fixture runs automatically after each test (autouse=True).
    Only adds delay if GROQ_API_KEY is set.
    """
    yield  # Run the test first

    # After test completes, add delay if using Groq (free tier 8000 TPM limit)
    if _is_using_groq():
        delay = _get_groq_delay_seconds()
        if delay > 0:
            import time
            time.sleep(delay)
