from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from core.infrastructure.database import ensure_schema, get_connection

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"
RESOURCE_DISPATCH_JS = REPO_ROOT / "static" / "js" / "resource_dispatch.js"
RESOURCE_DISPATCH_TEMPLATE = REPO_ROOT / "templates" / "scheduler" / "resource_dispatch.html"
UI_CONTRACT_CSS = REPO_ROOT / "static" / "css" / "ui_contract.css"


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    db_path = tmp_path / "aps_execution_feedback_routes.db"
    log_dir = tmp_path / "logs"
    backup_dir = tmp_path / "backups"
    template_dir = tmp_path / "templates_excel"
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))
    monkeypatch.setenv("APS_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(template_dir))

    ensure_schema(str(db_path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(db_path))
    try:
        _seed_execution_feedback_context(conn)
        conn.commit()
    finally:
        conn.close()

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    app.config["TESTING"] = True
    return app, str(db_path)


def _seed_execution_feedback_context(conn) -> None:
    conn.executescript(
        """
        INSERT INTO ResourceTeams(team_id, name, status)
        VALUES ('T1', '一组', 'active');

        INSERT INTO Machines(machine_id, name, status, team_id)
        VALUES ('M1', '一号设备', 'active', 'T1'), ('M2', '二号设备', 'active', 'T1');

        INSERT INTO Operators(operator_id, name, status, team_id)
        VALUES ('O1', '张三', 'active', 'T1'), ('O2', '李四', 'active', 'T1');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 10, '2026-05-10', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (1);
        INSERT INTO ScheduleVersionSeq(version) VALUES (2);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
            (100, 10, 'M1', 'O1', '2026-05-01 08:00:00', '2026-05-01 09:00:00', 'unlocked', 2),
            (101, 10, 'M1', 'O1', '2026-04-30 08:00:00', '2026-04-30 09:00:00', 'unlocked', 1);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES
            (1, 'priority_first', 1, 1, 'success', '{}', 'pytest'),
            (2, 'priority_first', 1, 1, 'success', '{}', 'pytest');

        INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved)
        VALUES
            (2, 'adopted', '正式采用', 'baseline', 'completed', 'no', 'no'),
            (2, 'baseline_best', '原算法代表', 'baseline', 'completed', 'no', 'yes');

        INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, machine_id, operator_id, start_time, end_time, lock_status)
        VALUES (
            2,
            (SELECT id FROM ScheduleCandidate WHERE version = 2 AND candidate_key = 'baseline_best'),
            10,
            'M2',
            'O2',
            '2026-05-01 10:00:00',
            '2026-05-01 11:00:00',
            'unlocked'
        );

        INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
        VALUES
            (2, 'adopted', (SELECT id FROM ScheduleCandidate WHERE version = 2 AND candidate_key = 'adopted'), 'schedule'),
            (2, 'baseline_best', (SELECT id FROM ScheduleCandidate WHERE version = 2 AND candidate_key = 'baseline_best'), 'candidate_rows');

        INSERT INTO ScheduleAdjustmentDraft(draft_id, base_version, base_plan_role, status, created_by)
        VALUES ('draft-1', 2, 'adopted', 'saved_scenario', 'pytest');

        INSERT INTO ScheduleAdjustmentScenario(
            scenario_id, source_draft_id, base_version, base_plan_role, base_source_table,
            scenario_name, status, validation_status, row_count, created_by
        )
        VALUES ('scenario-plain', 'draft-1', 2, 'adopted', 'schedule', '', 'active', 'valid', 1, 'pytest');

        INSERT INTO ScheduleAdjustmentScenarioRow(
            scenario_id, source_table, source_row_id, op_id, machine_id, operator_id, start_time, end_time, lock_status
        )
        VALUES ('scenario-plain', 'schedule', 100, 10, 'M1', 'O1', '2026-05-01 12:00:00', '2026-05-01 13:00:00', 'unlocked');
        """
    )


def _json(resp) -> Dict[str, Any]:
    return json.loads(resp.get_data(as_text=True) or "{}")


def _event_count(db_path: str) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) AS count FROM OperationExecutionEvents").fetchone()
        return int(row["count"])
    finally:
        conn.close()


def _event_count_for_op(db_path: str, op_id: int) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) AS count FROM OperationExecutionEvents WHERE op_id = ?", (op_id,)).fetchone()
        return int(row["count"])
    finally:
        conn.close()


