# Voice portfolio (Melvin)

LiveKit-based voice agent (“Melvin”) for Mihir’s portfolio: STT, LLM, TTS, Cal.com booking, and optional post-session storage (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

## Prerequisites

- Python 3.11+ ([`pyproject.toml`](pyproject.toml))
- [uv](https://github.com/astral-sh/uv) (recommended; used in this repo for tests and Alembic)

## Install

From the project root:

```bash
uv sync
```

## Environment variables

1. Create a file named **`.env.local`** in the project root. The app loads it automatically when it exists ([`src/main.py`](src/main.py), [`src/config/settings.py`](src/config/settings.py)).
2. **Do not commit** `.env.local` (it is listed in [`.gitignore`](.gitignore)). You can copy from [`.env.example`](.env.example) and fill in real values.
3. Full keys are also declared in code in [`src/config/settings.py`](src/config/settings.py).

### Table

| Variable | Required? | Purpose |
|----------|------------|---------|
| `LIVEKIT_URL` | **Yes** | WebSocket URL of your LiveKit server (e.g. from LiveKit Cloud). |
| `LIVEKIT_API_KEY` | **Yes** | Project API key (LiveKit Cloud dashboard or self‑hosted). |
| `LIVEKIT_API_SECRET` | **Yes** | Project API secret, paired with the key. |
| `OPENAI_API_KEY` | For default LLM | Used for `openai/gpt-4.1-mini` in [`src/hooks/session.py`](src/hooks/session.py). |
| `DEEPGRAM_API_KEY` | For default STT | Used for `deepgram/nova-3:multi`. |
| `INWORLD_API_KEY` | For default TTS | Inworld TTS via LiveKit; key read by the [Inworld plugin](https://docs.livekit.io/reference/python/livekit/plugins/inworld/index.html) (often base64-encoded per provider docs). |
| `CALCOM_API_KEY` | For booking | Cal.com API; required when calling slot/booking tools. |
| `CALCOM_EVENT_TYPE_ID` | For booking | Event type to book. |
| `CALCOM_BASE_URL` | Optional | Defaults to `https://api.cal.com/v2` in settings. |
| `CALCOM_API_VERSION` | Optional | Header for slot API (default `2024-09-04`). |
| `CALCOM_BOOKING_API_VERSION` | Optional | Header for bookings API (default `2024-08-13`). |
| `CARTESIA_API_KEY` | Optional | In settings but not the current TTS in `session.py` (if you switch TTS provider). |
| `DATABASE_URL` | Optional | Postgres URL for user/session data and analysis pipeline, e.g. `postgresql+psycopg://postgres:postgres@localhost:5432/voice_portfolio` when using the bundled Compose stack. |
| `R2_ENDPOINT` | Optional | S3‑compatible endpoint (e.g. Cloudflare R2) for session artifacts. |
| `R2_BUCKET` | Optional | Bucket name. |
| `R2_ACCESS_KEY_ID` | Optional | R2 / S3 access key. |
| `R2_SECRET_ACCESS_KEY` | Optional | R2 / S3 secret key. |

**Notes**

- Pydantic `Settings` in [`src/config/settings.py`](src/config/settings.py) **requires** `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` at import time in many code paths. Provider keys (OpenAI, Deepgram, Inworld) are what the [LiveKit Agents](https://docs.livekit.io/agents/) stack expects in the environment for the configured `stt` / `llm` / `tts` string IDs.
- Cal.com calls fail with a clear error if `CALCOM_API_KEY` and `CALCOM_EVENT_TYPE_ID` are missing (see `cal_com_booking._require_calcom_config`).

## Run the agent

The process is a **LiveKit agent worker**; register it with the same project as your [LiveKit Cloud](https://cloud.livekit.io/) or self-hosted server. See the [LiveKit Agents docs](https://docs.livekit.io/agents/) for worker deployment and dispatch.

From the project root:

```bash
uv run python src/main.py dev
```

| Mode | Description |
|------|-------------|
| `dev` | Hot reload and verbose logs. |
| `start` | Production-style agent run. |
| `console` | Console / local agent run (see LiveKit CLI help). |

Omit the argument to use the default (`start`).

**Local database (optional, for analysis pipeline / migrations):**

```bash
docker compose up -d
```

Then, with `DATABASE_URL` set, from project root:

```bash
uv run alembic upgrade head
```

(Comments in [`alembic.ini`](alembic.ini) and [`src/db/migrations/env.py`](src/db/migrations/env.py) assume this workflow.)

## Tests

See [tests/README.md](tests/README.md), for example:

```bash
uv run pytest tests/
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — high-level system, agent orchestration, voice UX vs code, conversation state, session capture, related links.
- [implementations/PRD.md](implementations/PRD.md) — conversation analysis / session reporting product scope.
- [implementations/pipeline.md](implementations/pipeline.md) — offline analysis pipeline stages.
- [implementations/voice_ux.md](implementations/voice_ux.md) — product voice UX, ideal state diagram, edge cases.
