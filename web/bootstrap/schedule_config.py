"""Initialize an empty scheduling configuration before read-only workbench requests."""

import logging

from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.services.scheduler.config.config_field_spec import list_config_fields
from data.repositories.config_repo import ConfigRepository


def bootstrap_schedule_config(database_path: str, *, logger: logging.Logger) -> None:
    conn = get_connection(database_path)
    try:
        repo = ConfigRepository(conn, logger=logger)
        with TransactionManager(conn).transaction(begin_immediate=True):
            if repo.count_all():
                return
            defaults = [(spec.key, str(spec.default), spec.description) for spec in list_config_fields()]
            repo.set_batch(defaults)
    finally:
        conn.close()
