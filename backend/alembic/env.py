"""
Alembic environment configuration.
Imports Base and all ORM models so migrations cover all tables.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Add project root to sys.path ──────────────────────────────────────────────
# env.py lives at backend/alembic/env.py
# We need 'backend/' on the path so `from app.xxx import ...` works.
_alembic_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_alembic_dir)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# ── Import Base and all models ────────────────────────────────────────────────
from app.database import Base  # noqa: E402
import app.models  # noqa: E402, F401 — Phase 1 models
import app.models_v2  # noqa: E402, F401 — Phase 2 models

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Pull the database URL from the app's config if not set in alembic.ini
if not config.get_main_option("sqlalchemy.url", None):
    from app.config import settings
    config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (without a live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with a live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
