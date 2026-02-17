"""
Alembic migration environment.
Uses DATABASE_URL from environment (e.g. .env.local). Run from project root: uv run alembic upgrade head
"""
from logging.config import fileConfig

# Load .env.local so DATABASE_URL is available when running alembic CLI
try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
except ImportError:
    pass

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import our models so that Base.metadata has all tables for autogenerate
from src.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Prefer DATABASE_URL from environment (e.g. pydantic-settings / .env.local)."""
    import os
    url = os.environ.get("DATABASE_URL")
    if url:
        # Some providers use postgres://; SQLAlchemy expects postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return config.get_main_option("sqlalchemy.url", "postgresql://localhost/voice_portfolio")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL only)."""
    url = get_url()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to DB)."""
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