def _current_card(client) -> Dict[str, Any]:
    resp = client.get(
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
    )
    assert resp.status_code == 200
    data = _json(resp)["data"]
    return data["tasks"][0]


def _base_payload(card: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
    payload = {
        "version": 2,
        "schedule_id": card["schedule_id"],
        "batch_id": card["batch_id"],
        "requested_plan_role": "adopted",
        "effective_plan_role": "adopted",
        "source_table": "schedule",
        "scenario_id": None,
        "expected_state_revision": card["state_revision"],
        "event_time": "2026-05-01 08:10:00",
        "created_by": "张三",
        "idempotency_key": "route-key-start",
        "operator_id": "O1",
        "machine_id": "M1",
        "remark": "开始加工",
    }
    payload.update(overrides)
    return payload


def _post_controlled(client, url: str, payload: Dict[str, Any]):
    return client.post(url, json=payload, headers={"X-APS-Test-Execution-Feedback": "allow"})


def test_execution_data_returns_task_card_contract(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
    )
    payload = _json(resp)

    assert resp.status_code == 200
    assert payload["success"] is True
    data = payload["data"]
    assert data["plan_identity_label"] == "正式采用方案"
    assert data["can_write_feedback"] is True
    assert data["disabled_reason"] == ""
    assert len(data["tasks"]) == 1
    card = data["tasks"][0]
    for key in (
        "op_id",
        "schedule_id",
        "batch_id",
        "op_name",
        "current_status_label",
        "state_revision",
        "available_actions",
        "unavailable_reasons",
    ):
        assert key in card
    assert card["current_status_label"] == "待开工"
    assert isinstance(card["unavailable_reasons"], dict)
    assert card["available_actions"][0]["label"] == "开工"
    assert card["available_actions"][0]["enabled"] is True
    assert card["available_actions"][0]["disabled_reason"] == ""
    assert "start" not in card["unavailable_reasons"]
    assert "不能完工" in card["unavailable_reasons"]["finish"]


def test_plain_user_start_finish_posts_write_after_guardrail(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    start_resp = client.post(f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", json=_base_payload(card))
    start_data = _json(start_resp)["data"]

    assert start_resp.status_code == 200
    assert start_data["event"]["action_label"] == "开工"
    assert start_data["current_status_label"] == "生产中"
    assert start_data["task_card"]["current_status_label"] == "生产中"
    assert start_data["state_revision"] != card["state_revision"]
    assert _event_count(db_path) == 1

    finish_resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        json=_base_payload(
            card,
            expected_state_revision=start_data["state_revision"],
            idempotency_key="route-key-finish",
            event_time="2026-05-01 09:00:00",
            quantity_done=10,
        ),
    )
    finish_data = _json(finish_resp)["data"]

    assert finish_resp.status_code == 200
    assert finish_data["event"]["action_label"] == "完工"
    assert finish_data["current_status_label"] == "已完工"
    assert finish_data["task_card"]["current_status_label"] == "已完工"
    assert finish_data["state_revision"] != start_data["state_revision"]
    assert _event_count(db_path) == 2


def test_controlled_start_finish_posts_return_refresh_contract(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    start_data = _json(start_resp)["data"]

    assert start_resp.status_code == 200
    for key in (
        "event",
        "current_status",
        "current_status_label",
        "state_revision",
        "idempotency_reused",
        "task_card",
    ):
        assert key in start_data
    for key in (
        "event_id",
        "op_id",
        "schedule_id",
        "action",
        "action_label",
        "event_time",
        "created_by",
        "remark",
    ):
        assert key in start_data["event"]
    assert start_data["event"]["action_label"] == "开工"
    assert start_data["current_status_label"] == "生产中"
    assert start_data["idempotency_reused"] is False
    for key in (
        "op_id",
        "schedule_id",
        "batch_id",
        "op_name",
        "current_status",
        "current_status_label",
        "state_revision",
        "actual_start_time",
        "actual_end_time",
        "planned_machine_display_label",
        "planned_machine_identity_label",
        "actual_machine_label",
        "actual_machine_display_label",
        "actual_machine_identity_label",
        "planned_operator_display_label",
        "planned_operator_identity_label",
        "actual_operator_label",
        "actual_operator_display_label",
        "actual_operator_identity_label",
        "last_event_action_label",
        "last_event_remark",
        "latest_exception_reason_label",
        "latest_exception_severity_label",
        "latest_exception_impact_minutes_label",
        "latest_exception_affected_machine_label",
        "latest_exception_affected_operator_label",
        "latest_exception_handling_status_label",
        "latest_exception_suggest_reschedule_label",
        "latest_exception_remark",
        "updated_at",
        "available_actions",
        "unavailable_reasons",
    ):
        assert key in start_data["task_card"]
    assert start_data["task_card"]["current_status_label"] == "生产中"
    assert start_data["task_card"]["planned_machine_label"] == "M1 一号设备"
    assert start_data["task_card"]["planned_machine_display_label"] == "一号设备"
    assert start_data["task_card"]["planned_machine_identity_label"] == "M1 一号设备"
    assert start_data["task_card"]["actual_machine_label"] == "M1 一号设备"
    assert start_data["task_card"]["actual_machine_display_label"] == "一号设备"
    assert start_data["task_card"]["actual_machine_identity_label"] == "M1 一号设备"
    assert start_data["task_card"]["planned_operator_label"] == "O1 张三"
    assert start_data["task_card"]["planned_operator_display_label"] == "张三"
    assert start_data["task_card"]["planned_operator_identity_label"] == "O1 张三"
    assert start_data["task_card"]["actual_operator_label"] == "O1 张三"
    assert start_data["task_card"]["actual_operator_display_label"] == "张三"
    assert start_data["task_card"]["actual_operator_identity_label"] == "O1 张三"
    action_by_name = {item["action"]: item for item in start_data["task_card"]["available_actions"]}
    assert action_by_name["finish"]["label"] == "完工"
    assert action_by_name["finish"]["enabled"] is True

    finish_payload = _base_payload(
        card,
        expected_state_revision=start_data["state_revision"],
        idempotency_key="route-key-finish",
        event_time="2026-05-01 09:00:00",
        quantity_done=8,
        quantity_scrapped="",
    )
    finish_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish", finish_payload)
    finish_data = _json(finish_resp)["data"]

    assert finish_resp.status_code == 200
    assert finish_data["event"]["action_label"] == "完工"
    assert finish_data["current_status_label"] == "已完工"
    assert finish_data["task_card"]["current_status_label"] == "已完工"
    assert finish_data["task_card"]["actual_end_time"] == "2026-05-01 09:00:00"
    assert _event_count(db_path) == 2


def test_plain_write_does_not_depend_on_testing_header(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    app.config["TESTING"] = False
    resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    payload = _json(resp)["data"]

    assert resp.status_code == 200
    assert payload["event"]["action_label"] == "开工"
    assert _event_count(db_path) == 1


def test_direct_post_rejects_candidate_preview_and_history(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    cases: Tuple[Dict[str, Any], ...] = (
        {"requested_plan_role": "baseline_best", "effective_plan_role": "adopted", "source_table": "schedule"},
        {"requested_plan_role": "adopted", "scenario_id": "scenario-plain"},
        {"version": 1},
    )

    for index, overrides in enumerate(cases):
        resp = _post_controlled(
            client,
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
            _base_payload(card, idempotency_key=f"reject-key-{index}", **overrides),
        )
        payload = _json(resp)
        assert resp.status_code == 409
        assert payload["error"]["code"] == "6003"
        assert payload["error"]["details"]["reason"] == "not_current_official_plan"
        assert payload["error"]["details"]["action_label"] == "开工"
        assert payload["error"]["details"]["can_retry"] is False
    assert _event_count(db_path) == 0


def test_direct_post_requires_complete_plan_identity_and_batch_match(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    missing_identity_payload = _base_payload(card, idempotency_key="missing-identity")
    missing_identity_payload.pop("requested_plan_role")
    resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        missing_identity_payload,
    )
    payload = _json(resp)
    assert resp.status_code == 400
    assert payload["error"]["details"]["reason"] == "missing_required_field"
    assert payload["error"]["details"]["field"] == "requested_plan_role"
    assert payload["error"]["details"]["can_retry"] is True

    wrong_batch = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, idempotency_key="wrong-batch", batch_id="B-other"),
    )
    wrong_batch_payload = _json(wrong_batch)
    assert wrong_batch.status_code == 409
    assert wrong_batch_payload["error"]["details"]["reason"] == "schedule_mismatch"
    assert wrong_batch_payload["error"]["details"]["can_retry"] is True
    assert _event_count(db_path) == 0


def test_validation_errors_use_chinese_field_label(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    cases = [
        ("start", {"operator_id": ""}, "操作人员", "operator_id"),
        ("start", {"machine_id": ""}, "设备", "machine_id"),
        ("finish", {"quantity_done": ""}, "完成数量", "quantity_done"),
        ("start", {"expected_state_revision": ""}, "页面状态", "expected_state_revision"),
    ]

    for action, overrides, field_label, raw_field in cases:
        resp = _post_controlled(
            client,
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/{action}",
            _base_payload(card, idempotency_key=f"bad-{raw_field}", **overrides),
        )
        payload = _json(resp)
        assert resp.status_code == 400
        assert payload["error"]["details"]["field_label"] == field_label
        assert payload["error"]["details"]["can_retry"] is True
        assert raw_field not in payload["error"]["message"]


def test_conflicts_return_reason_and_action_label(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    finish_before_start = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(card, idempotency_key="finish-before-start", quantity_done=10),
    )
    finish_error = _json(finish_before_start)["error"]
    assert finish_before_start.status_code == 409
    assert finish_error["details"]["reason"] == "invalid_state_transition"
    assert finish_error["details"]["action_label"] == "完工"
    assert finish_error["details"]["can_retry"] is False
    assert "刷新页面查看最新状态" in finish_error["message"]
    assert "联系计划员处理" in finish_error["message"]

    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    state_revision = _json(start_resp)["data"]["state_revision"]

    early_finish = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(
            card,
            expected_state_revision=state_revision,
            idempotency_key="early-finish",
            event_time="2026-05-01 08:05:00",
            quantity_done=10,
        ),
    )
    early_finish_error = _json(early_finish)["error"]
    assert early_finish.status_code == 409
    assert early_finish_error["details"]["reason"] == "invalid_state_transition"
    assert early_finish_error["details"]["action_label"] == "完工"
    assert early_finish_error["details"]["can_retry"] is False

    stale_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(card, idempotency_key="stale-finish", quantity_done=10),
    )
    stale_error = _json(stale_resp)["error"]
    assert stale_resp.status_code == 409
    assert stale_error["details"]["reason"] == "stale_state_revision"
    assert stale_error["details"]["action_label"] == "完工"
    assert stale_error["details"]["can_retry"] is True

    conflict_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, event_time="2026-05-01 08:20:00"),
    )
    conflict_error = _json(conflict_resp)["error"]
    assert conflict_resp.status_code == 409
    assert conflict_error["details"]["reason"] == "idempotency_conflict"
    assert conflict_error["details"]["action_label"] == "开工"
    assert conflict_error["details"]["can_retry"] is True

    finish_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(card, expected_state_revision=state_revision, idempotency_key="finish-ok", quantity_done=10),
    )
    finish_state_revision = _json(finish_resp)["data"]["state_revision"]
    restart_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, expected_state_revision=finish_state_revision, idempotency_key="restart-key"),
    )
    restart_error = _json(restart_resp)["error"]
    assert restart_resp.status_code == 409
    assert restart_error["details"]["reason"] == "invalid_state_transition"
    assert restart_error["details"]["action_label"] == "开工"
    assert restart_error["details"]["can_retry"] is False
    assert "刷新页面查看最新状态" in restart_error["message"]
    assert "联系计划员处理" in restart_error["message"]


