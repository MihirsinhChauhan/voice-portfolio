# Voice UX Test Suite

This directory contains behavioral tests and evaluations for the voice portfolio agent, implementing Phase 6 of the voice UX plan.

## Test Structure

- **`helpers/session_factory.py`**: Test infrastructure
  - Factory to create `AgentSession` with `PortfolioAssistant`
  - Optional judge LLM for qualitative evaluations
  - Environment-aware (offline vs eval mode)

- **`test_voice_ux_flows.py`**: Flow coverage tests (Phase 6B)
  - Warm Entry
  - Intent Discovery (Explorer, Hiring, Founder, FastBook)
  - Value Exchange
  - Optional Depth
  - Soft CTA
  - Booking deterministic flow

- **`test_voice_ux_edge_cases.py`**: Edge case tests (Phase 6C)
  - Silence / empty transcript
  - Confusion handling
  - Interruption acknowledgment
  - "Just testing" scenarios

- **`test_voice_ux_error_handling.py`**: Error-handling tests (Phase 6D)
  - Cal.com unavailable / 500 errors
  - No slots available
  - Invalid date/time inputs
  - Booking failures
  - Missing Cal.com config

## Running Tests

### Prerequisites

Install test dependencies:
```bash
uv sync
```

### Offline Mode (Deterministic Assertions Only)

Run tests without LLM judge (faster, no API costs):
```bash
uv run pytest tests/
```

This mode:
- ✅ Tests tool call order and arguments
- ✅ Tests state transitions
- ✅ Tests error message formats
- ❌ Skips `judge()` evaluations (requires `OPENAI_API_KEY`)

### Eval Mode (With LLM Judge)

Run tests with qualitative evaluations using any supported provider:

**Using GROQ:**
```bash
export GROQ_API_KEY=your_key_here
uv run pytest tests/
```

**Groq free tier (8000 TPM):** A delay runs automatically between tests when `GROQ_API_KEY` is set so you stay under the rate limit. Default is 3 seconds. Override with:
```bash
# Slower (safer for free tier)
export GROQ_TEST_DELAY_SECONDS=5
# No delay (e.g. paid tier)
export GROQ_TEST_DELAY_SECONDS=0
```

**Using Google Gemini:**
```bash
export GEMINI_API_KEY=your_key_here
uv run pytest tests/
```

**Using OpenAI:**
```bash
export OPENAI_API_KEY=your_key_here
uv run pytest tests/
```

This mode:
- ✅ All offline mode tests
- ✅ Plus qualitative `judge()` checks for message intent, tone, and behavior
- Automatically selects provider based on available API keys (GROQ > Gemini > OpenAI)

### Verbose Output

To see detailed execution traces:
```bash
LIVEKIT_EVALS_VERBOSE=1 uv run pytest -s tests/
```

### Running Specific Test Files

```bash
# Flow tests only
uv run pytest tests/test_voice_ux_flows.py

# Error handling only
uv run pytest tests/test_voice_ux_error_handling.py

# Edge cases only
uv run pytest tests/test_voice_ux_edge_cases.py
```

### Running Specific Tests

```bash
# Single test
uv run pytest tests/test_voice_ux_flows.py::test_warm_entry_greeting

# Tests matching a pattern
uv run pytest -k "booking" tests/
```

## Test Modes

### Offline Mode
- No API keys required
- Tests deterministic behavior (tool calls, state, error messages)
- Fast and free
- Use for CI/CD when API keys aren't available

### Eval Mode
- Requires one of: `GROQ_API_KEY`, `GOOGLE_API_KEY`, or `OPENAI_API_KEY`
- Adds qualitative `judge()` evaluations
- Tests intent, tone, and behavioral correctness
- Slower and incurs API costs
- Use for comprehensive validation and debugging

**Provider Priority:**
1. `GROQ_API_KEY` → uses Groq LLM (llama-3.3-70b-versatile)
2. `GOOGLE_API_KEY` → uses Google Gemini LLM (gemini-1.5-flash)
3. `OPENAI_API_KEY` → uses OpenAI LLM (gpt-4o-mini)

**Installing Provider Plugins:**

```bash
# For GROQ support
uv add "livekit-agents[groq]~=1.3"

# For Google Gemini support
uv add "livekit-agents[google]~=1.3"

# For OpenAI support (usually already included)
uv add "livekit-agents[openai]~=1.3"
```

The test helper will automatically detect which API key is available and use the corresponding provider. If multiple keys are set, GROQ takes precedence, then Gemini, then OpenAI.

### Rate limiting (Groq free tier, 8000 TPM)

When `GROQ_API_KEY` is set, an **automatic delay** runs **between each test** so you stay under the 8000 tokens-per-minute limit. Configure it with:

| Env var | Default | Description |
|--------|--------|-------------|
| `GROQ_TEST_DELAY_SECONDS` | `3.0` | Seconds to wait after each test. Set to `0` to disable (e.g. paid tier). |

Example: use a 5-second delay for extra headroom:
```bash
export GROQ_API_KEY=your_key
export GROQ_TEST_DELAY_SECONDS=5
uv run pytest tests/
```

## Writing New Tests

### Basic Test Template

```python
import pytest
from tests.helpers.session_factory import create_judge_llm, create_test_session

@pytest.mark.asyncio
async def test_your_scenario() -> None:
    async with create_test_session() as session, create_judge_llm() as judge_llm:
        # Run conversation turns
        result = await session.run(user_input="Hello")

        # Assert deterministic behavior
        result.expect.next_event().is_message(role="assistant")
        result.expect.no_more_events()

        # Optional: qualitative evaluation
        if judge_llm:
            await result.expect[0].is_message(role="assistant").judge(
                judge_llm,
                intent="Should do X and Y.",
            )
```

### Mocking Tools

Use `mock_tools` to simulate tool failures or custom responses:

```python
from livekit.agents import mock_tools
from src.agents.protfolio_agent import PortfolioAssistant

def mock_get_available_slots(start_date: str, end_date: str, timezone: str) -> str:
    return "No available slots."

with mock_tools(PortfolioAssistant, {"get_available_slots": mock_get_available_slots}):
    result = await session.run(user_input="Book a call")
    # Test error handling...
```

## CI Integration

Tests are designed to run in CI with or without API keys:

- **Without API keys**: Runs offline mode tests (deterministic assertions)
- **With API keys**: Runs full eval mode (includes qualitative checks)

Set one of the following as a CI secret to enable eval mode:
- `GROQ_API_KEY` (recommended for cost-effectiveness)
- `GOOGLE_API_KEY` (alternative option)
- `OPENAI_API_KEY` (fallback option)

The test helper automatically selects the provider based on which key is available.

## Next Steps (Phase 7)

- Add CI workflow (GitHub Actions or equivalent)
- Configure secrets for eval mode in CI
- Set up test result reporting
