"""DDL is an explicit release operation, never an API startup side effect."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from juya_api import models  # noqa: F401
from juya_api.database import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = os.environ.get("JUYA_MIGRATION_DATABASE_URL") or os.environ["JUYA_DATABASE_URL"]

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url, poolclass=pool.NullPool).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
