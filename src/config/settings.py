from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

# Only load .env.local in local development
if os.path.exists(".env.local"):
    load_dotenv(".env.local")

def get_env(key: str, default: str | None = None) -> str | None:
    """Get environment variable."""
    return os.environ.get(key, default)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    LIVEKIT_URL: str
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    # Cal.com integration (https://cal.com/docs/api-reference/v2)
    CALCOM_API_KEY: str | None = get_env("CALCOM_API_KEY")
    CALCOM_EVENT_TYPE_ID: str | None = get_env("CALCOM_EVENT_TYPE_ID")
    CALCOM_BASE_URL: str = get_env("CALCOM_BASE_URL") or "https://api.cal.com/v2"
    CALCOM_API_VERSION: str = get_env("CALCOM_API_VERSION") or "2024-09-04"  # for GET /slots
    CALCOM_BOOKING_API_VERSION: str = get_env("CALCOM_BOOKING_API_VERSION") or "2024-08-13"  # for POST /bookings
    CALCOM_MEETING_LENGTH_MINUTES: int = 15  # 15 min meeting (match your event type)

    DEEPGRAM_API_KEY: str | None = get_env("DEEPGRAM_API_KEY")
    OPENAI_API_KEY: str | None = get_env("OPENAI_API_KEY")
    CARTESIA_API_KEY: str | None = get_env("CARTESIA_API_KEY")

    # Database (Postgres); e.g. postgresql+psycopg://user:pass@localhost:5432/voice_portfolio
    DATABASE_URL: str | None = get_env("DATABASE_URL")

    # R2 / S3-compatible object storage (e.g. Cloudflare R2)
    R2_ENDPOINT: str | None = get_env("R2_ENDPOINT")
    R2_BUCKET: str | None = get_env("R2_BUCKET")
    R2_ACCESS_KEY_ID: str | None = get_env("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY: str | None = get_env("R2_SECRET_ACCESS_KEY")

settings = Settings()
