"""回归测试：甘特调整草稿存为模拟方案（save_scenario）只写 ScheduleAdjustmentScenario(Row) 不动正式表，被阻塞草稿拒绝保存；ScheduleAdjustmentScenario 表/索引存在且 detect_schema_is_current 依赖之、v12 旧库迁移保留既有数据；scenario_id 预览读模拟行不回退 adopted，save-scenario 路由用服务端操作者 web 覆盖 JSON 里的 created_by。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from core.infrastructure.migration_state import MigrationContractError, detect_schema_is_current
from core.services.scheduler.gantt_adjustment_scenario_service import GanttAdjustmentScenarioService
from core.services.scheduler.gantt_service import GanttService
from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
from tests._support.gantt_scenario import (
    SCHEMA_PATH as SCHEMA_PATH,
)
from tests._support.gantt_scenario import (
    VERSION as VERSION,
)
from tests._support.gantt_scenario import (
    _build_app as _build_app,
)
from tests._support.gantt_scenario import (
    _connect as _connect,
)
from tests._support.gantt_scenario import (
    _draft_with_change as _draft_with_change,
)
from tests._support.gantt_scenario import (
    _seed_base as _seed_base,
)
from tests.gantt.gantt_legacy_schema_support import (
    assert_frozen_catalog,
    assert_legacy_business_data_preserved,
    load_frozen_schema,
    schema_catalog,
    snapshot_legacy_business_data,
    strip_later_schema,
)

_PUBLIC_GANTT_JSON_FORBIDDEN_KEYS = {
    "op_id",
    "schedule_id",
    "scenario_id",
    "candidate_id",
    "selection_candidate_id",
    "resolved_candidate_id",
    "candidate_key",
    "source_row_id",
    "source_table",
}


def _public_json_forbidden_key_paths(value, *, path: str = "data"):
    paths = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if str(key) in _PUBLIC_GANTT_JSON_FORBIDDEN_KEYS:
                paths.append(key_path)
            paths.extend(_public_json_forbidden_key_paths(child, path=key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_public_json_forbidden_key_paths(child, path=f"{path}[{index}]"))
    return paths


def _table_names(conn) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row["name"]) for row in rows}


def _index_names(conn) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return {str(row["name"]) for row in rows}


def _snapshot(conn) -> dict:
    return {
        "schedule": [dict(row) for row in conn.execute("SELECT * FROM Schedule ORDER BY id").fetchall()],
        "history": [dict(row) for row in conn.execute("SELECT * FROM ScheduleHistory ORDER BY id").fetchall()],
        "seq": [dict(row) for row in conn.execute("SELECT * FROM ScheduleVersionSeq ORDER BY version").fetchall()],
        "candidate": [dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidate ORDER BY id").fetchall()],
        "candidate_rows": [dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidateRows ORDER BY id").fetchall()],
        "candidate_selection": [
            dict(row) for row in conn.execute("SELECT * FROM ScheduleCandidateSelection ORDER BY id").fetchall()
        ],
    }


def _create_v12_schema(conn) -> None:
    """Load b83407fe's exact v12 catalog without inheriting current-schema objects."""
    load_frozen_schema(conn, version=12)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert not {"ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow", "OperationExecutionEvents"} & names
    assert not {"idx_batch_operations_identity_unique", "idx_schedule_identity_unique"} & names
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall() == []
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 12
    assert not detect_schema_is_current(conn)


@pytest.mark.parametrize("version,tables,indexes", [(12, 31, 66), (13, 33, 72), (16, 34, 80)])
def test_frozen_legacy_catalog_matches_history_before_seeding(tmp_path, version, tables, indexes):
    conn = get_connection(str(tmp_path / "frozen.db"))
    try:
        load_frozen_schema(conn, version=version)
        assert_frozen_catalog(conn, version=version)
        objects = schema_catalog(conn)["objects"]
        assert sum(row[0] == "table" for row in objects) == tables
        assert sum(row[0] == "index" for row in objects) == indexes
        assert not any(row[0] == "trigger" for row in objects)
    finally:
        conn.close()


@pytest.mark.parametrize("version", [13, 16])
@pytest.mark.parametrize("damage", ["business_rows", "dangling_trigger", "foreign_keys_off"])
def test_legacy_fixture_replacement_rejects_non_pristine_database(tmp_path, version, damage):
    conn = get_connection(str(tmp_path / "not_pristine.db"))
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if damage == "business_rows":
            conn.execute("INSERT INTO Parts(part_no, part_name) VALUES ('RETAIN', 'retained business row')")
            conn.commit()
        elif damage == "dangling_trigger":
            conn.execute("CREATE TRIGGER broken_fixture AFTER UPDATE ON Parts BEGIN SELECT * FROM AbsentTable; END")
        else:
            conn.execute("PRAGMA foreign_keys = OFF")
        before = tuple(conn.iterdump())
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        with pytest.raises(AssertionError):
            strip_later_schema(conn, version=version)
        assert tuple(conn.iterdump()) == before
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == foreign_keys
    finally:
        conn.close()


