"""Initialize an empty scheduling configuration before read-only workbench requests."""

from core.infrastructure.database import get_connection
from core.services.scheduler.config.config_service import ConfigService


def bootstrap_schedule_config(database_path: str, *, logger=None) -> None:
    conn = get_connection(database_path)
    try:
        service = ConfigService(conn, logger=logger)
        # Defaults, presets and their provenance form one startup transaction.
        # Existing partial or invalid configurations remain available for strict validation.
        with service.tx_manager.transaction(begin_immediate=True):
            service.ensure_defaults_if_pristine()
    finally:
        conn.close()
