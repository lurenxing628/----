"""Initialize an empty scheduling configuration before read-only workbench requests."""

from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.services.scheduler.config.config_constants import (
    ACTIVE_PRESET_KEY,
    ACTIVE_PRESET_META_KEY,
    ACTIVE_PRESET_REASON_KEY,
    BUILTIN_PRESET_DEFAULT,
)
from core.services.scheduler.config.config_field_spec import list_config_fields
from data.repositories.config_repo import ConfigRepository


def bootstrap_schedule_config(database_path: str, *, logger=None) -> None:
    conn = get_connection(database_path)
    try:
        repo = ConfigRepository(conn, logger=logger)
        with TransactionManager(conn).transaction(begin_immediate=True):
            if repo.count_all():
                return
            # Existing configurations and historical preset rows keep their saved values.
            defaults = [(spec.key, str(spec.default), spec.description) for spec in list_config_fields()]
            repo.set_batch(defaults + [
                (ACTIVE_PRESET_KEY, BUILTIN_PRESET_DEFAULT, "当前启用排产配置模板"),
                (ACTIVE_PRESET_REASON_KEY, "", "当前启用排产配置模板的状态说明"),
                (ACTIVE_PRESET_META_KEY, "", "当前启用排产配置模板的结构化来源记录"),
            ])
    finally:
        conn.close()
