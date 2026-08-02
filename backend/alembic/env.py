import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Registers every model on Base.metadata (see target_metadata below) purely
# via import side effect - nothing here references the module directly.
import app.models  # noqa: F401
from alembic import context
from app.db.session import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# alembic.ini's sqlalchemy.url is a hardcoded localhost:5432 connection
# string - correct only when alembic runs directly on a developer's host,
# where the local dev Postgres really is reachable at localhost. Inside a
# container (see backend/Dockerfile, run as part of the image's startup
# command), Postgres is a separate service reachable by its compose service
# name, not localhost - DATABASE_URL (already required by Settings, see
# app/core/config.py) is the same value the application itself connects
# with, so alembic overriding its own static default with it when present
# keeps both environments working from the one file, with no separate
# alembic-specific configuration to keep in sync.
if database_url := os.environ.get("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", database_url)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
