"""配置快照读取与缺失配置拒绝。"""

from __future__ import annotations

import json

import pytest

from core.errors import ValidationError
from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_config_runtime_coercion import ensure_schedule_config_snapshot
from core.models.schedule_config_runtime_fields import RETIRED_CONFIG_FIELDS, list_runtime_config_fields
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.config.config_field_spec import list_config_fields
from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot
from data.repositories.config_repo import ConfigRepository
from tests._support.paths import REPO_ROOT
from web.bootstrap.schedule_config import bootstrap_schedule_config

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _stored_snapshot(conn):
    """Build the snapshot from stored ScheduleConfig rows, as the run preflight reads them."""
    rows = [dict(row) for row in conn.execute("SELECT config_key, config_value FROM ScheduleConfig ORDER BY rowid")]
    return build_schedule_config_snapshot(rows=rows)


@pytest.fixture()
def config_store(tmp_path):
    test_db = tmp_path / "aps_config_field_spec.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    bootstrap_schedule_config(str(test_db))
    conn = get_connection(str(test_db))
    try:
        yield conn, ConfigRepository(conn), test_db
    finally:
        conn.close()


def test_config_snapshot_includes_hidden_fields_and_ignores_retired_fields(config_store) -> None:
    conn, repo, _database = config_store
    snap = _stored_snapshot(conn)
    assert snap.auto_assign_persist == "yes"
    assert snap.to_dict()["auto_assign_persist"] == "yes"
    assert snap.graph_analysis_mode == "on"
    assert snap.graph_block_on_cycle == "no"
    assert snap.graph_critical_weight == 500
    assert snap.graph_impact_weight == 10
    assert snap.time_budget_seconds == 10
    runtime_keys = {spec.key for spec in list_runtime_config_fields()}
    page_keys = {spec.key for spec in list_config_fields()}
    for key in RETIRED_CONFIG_FIELDS:
        assert not hasattr(snap, key) and key not in snap.to_dict()
        assert key not in runtime_keys and key not in page_keys
    assert snap.graph_debug_export == "no"
    assert repo.get_value("objective") == "min_overdue"
    assert snap.graph_analysis_mode == "on"
    assert snap.to_dict()["graph_critical_weight"] == 500


def test_legacy_preset_keeps_budget_and_saved_rows_during_reads_and_restart(config_store) -> None:
    conn, repo, database = config_store
    payload = dict(_stored_snapshot(conn).to_dict(), time_budget_seconds=47)
    payload.update({key: "Retired malformed value" for key in RETIRED_CONFIG_FIELDS})
    original_json = json.dumps(payload)
    legacy_key = "preset.legacy-explicit-budget"
    repo.set_batch(
        [
            (legacy_key, original_json, None),
            ("time_budget_seconds", "75", None),
            *((key, "Retired original value", None) for key in RETIRED_CONFIG_FIELDS),
        ]
    )
    conn.commit()
    rows_before = [tuple(row) for row in conn.execute("SELECT * FROM ScheduleConfig ORDER BY config_key")]
    bootstrap_schedule_config(str(database))
    assert _stored_snapshot(conn).time_budget_seconds == 75
    adapted = ensure_schedule_config_snapshot(json.loads(repo.get_value(legacy_key)), strict_mode=True)
    assert adapted.time_budget_seconds == 47 and not set(RETIRED_CONFIG_FIELDS) & set(adapted.to_dict())
    assert repo.get_value(legacy_key) == original_json
    assert [tuple(row) for row in conn.execute("SELECT * FROM ScheduleConfig ORDER BY config_key")] == rows_before


def test_build_schedule_config_snapshot_strict_mode_rejects_missing_repo_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_schedule_config_snapshot(rows=[])

    assert exc_info.value.field == "sort_strategy"


def test_calendar_reads_only_its_holiday_efficiency(config_store) -> None:
    conn, repo, _database = config_store
    repo.set_batch(
        [
            ("sort_strategy", "damaged-unrelated-setting", None),
            ("holiday_default_efficiency", "0.65", None),
        ]
    )
    conn.commit()
    statements = []
    conn.set_trace_callback(statements.append)
    try:
        service = CalendarService(conn)
        calendar = service._admin._build_work_calendar(date_value="2026-10-01", day_type="holiday", shift_hours=8)
        service._admin.repo.upsert_many([calendar])
        conn.commit()
    finally:
        conn.set_trace_callback(None)
    assert calendar.efficiency == 0.65
    reads = [sql for sql in statements if "SELECT" in sql.upper() and "ScheduleConfig" in sql]
    assert len(reads) == 1 and "holiday_default_efficiency" in reads[0]
    assert repo.get_value("sort_strategy") == "damaged-unrelated-setting"


@pytest.mark.parametrize("raw_value", [None, "NaN", "0"])
def test_calendar_rejects_missing_or_invalid_holiday_efficiency(config_store, raw_value) -> None:
    conn, repo, _database = config_store
    if raw_value is None:
        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = 'holiday_default_efficiency'")
    else:
        repo.set_batch([("holiday_default_efficiency", raw_value, None)])
    conn.commit()
    with pytest.raises(ValidationError) as rejected:
        CalendarService(conn)._admin._build_work_calendar(date_value="2026-10-01", day_type="holiday", shift_hours=8)
    assert rejected.value.field == "holiday_default_efficiency"
    assert conn.execute("SELECT COUNT(*) FROM WorkCalendar").fetchone()[0] == 0


def test_demo_configuration_uses_registered_fields_and_one_batch_write(config_store, monkeypatch) -> None:
    from tools.wufenchang_demo.blueprint import demo_blueprint
    from tools.wufenchang_demo.builder import _configure

    conn, repo, database = config_store
    values = demo_blueprint()["config_patch"]
    writes = []
    original_set_batch = ConfigRepository.set_batch

    def record_batch_write(target, updates):
        writes.append(list(updates))
        original_set_batch(target, writes[-1])

    monkeypatch.setattr(ConfigRepository, "set_batch", record_batch_write)
    _configure(database, values)
    assert len(writes) == 1 and {key for key, _value, _description in writes[0]} == set(values)
    snapshot = _stored_snapshot(conn)
    assert snapshot.time_budget_seconds == values["time_budget_seconds"]
    assert snapshot.algo_mode == values["algo_mode"]

    before = [tuple(row) for row in conn.execute("SELECT * FROM ScheduleConfig ORDER BY config_key")]
    with pytest.raises(ValidationError):
        _configure(database, {"time_budget_seconds": 45, "objective": "invalid-objective"})
    assert len(writes) == 1
    assert [tuple(row) for row in conn.execute("SELECT * FROM ScheduleConfig ORDER BY config_key")] == before
