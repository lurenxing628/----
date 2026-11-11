"""Initialize an empty scheduling configuration before read-only workbench requests."""

import logging
import sqlite3

from core.infrastructure.transaction import TransactionManager
from core.services.scheduler.config.config_field_spec import list_config_fields
from data.repositories.config_repo import ConfigRepository


def bootstrap_schedule_config(conn: sqlite3.Connection, logger: logging.Logger) -> None:
    repo = ConfigRepository(conn, logger=logger)
    with TransactionManager(conn).transaction(begin_immediate=True):
        if repo.count_all():
            return
        defaults = [(spec.key, str(spec.default), spec.description) for spec in list_config_fields()]
        repo.set_batch(defaults)