def test_start_finish_business_validation_is_user_facing(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    wrong_machine = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, machine_id="M2"),
    )
    assert wrong_machine.status_code == 400
    wrong_machine_error = _json(wrong_machine)["error"]
    assert wrong_machine_error["details"]["reason"] == "invalid_field_value"
    assert wrong_machine_error["details"]["field_label"] == "设备"

    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    state_revision = _json(start_resp)["data"]["state_revision"]
    too_many = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(
            card,
            expected_state_revision=state_revision,
            idempotency_key="too-many-finish",
            quantity_done=9,
            quantity_scrapped=2,
        ),
    )
    too_many_error = _json(too_many)["error"]
    assert too_many.status_code == 400
    assert too_many_error["details"]["reason"] == "invalid_field_value"
    assert too_many_error["details"]["field_label"] == "完成数量"
    assert too_many_error["details"]["can_retry"] is True
    assert "计划数量" in too_many_error["message"]
    assert "quantity_done" not in too_many_error["message"]


def test_start_rejects_schedule_without_planned_machine(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
            VALUES (11, 'OP11', 'B1', 'piece-b', 20, '铣削', 'internal', 'scheduled')
            """
        )
        conn.execute(
            """
            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (102, 11, NULL, 'O1', '2026-05-01 10:00:00', '2026-05-01 11:00:00', 'unlocked', 2)
            """
        )
        conn.commit()
    finally:
        conn.close()

    resp = _post_controlled(
        client,
        "/scheduler/resource-dispatch/execution/11/start",
        _base_payload(card, schedule_id=102, idempotency_key="missing-plan-machine", expected_state_revision="11:0:0"),
    )
    payload = _json(resp)

    assert resp.status_code == 400
    assert payload["error"]["details"]["reason"] == "invalid_field_value"
    assert payload["error"]["details"]["field_label"] == "设备"
    assert _event_count_for_op(db_path, 11) == 0


def test_finish_quantity_boundaries_use_chinese_field_labels(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    state_revision = _json(start_resp)["data"]["state_revision"]

    cases = [
        ({"quantity_done": -1}, "完成数量"),
        ({"quantity_done": "abc"}, "完成数量"),
        ({"quantity_done": 1.5}, "完成数量"),
        ({"quantity_done": "1.5"}, "完成数量"),
        ({"quantity_done": True}, "完成数量"),
        ({"quantity_done": 8, "quantity_scrapped": -1}, "报废数量"),
        ({"quantity_done": 8, "quantity_scrapped": "abc"}, "报废数量"),
        ({"quantity_done": 8, "quantity_scrapped": 1.5}, "报废数量"),
    ]

    for index, (overrides, field_label) in enumerate(cases):
        resp = _post_controlled(
            client,
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
            _base_payload(
                card,
                expected_state_revision=state_revision,
                idempotency_key=f"bad-quantity-{index}",
                **overrides,
            ),
        )
        payload = _json(resp)
        assert resp.status_code == 400
        assert payload["error"]["details"]["reason"] == "invalid_field_value"
        assert payload["error"]["details"]["field_label"] == field_label
        assert payload["error"]["details"]["can_retry"] is True
        assert "quantity_" not in payload["error"]["message"]


def test_resource_dispatch_page_has_execution_tab_without_feedback_protection_copy(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "现场反馈" in body
    assert "data-execution-url=" in body
    assert 'id="rdExecutionCreatedBy"' in body
    assert "反馈人" in body
    assert "现场反馈保护还没开启，暂不能提交开工或完工" not in body


def test_resource_dispatch_frontend_posts_execution_button_clicks() -> None:
    source = RESOURCE_DISPATCH_JS.read_text(encoding="utf-8")
    template = RESOURCE_DISPATCH_TEMPLATE.read_text(encoding="utf-8")
    css = UI_CONTRACT_CSS.read_text(encoding="utf-8")

    assert "bindExecutionActionClicks" in source
    assert "postExecutionAction" in source
    assert "executionCreatedBy" in source
    assert "rdExecutionCreatedBy" in source
    assert "请先填写反馈人。" in source
    assert "payload.created_by = createdBy" in source
    assert 'payload.created_by = "现场反馈"' not in source
    assert "window.confirm" not in source
    assert "executionPromptStartResource" not in source
    assert "请确认实际设备编号" not in source
    assert "请填写实际人员工号" not in source
    assert 'payload.machine_id = machine' in source
    assert 'payload.operator_id = operator' in source
    assert "renderFinishInlineForm" in source
    assert "aps-execution-finish-qty" in source
    assert "请填写完成数量。" in source
    assert "aps-execution-inline-form" in css
    assert "background: var(--ui-surface-muted" in css
    assert "--ui-bg-subtle" not in css
    assert "normalizedUnavailableReasonTexts" in source
    assert "statusUnavailableReasonSummary" in source
    assert '"start", "pause", "resume", "finish", "report_exception"' in source
    assert 'actions.join("、")' in source
    assert 'map(escapeHtml).join("；")' not in source
    assert "第一版" not in source
    assert 'id="rdExecutionCreatedBy"' in template
    assert "反馈人" in template
    assert 'method: "POST"' in source
    assert 'data-op-id="' in source
    assert 'data-state-revision="' in source
    assert 'data-machine-id="' in source
    assert 'data-operator-id="' in source
    assert "/scheduler/resource-dispatch/execution/" in source
    assert "idempotency_key" in source