def test_scenario_schema_exists_and_detection_requires_it(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert {"ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow"} <= _table_names(conn)
        assert {
            "idx_schedule_adjustment_scenario_base",
            "idx_schedule_adjustment_scenario_draft",
            "idx_schedule_adjustment_scenario_row_op",
            "idx_schedule_adjustment_scenario_row_time",
        } <= _index_names(conn)
        assert detect_schema_is_current(conn)
        conn.execute("DROP TABLE ScheduleAdjustmentScenarioRow")
        assert not detect_schema_is_current(conn)
        conn.commit()
        with pytest.raises(MigrationContractError):
            ensure_schema(
                str(tmp_path / "aps.db"), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups")
            )
        assert "ScheduleAdjustmentScenarioRow" not in _table_names(conn)
        assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
        assert not detect_schema_is_current(conn)
    finally:
        conn.close()


def test_scenario_migration_preserves_existing_v12_data(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v12.db"
    conn = get_connection(str(db_path))
    try:
        _create_v12_schema(conn)
        _seed_base(conn)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        before = _snapshot(conn)
        all_old_rows = snapshot_legacy_business_data(conn)
        conn.executescript(
            """
            CREATE TABLE LegacyRows (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO LegacyRows (id, name) VALUES (1, 'keep-me');
            """
        )
        conn.commit()
    finally:
        conn.close()

    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "legacy_backups"))
    conn = get_connection(str(db_path))
    try:
        schema_version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        assert int(schema_version["version"]) == CURRENT_SCHEMA_VERSION
        assert {"ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow"} <= _table_names(conn)
        assert {
            "idx_schedule_adjustment_scenario_base",
            "idx_schedule_adjustment_scenario_draft",
            "idx_schedule_adjustment_scenario_row_op",
            "idx_schedule_adjustment_scenario_row_time",
        } <= _index_names(conn)
        assert detect_schema_is_current(conn)
        assert _snapshot(conn) == before
        assert_legacy_business_data_preserved(conn, all_old_rows)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT name FROM LegacyRows WHERE id=1").fetchone()["name"] == "keep-me"
    finally:
        conn.close()


def test_scenario_id_preview_reads_scenario_rows_without_adopted_fallback(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = GanttAdjustmentScenarioService(conn).save_scenario(
            draft_id=_draft_with_change(conn),
            scenario_name="单日模拟",
        )
        plan_query = SchedulePlanQueryService(conn)

        formal_rows = plan_query.list_plan_detail_rows_between(
            version=VERSION,
            role="adopted",
            start_time="2026-05-04 00:00:00",
            end_time="2026-05-05 00:00:00",
        )
        scenario_rows = plan_query.list_plan_detail_rows_between_for_view(
            version=VERSION,
            role="adopted",
            scenario_id=scenario.scenario_id,
            start_time="2026-05-04 00:00:00",
            end_time="2026-05-05 00:00:00",
        )

        assert next(row for row in formal_rows if row["op_id"] == 30)["start_time"] == "2026-05-04 08:00:00"
        assert next(row for row in scenario_rows if row["op_id"] == 30)["start_time"] == "2026-05-04 11:00:00"
        with pytest.raises(ValueError, match="模拟方案不存在"):
            plan_query.resolve_plan_view(VERSION, "adopted", "scenario-missing")
    finally:
        conn.close()


def test_gantt_service_and_template_keep_scenario_preview_context(tmp_path: Path, monkeypatch) -> None:
    from tests._support.gantt_current import assert_plan_exports, assert_retired, prepare_read_state
    from tests._support.gantt_retirement import _business_state, _canonical_workspace

    conn = _connect(tmp_path)
    try:
        _seed_base(conn)
        scenario = GanttAdjustmentScenarioService(conn).save_scenario(
            draft_id=_draft_with_change(conn),
            scenario_name="单日模拟",
        )
        data = GanttService(conn).get_gantt_tasks(
            view="machine",
            start_date="2026-05-04",
            end_date="2026-05-04",
            version=VERSION,
            plan_role="adopted",
            scenario_id=scenario.scenario_id,
        )
        op30_task = next(task for task in data["tasks"] if (task.get("meta") or {}).get("operation_label") == "10（铣削）")
        assert op30_task["start"] == "2026-05-04 11:00:00"
        assert data["is_scenario_preview"] is True
        assert data["scenario_id"] == scenario.scenario_id
    finally:
        conn.close()

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    before = prepare_read_state(client)
    query = {"version": VERSION, "plan_role": "adopted", "scenario_id": scenario.scenario_id}
    context, workspace = _canonical_workspace(client, query)
    assert set(context) == {"plan_ref"}
    assert scenario.scenario_id not in json.dumps(context)
    assert workspace["data"]["plan"]["kind"] == "scenario"
    assert workspace["data"]["plan"]["is_current_official"] is False
    current = next(task for task in workspace["data"]["tasks"] if task["process_label"] == "铣削")
    assert current["start"] == "2026-05-04T11:00:00"
    assert current["end"] == "2026-05-04T12:00:00"
    assert _public_json_forbidden_key_paths(workspace["data"]) == []
    assert_plan_exports(client, context, workspace)
    data_response = client.get(
        f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role=adopted&scenario_id={scenario.scenario_id}"
    )
    payload = data_response.get_json() or {}
    public_data = payload.get("data") or {}
    assert data_response.status_code == 200
    assert public_data.get("is_scenario_preview") is True
    assert _public_json_forbidden_key_paths(public_data) == []
    zoom_html = assert_retired(client, dict(query, gantt_zoom="hour"))
    assert scenario.scenario_id not in zoom_html
    assert _business_state(client) == before


