"""回归测试：现场执行事实读取须按完整计划身份(version/schedule_id/source_table/effective_plan_role)收口——ExecutionFactProvider.facts_by_op_id_for_plan_rows 缺字段/重复 op_id 身份/include 越界时报错，旧版本(v1)反馈不污染当前任务卡，事件列表与现场写入接口缺身份时返回 400，超期正式方案导出标注「历史正式方案」。"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from urllib.parse import unquote

import openpyxl
import pytest

from core.infrastructure.database import get_connection
from core.models.operation_execution_scope import OperationExecutionScope
from core.models.operation_execution_state import OperationExecutionState
from core.services.scheduler.execution_fact_provider import ExecutionFact, ExecutionFactProvider
from core.services.scheduler.execution_snapshot import build_execution_snapshot, positive_op_ids
from core.services.scheduler.operation_execution_feedback_service import ExecutionFeedbackContext
from core.services.scheduler.resource_dispatch_actual_records import TaskRef
from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from tests.operation_execution.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _current_query,
    _event_count,
    _events_url,
    _json,
    _post_controlled,
)


def _insert_legacy_v1_start(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        OperationExecutionEventRepo(conn).insert_event(
            {
                "schedule_version": 1,
                "schedule_id": 101,
                "op_id": 10,
                "batch_id": "B1",
                "source_table": "schedule",
                "effective_plan_role": "adopted",
                "scenario_id": None,
                "event_type": "start",
                "reported_status": "processing",
                "event_time": "2026-04-30 08:10:00",
                "actual_machine_id": "M1",
                "actual_operator_id": "O1",
                "created_by": "pytest",
                "idempotency_key": "legacy-v1-start",
                "request_fingerprint": "legacy-v1-start",
                "previous_state_revision": "10:0:0",
            }
        )
        conn.commit()
    finally:
        conn.close()


def _current_execution_payload(client):
    resp = client.get(f"/scheduler/resource-dispatch/execution/data?{_current_query()}")
    assert resp.status_code == 200
    return _json(resp)["data"]


def _summary_dict(wb) -> dict:
    out = {}
    for row in wb["查询摘要"].iter_rows(min_row=2, values_only=True):
        key, value = row[0], row[1]
        if key:
            out[str(key)] = value
    return out


class _FakeExecutionFactRepo:
    def __init__(self, states_by_scope):
        self._states_by_scope = states_by_scope

    def aggregate_states_by_scopes(self, scopes):
        return {scope: self._states_by_scope.get(scope) for scope in scopes}


def _scope(op_id: int = 10) -> OperationExecutionScope:
    return OperationExecutionScope.from_values(
        schedule_version=2,
        schedule_id=100,
        op_id=op_id,
        batch_id="B1",
        source_table="schedule",
        effective_plan_role="adopted",
    )


def _fact_from_actual_times(actual_start_time, actual_end_time=None) -> ExecutionFact:
    scope = _scope()
    state = OperationExecutionState(
        op_id=10,
        batch_id="B1",
        current_status="processing",
        actual_start_time=actual_start_time,
        actual_end_time=actual_end_time,
        state_revision="10:1:1",
    )
    provider = ExecutionFactProvider(None)
    provider.event_repo = _FakeExecutionFactRepo({scope: state})
    return provider.facts_by_scope([scope])[scope]


def test_current_task_card_ignores_superseded_same_op_feedback(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_legacy_v1_start(db_path)

    data = _current_execution_payload(app.test_client())
    card = data["tasks"][0]

    assert card["current_status_label"] == "待开工"
    assert "state_revision" not in card
    assert str(card["state_key"]).startswith("state_")
    assert card["actual_start_time"] is None
    assert card["actual_machine_label"] is None


def test_execution_fact_provider_scopes_dashboard_rows_by_plan_identity(tmp_path, monkeypatch) -> None:
    _app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_legacy_v1_start(db_path)
    conn = get_connection(db_path)
    try:
        rows = SchedulePlanQueryService(conn).list_plan_detail_rows_between_for_view(
            version=2,
            role="adopted",
            start_time="2026-05-01 00:00:00",
            end_time="2026-05-02 00:00:00",
        )
        provider = ExecutionFactProvider(conn)

        with pytest.raises(ValueError, match="完整计划身份"):
            provider.facts_by_op_id([10])
        scoped_fact = provider.facts_by_op_id_for_plan_rows(
            rows,
            {"version": 2, "source_table": "schedule", "effective_plan_role": "adopted"},
            include_op_ids=[10],
        )[10]

        assert scoped_fact.actual_status == "not_started"
        assert scoped_fact.actual_start_time is None
        assert scoped_fact.state_revision == "10:0:0"
        assert scoped_fact.schedule_version == 2
        assert scoped_fact.schedule_id == 100
    finally:
        conn.close()


def test_execution_scope_read_fails_loudly_when_plan_identity_is_incomplete() -> None:
    with pytest.raises(ValueError, match="schedule_id"):
        ExecutionFactProvider(None).facts_by_op_id_for_plan_rows(
            [{"op_id": 10, "version": 2, "batch_id": "B1"}],
            {"version": 2, "source_table": "schedule", "effective_plan_role": "adopted"},
            include_op_ids=[10],
        )
    with pytest.raises(ValueError, match="schedule_id"):
        ExecutionFactProvider(None).facts_by_op_id_for_plan_rows(
            [{"op_id": 10, "id": 100, "version": 2, "batch_id": "B1"}],
            {"version": 2, "source_table": "schedule", "effective_plan_role": "adopted"},
            include_op_ids=[10],
        )
    with pytest.raises(ValueError, match="version"):
        ExecutionFactProvider(None).facts_by_op_id_for_plan_rows(
            [{"op_id": 10, "schedule_id": 100, "batch_id": "B1"}],
            {"version": 2, "source_table": "schedule", "effective_plan_role": "adopted"},
            include_op_ids=[10],
        )
    with pytest.raises(ValueError, match="source_table"):
        ExecutionFactProvider(None).facts_by_op_id_for_plan_rows(
            [{"op_id": 10, "schedule_id": 100, "version": 2, "batch_id": "B1"}],
            {"version": 2, "effective_plan_role": "adopted"},
            include_op_ids=[10],
        )
    with pytest.raises(ValueError, match="effective_plan_role"):
        ExecutionFactProvider(None).facts_by_op_id_for_plan_rows(
            [{"op_id": 10, "schedule_id": 100, "version": 2, "batch_id": "B1"}],
            {"version": 2, "source_table": "schedule"},
            include_op_ids=[10],
        )


def test_execution_fact_provider_rejects_duplicate_op_id_scopes() -> None:
    rows = [
        {"op_id": 10, "schedule_id": 100, "version": 2, "batch_id": "B1"},
        {"op_id": 10, "schedule_id": 101, "version": 2, "batch_id": "B1"},
    ]
    with pytest.raises(ValueError, match="多个现场执行身份"):
        ExecutionFactProvider(None).facts_by_op_id_for_plan_rows(
            rows,
            {"version": 2, "source_table": "schedule", "effective_plan_role": "adopted"},
            include_op_ids=[10],
        )


def test_execution_fact_provider_rejects_include_op_id_without_scope(tmp_path, monkeypatch) -> None:
    _app, db_path = _build_app(tmp_path, monkeypatch)
    conn = get_connection(db_path)
    try:
        rows = SchedulePlanQueryService(conn).list_plan_detail_rows_between_for_view(
            version=2,
            role="adopted",
            start_time="2026-05-01 00:00:00",
            end_time="2026-05-02 00:00:00",
        )
        with pytest.raises(ValueError, match="现场执行事实缺少完整计划身份：op_id=20"):
            ExecutionFactProvider(conn).facts_by_op_id_for_plan_rows(
                rows,
                {"version": 2, "source_table": "schedule", "effective_plan_role": "adopted"},
                include_op_ids=[30, 20, 10, 20, 0, -1, "x", None],
            )
    finally:
        conn.close()


@pytest.mark.parametrize("blank_value", [None, "", " "])
def test_execution_fact_provider_keeps_blank_actual_times_optional(blank_value) -> None:
    fact = _fact_from_actual_times(blank_value, blank_value)

    assert fact.actual_start_time is None
    assert fact.actual_end_time is None


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2026/05/01T08:10", datetime(2026, 5, 1, 8, 10)),
        ("2026-05-01", datetime(2026, 5, 1)),
        ("2026-05-01 08:10:30", datetime(2026, 5, 1, 8, 10, 30)),
        ("2026-05-01 08：10", datetime(2026, 5, 1, 8, 10)),
        (datetime(2026, 5, 1, 8, 10, 30, 123456), datetime(2026, 5, 1, 8, 10, 30)),
    ],
)
def test_execution_fact_provider_parses_valid_actual_times_like_operation_event_time(raw_value, expected) -> None:
    fact = _fact_from_actual_times(raw_value)

    assert fact.actual_start_time == expected


@pytest.mark.parametrize("bad_value", ["not-a-date", "2026-02-30 08:10:00", "2026-05-01 08:10:00.123456", 0, False])
def test_execution_fact_provider_rejects_bad_actual_time_loudly(bad_value) -> None:
    with pytest.raises(ValueError, match="event_time"):
        _fact_from_actual_times(bad_value)


def test_execution_snapshot_revision_includes_plan_identity() -> None:
    base = {
        "op_id": 10,
        "batch_id": "B1",
        "actual_status": "not_started",
        "actual_start_time": None,
        "actual_end_time": None,
        "actual_machine_id": None,
        "actual_operator_id": None,
        "state_revision": "10:0:0",
        "source_table": "schedule",
        "effective_plan_role": "adopted",
        "scenario_id": None,
    }
    v1 = build_execution_snapshot(
        {10: ExecutionFact(schedule_version=1, schedule_id=100, **base)},
        [10],
    )
    v2 = build_execution_snapshot(
        {10: ExecutionFact(schedule_version=2, schedule_id=200, **base)},
        [10],
    )

    assert v1.revision != v2.revision
    assert "schedule=100" in v1.identity_revisions[10]
    assert "schedule=200" in v2.identity_revisions[10]


def test_execution_snapshot_sorts_and_dedupes_op_ids_for_stable_revision() -> None:
    def fact(op_id: int) -> ExecutionFact:
        return ExecutionFact(
            op_id=op_id,
            batch_id=f"B{op_id}",
            actual_status="not_started",
            actual_start_time=None,
            actual_end_time=None,
            actual_machine_id=None,
            actual_operator_id=None,
            state_revision=f"{op_id}:0:0",
            schedule_version=1,
            schedule_id=100 + op_id,
            source_table="schedule",
            effective_plan_role="adopted",
            scenario_id=None,
        )

    facts = {op_id: fact(op_id) for op_id in (1, 2, 3)}
    messy_ids = [3, 1, 2, 1, 0, -1, "x", None]
    ordered = build_execution_snapshot(facts, [1, 2, 3])
    messy = build_execution_snapshot(facts, messy_ids)

    assert positive_op_ids(messy_ids) == [1, 2, 3]
    assert positive_op_ids([]) == []
    assert positive_op_ids(None) == []
    assert messy.op_ids == [1, 2, 3]
    assert messy.revision == ordered.revision


def test_execution_snapshot_rejects_fact_without_plan_identity() -> None:
    fact = ExecutionFact(
        op_id=10,
        batch_id="B1",
        actual_status="not_started",
        actual_start_time=None,
        actual_end_time=None,
        actual_machine_id=None,
        actual_operator_id=None,
        state_revision="10:0:0",
    )

    with pytest.raises(ValueError, match="schedule_version"):
        build_execution_snapshot({10: fact}, [10])


def test_execution_identity_carriers_require_explicit_plan_identity() -> None:
    with pytest.raises(TypeError, match="requested_plan_role"):
        ExecutionFeedbackContext(
            schedule_version=1,
            schedule_id=100,
            op_id=10,
            batch_id="B1",
            expected_state_revision="10:0:0",
            created_by="张三",
            idempotency_key="missing-plan-identity",
        )
    with pytest.raises(TypeError, match="requested_plan_role"):
        TaskRef(
            task_code="缺身份任务",
            schedule_version=2,
            schedule_id=100,
            op_id=10,
            batch_id="B1",
            op_name="OP10",
            planned_machine_id="M1",
            planned_machine_label="一号设备",
            planned_operator_id="O1",
            planned_operator_label="张三",
            state=OperationExecutionState(op_id=10, batch_id="B1"),
        )


def test_current_event_list_ignores_superseded_same_op_feedback(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_legacy_v1_start(db_path)
    client = app.test_client()
    card = _current_card(client)

    resp = client.get(_events_url(card))
    payload = _json(resp)

    assert resp.status_code == 200
    assert payload["data"]["events"] == []
    assert payload["data"]["task_card"]["current_status_label"] == "待开工"


def test_event_list_requires_full_task_identity(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(f"/scheduler/resource-dispatch/execution/10/events?{_current_query()}")
    payload = _json(resp)

    assert resp.status_code == 400
    assert payload["error"]["details"]["reason"] == "missing_required_field"


def test_event_list_requires_explicit_plan_query_identity(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, idempotency_key="event-read-query-identity"),
    )
    assert start.status_code == 200

    resp = client.get(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/events"
        "?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01"
        f"&date_from=2026-05-01&date_to=2026-05-07&schedule_id={card['schedule_id']}&batch_id={card['batch_id']}"
    )
    payload = _json(resp)

    assert resp.status_code == 400
    assert payload["error"]["details"]["field"] == "plan_identity"
    assert set(payload["error"]["details"]["missing_fields"]) == {"version", "plan_role"}


def test_current_actual_write_validation_ignores_superseded_same_op_feedback(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _insert_legacy_v1_start(db_path)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/tasks/{card['task_key']}/actual?{_current_query()}",
        json=_base_payload(
            card,
            actual_start_time="2026-05-01 08:20:00",
            idempotency_key="current-actual-ignores-history",
        ),
    )
    payload = _json(resp)

    assert resp.status_code == 200
    assert payload["data"]["task_card"]["actual_start_time"] == "2026-05-01 08:20:00"
    assert _event_count(db_path) == 2


def test_execution_review_export_labels_superseded_adopted_version(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(
        "/reports/execution-review/export"
        "?version=1&date_from=2026-04-30&date_to=2026-04-30&batch_id=B1"
    )
    disposition = unquote(resp.headers.get("Content-Disposition", ""))

    assert resp.status_code == 200
    assert "历史正式方案" in disposition
    assert "计划和现场实际-正式采用方案-v1" not in disposition
    wb = openpyxl.load_workbook(BytesIO(resp.data), data_only=True)
    try:
        summary = _summary_dict(wb)
        assert "历史正式方案" in str(summary["方案"])
        assert summary["方案"] != "正式采用方案"
    finally:
        wb.close()
