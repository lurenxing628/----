"""配置快照读取与缺失配置拒绝。"""

from __future__ import annotations

import json

import pytest

from core.errors import ValidationError
from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_config_runtime import ensure_schedule_config_snapshot
from core.models.schedule_config_runtime_fields import RETIRED_CONFIG_FIELDS, list_runtime_config_fields
from core.services.scheduler import ConfigService
from core.services.scheduler.config.config_field_spec import list_config_fields
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
    assert snap.time_budget_seconds == ConfigService.DEFAULT_TIME_BUDGET_SECONDS == 10
    runtime_keys = {spec.key for spec in list_runtime_config_fields()}
    page_keys = {spec.key for spec in list_config_fields()}
    for key in RETIRED_CONFIG_FIELDS:
        assert not hasattr(snap, key) and key not in snap.to_dict()
        assert key not in runtime_keys and key not in page_keys and key not in ConfigService.CONFIG_PAGE_WRITE_FIELDS
    assert snap.graph_debug_export == "no"
    assert config_service.get("objective") == "min_overdue"
    assert snap.graph_analysis_mode == "on"
    assert snap.to_dict()["graph_critical_weight"] == 500
    with pytest.raises(TypeError):
        config_service.get("objective", "fallback")


def test_legacy_preset_keeps_budget_and_retired_page_fields_reject_before_writes(config_service: ConfigService) -> None:
    service = config_service
    rows_before = [tuple(row) for row in service.conn.execute("SELECT * FROM ScheduleConfig ORDER BY config_key")]
    for key in RETIRED_CONFIG_FIELDS:
        with pytest.raises(ValidationError) as rejected:
            service.save_page_config({key: None})
        assert rejected.value.field == key
        assert rejected.value.message == "固定图权重档已经取消，请刷新设置页面后重试。"
        assert [tuple(row) for row in service.conn.execute("SELECT * FROM ScheduleConfig ORDER BY config_key")] == rows_before

    service.ensure_defaults()
    builtins = {name: snapshot.time_budget_seconds for name, snapshot, _description in service._builtin_presets()}
    assert builtins == {service.BUILTIN_PRESET_DEFAULT: 10, service.BUILTIN_PRESET_DUE_FIRST: 10,
                        service.BUILTIN_PRESET_MIN_CHANGEOVER: 10, service.BUILTIN_PRESET_IMPROVE_SLOW: 30}
    payload = dict(service.get_snapshot(strict_mode=True).to_dict(), time_budget_seconds=47)
    payload.update({key: "Retired malformed value" for key in RETIRED_CONFIG_FIELDS})
    original_json = json.dumps(payload)
    legacy_key = service._preset_key("legacy-explicit-budget")
    service.repo.set(legacy_key, original_json)
    service.repo.set("time_budget_seconds", "75")
    for key in RETIRED_CONFIG_FIELDS:
        service.repo.set(key, "Retired original value")
    service.conn.commit()
    retired_before = {key: tuple(service.conn.execute("SELECT * FROM ScheduleConfig WHERE config_key=?", (key,)).fetchone())
                      for key in RETIRED_CONFIG_FIELDS}
    service.ensure_defaults()
    assert service.get_snapshot(strict_mode=True).time_budget_seconds == 75
    adapted = ensure_schedule_config_snapshot(payload, strict_mode=True)
    assert adapted.time_budget_seconds == 47 and not set(RETIRED_CONFIG_FIELDS) & set(adapted.to_dict())
    baseline, failed = service.preset_service.try_load_preset_snapshot_for_baseline("legacy-explicit-budget")
    assert not failed and baseline.time_budget_seconds == 47
    applied = service.apply_preset("legacy-explicit-budget")
    assert applied["status"] == "applied" and applied["adjusted_fields"] == []
    assert service.get_snapshot(strict_mode=True).time_budget_seconds == 47
    assert service.get(legacy_key) == original_json
    assert {key: tuple(service.conn.execute("SELECT * FROM ScheduleConfig WHERE config_key=?", (key,)).fetchone())
            for key in RETIRED_CONFIG_FIELDS} == retired_before
    service.save_preset("new-explicit-budget")
    saved = json.loads(service.get(service._preset_key("new-explicit-budget")))
    assert saved["time_budget_seconds"] == 47 and not set(RETIRED_CONFIG_FIELDS) & set(saved)


def test_build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_schedule_config_snapshot(_EmptyRepo(), strict_mode=True)

    assert exc_info.value.field == "sort_strategy"
