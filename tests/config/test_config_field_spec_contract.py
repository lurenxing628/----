"""配置快照读取与缺失配置拒绝。"""

from __future__ import annotations

import pytest

from core.errors import ValidationError
from core.infrastructure.database import ensure_schema, get_connection
from core.services.scheduler import ConfigService
from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


class _EmptyRepo:
    def get_value(self, key, default=None):
        return default


@pytest.fixture()
def config_service(tmp_path):
    test_db = tmp_path / "aps_config_field_spec.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    try:
        yield ConfigService(conn, logger=None, op_logger=None)
    finally:
        conn.close()


def test_config_service_snapshot_includes_hidden_field_and_get_stays_single_arg(config_service: ConfigService) -> None:
    config_service.ensure_defaults()

    snap = config_service.get_snapshot()
    assert snap.auto_assign_persist == "yes"
    assert snap.to_dict()["auto_assign_persist"] == "yes"
    assert snap.graph_analysis_mode == "on"
    assert snap.graph_block_on_cycle == "no"
    assert snap.graph_critical_weight == 500
    assert snap.graph_impact_weight == 10
    assert snap.graph_candidate_weight_count == 5
    assert snap.graph_selection_policy == "balanced"
    assert snap.graph_overdue_tolerance_count == 1
    assert snap.graph_tardiness_tolerance_ratio == 0.10
    assert snap.graph_debug_export == "no"
    assert config_service.get("objective") == "min_overdue"
    assert snap.graph_analysis_mode == "on"
    assert snap.to_dict()["graph_critical_weight"] == 500
    with pytest.raises(TypeError):
        config_service.get("objective", "fallback")


def test_build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_schedule_config_snapshot(_EmptyRepo(), strict_mode=True)

    assert exc_info.value.field == "sort_strategy"
