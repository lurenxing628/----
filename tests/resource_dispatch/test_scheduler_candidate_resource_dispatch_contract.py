"""回归测试：ResourceDispatchService 按请求的 plan_role 读对应候选方案（baseline_best 读候选行、无此角色时回退 adopted 并标记 fallback_to_adopted），超期标记从候选行自身计算而不复用 adopted 历史，页面/数据/导出接口在 URL 与日志中保留 plan_role、对外 JSON 不泄露 schedule_id/op_id/source_table 等内部键；并钉住执行上下文写闸查询侧 can_write_feedback 与 feedback_write_enabled 的同源锁步不变式（N1）。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from urllib.parse import unquote

import pytest
from flask import Flask, g

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST
from data.repositories.schedule_candidate_repo import ScheduleCandidateRepository
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from tests._support.paths import REPO_ROOT

VERSION = 7


def _connect_fresh_schema(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _require_id(value: Any) -> int:
    assert value is not None
    return int(value)


def _seed_schedule_context(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO ResourceTeams(team_id, name, status)
        VALUES ('T-ADOPTED', '最终班组', 'active'), ('T-CANDIDATE', '候选班组', 'active');

        INSERT INTO Machines(machine_id, name, status, team_id)
        VALUES ('M-ADOPTED', '最终设备', 'active', 'T-ADOPTED'), ('M-CANDIDATE', '候选设备', 'active', 'T-CANDIDATE');

        INSERT INTO Operators(operator_id, name, status, team_id)
        VALUES ('O-ADOPTED', '最终人员', 'active', 'T-ADOPTED'), ('O-CANDIDATE', '候选人员', 'active', 'T-CANDIDATE');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 1, '2026-05-03', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(
            id, op_code, batch_id, piece_id, seq, op_type_name, source, status
        )
        VALUES (10, 'OP10', 'B1', 'piece-a', 1, '车削', 'internal', 'scheduled');

        INSERT INTO Schedule(
            id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
        )
        VALUES (1, 10, 'M-ADOPTED', 'O-ADOPTED', '2026-05-01 08:00', '2026-05-01 10:00', 'unlocked', 7);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (7, 'greedy', 1, 1, 'success', '{"overdue_batches": []}', 'pytest');
        """
    )


def _seed_candidates(conn: sqlite3.Connection) -> None:
    repo = ScheduleCandidateRepository(conn)
    adopted = repo.create_candidate(
        ScheduleCandidate(
            id=None,
            version=VERSION,
            candidate_key="adopted",
            candidate_label="最终采用",
            candidate_kind="baseline",
            status="completed",
            graph_enabled="no",
            detail_saved="no",
        )
    )
    baseline = repo.create_candidate(
        ScheduleCandidate(
            id=None,
            version=VERSION,
            candidate_key="baseline_best",
            candidate_label="原算法最好候选",
            candidate_kind="baseline",
            status="completed",
            graph_enabled="no",
            detail_saved="yes",
        )
    )
    baseline_id = _require_id(baseline.id)
    repo.bulk_create_candidate_rows(
        [
            ScheduleCandidateRows(
                id=None,
                version=VERSION,
                candidate_id=baseline_id,
                op_id=10,
                machine_id="M-CANDIDATE",
                operator_id="O-CANDIDATE",
                start_time="2026-05-01 13:00",
                end_time="2026-05-01 15:00",
                lock_status="locked",
            )
        ]
    )
    repo.create_selection(
        ScheduleCandidateSelection(
            id=None,
            version=VERSION,
            role=ROLE_ADOPTED,
            candidate_id=_require_id(adopted.id),
            source_table=SOURCE_SCHEDULE,
        )
    )
    repo.create_selection(
        ScheduleCandidateSelection(
            id=None,
            version=VERSION,
            role=ROLE_BASELINE_BEST,
            candidate_id=baseline_id,
            source_table=SOURCE_CANDIDATE_ROWS,
        )
    )


def _seed_db(tmp_path: Path) -> sqlite3.Connection:
    conn = _connect_fresh_schema(tmp_path)
    _seed_schedule_context(conn)
    _seed_candidates(conn)
    conn.commit()
    return conn


def _add_second_adopted_task(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B2', 'P001', '零件一', 1, '2026-05-04', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(
            id, op_code, batch_id, piece_id, seq, op_type_name, source, status
        )
        VALUES (20, 'OP20', 'B2', 'piece-b', 1, '铣削', 'internal', 'scheduled');

        INSERT INTO Schedule(
            id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
        )
        VALUES (2, 20, 'M-ADOPTED', 'O-ADOPTED', '2026-05-01 11:00', '2026-05-01 12:00', 'unlocked', 7);
        """
    )
    conn.commit()


def _build_route_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test"
    app.add_url_rule("/scheduler/resource-dispatch", endpoint="scheduler.resource_dispatch_page", view_func=lambda: "")
    app.add_url_rule("/scheduler/resource-dispatch/data", endpoint="scheduler.resource_dispatch_data", view_func=lambda: "")
    app.add_url_rule(
        "/scheduler/resource-dispatch/execution/data",
        endpoint="scheduler.resource_dispatch_execution_data",
        view_func=lambda: "",
    )
    app.add_url_rule(
        "/scheduler/resource-dispatch/execution/actual-template",
        endpoint="scheduler.resource_dispatch_actual_template",
        view_func=lambda: "",
    )
    app.add_url_rule(
        "/scheduler/resource-dispatch/execution/import",
        endpoint="scheduler.resource_dispatch_actual_import",
        view_func=lambda: "",
    )
    app.add_url_rule("/scheduler/resource-dispatch/export", endpoint="scheduler.resource_dispatch_export", view_func=lambda: "")
    return app


def _json_data(resp) -> Dict[str, Any]:
    return json.loads(resp.data.decode("utf-8") or "{}").get("data") or {}


def _json_key_hits(value: Any, forbidden_keys: set) -> List[str]:
    hits: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden_keys:
                hits.append(key)
            hits.extend(_json_key_hits(child, forbidden_keys))
    elif isinstance(value, list):
        for child in value:
            hits.extend(_json_key_hits(child, forbidden_keys))
    return hits


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def test_resource_dispatch_service_reads_requested_candidate_plan_and_falls_back_to_adopted(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        from core.services.scheduler.resource_dispatch_service import ResourceDispatchService

        svc = ResourceDispatchService(conn, logger=None, op_logger=None)
        baseline = svc.get_dispatch_payload(
            scope_type="operator",
            operator_id="O-CANDIDATE",
            period_preset="week",
            query_date="2026-05-01",
            version=VERSION,
            plan_role=ROLE_BASELINE_BEST,
        )
        baseline_filters = baseline.get("filters") or {}
        assert baseline_filters.get("requested_plan_role") == ROLE_BASELINE_BEST
        assert baseline_filters.get("effective_plan_role") == ROLE_BASELINE_BEST
        assert "正式采用方案" in str(baseline.get("plan_role_notice") or "")
        assert (baseline.get("detail_rows") or [])[0].get("operator_id") == "O-CANDIDATE"
        assert (baseline.get("detail_rows") or [])[0].get("machine_id") == "M-CANDIDATE"

        fallback = svc.get_dispatch_payload(
            scope_type="operator",
            operator_id="O-ADOPTED",
            period_preset="week",
            query_date="2026-05-01",
            version=VERSION,
            plan_role=ROLE_CRITICAL_BEST,
        )
        fallback_filters = fallback.get("filters") or {}
        assert fallback_filters.get("requested_plan_role") == ROLE_CRITICAL_BEST
        assert fallback_filters.get("effective_plan_role") == ROLE_ADOPTED
        assert fallback_filters.get("plan_role_status") == "fallback_to_adopted"
        assert "正式采用方案" in str(fallback.get("plan_role_notice") or "")
        assert (fallback.get("detail_rows") or [])[0].get("operator_id") == "O-ADOPTED"
    finally:
        conn.close()


def test_resource_dispatch_candidate_overdue_markers_are_computed_from_candidate_rows(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute("UPDATE Batches SET due_date = '2026-05-02' WHERE batch_id = 'B1'")
        conn.execute(
            """
            UPDATE ScheduleCandidateRows
               SET start_time = '2026-05-03 13:00',
                   end_time = '2026-05-03 15:00'
             WHERE version = ? AND op_id = 10
            """,
            (VERSION,),
        )
        conn.commit()

        from core.services.scheduler.resource_dispatch_service import ResourceDispatchService

        svc = ResourceDispatchService(conn, logger=None, op_logger=None)
        payload = svc.get_dispatch_payload(
            scope_type="operator",
            operator_id="O-CANDIDATE",
            period_preset="week",
            query_date="2026-05-01",
            version=VERSION,
            plan_role=ROLE_BASELINE_BEST,
        )

        detail_rows = payload.get("detail_rows") or []
        assert (payload.get("filters") or {}).get("effective_plan_role") == ROLE_BASELINE_BEST
        assert payload.get("overdue_markers_degraded") is False
        assert len(detail_rows) == 1
        assert detail_rows[0].get("batch_id") == "B1"
        assert detail_rows[0].get("is_overdue") is True
        assert (payload.get("summary") or {}).get("overdue_count") == 1
    finally:
        conn.close()


def test_resource_dispatch_candidate_overdue_markers_do_not_reuse_adopted_history(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute(
            """
            UPDATE ScheduleHistory
               SET result_summary = '{"overdue_batches": ["B1"]}'
             WHERE version = ?
            """,
            (VERSION,),
        )
        conn.commit()

        from core.services.scheduler.resource_dispatch_service import ResourceDispatchService

        svc = ResourceDispatchService(conn, logger=None, op_logger=None)
        payload = svc.get_dispatch_payload(
            scope_type="operator",
            operator_id="O-CANDIDATE",
            period_preset="week",
            query_date="2026-05-01",
            version=VERSION,
            plan_role=ROLE_BASELINE_BEST,
        )

        detail_rows = payload.get("detail_rows") or []
        assert (payload.get("filters") or {}).get("effective_plan_role") == ROLE_BASELINE_BEST
        assert payload.get("overdue_markers_degraded") is False
        assert len(detail_rows) == 1
        assert detail_rows[0].get("batch_id") == "B1"
        assert detail_rows[0].get("is_overdue") is False
        assert (payload.get("summary") or {}).get("overdue_count") == 0
    finally:
        conn.close()


def test_resource_dispatch_non_adopted_schedule_source_overdue_markers_use_adopted_history(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute(
            """
            UPDATE ScheduleHistory
               SET result_summary = '{"overdue_batches": ["B1"]}'
             WHERE version = ?
            """,
            (VERSION,),
        )
        conn.execute(
            """
            UPDATE ScheduleCandidateSelection
               SET source_table = ?
             WHERE version = ? AND role = ?
            """,
            (SOURCE_SCHEDULE, VERSION, ROLE_BASELINE_BEST),
        )
        conn.commit()

        from core.services.scheduler.resource_dispatch_service import ResourceDispatchService

        svc = ResourceDispatchService(conn, logger=None, op_logger=None)
        payload = svc.get_dispatch_payload(
            scope_type="operator",
            operator_id="O-ADOPTED",
            period_preset="week",
            query_date="2026-05-01",
            version=VERSION,
            plan_role=ROLE_BASELINE_BEST,
        )

        filters = payload.get("filters") or {}
        detail_rows = payload.get("detail_rows") or []
        assert filters.get("effective_plan_role") == ROLE_BASELINE_BEST
        assert filters.get("source_table") == SOURCE_SCHEDULE
        assert filters.get("is_comparison") is True
        assert payload.get("overdue_markers_degraded") is False
        assert len(detail_rows) == 1
        assert detail_rows[0].get("operator_id") == "O-ADOPTED"
        assert detail_rows[0].get("batch_id") == "B1"
        assert detail_rows[0].get("is_overdue") is True
        assert (payload.get("summary") or {}).get("overdue_count") == 1
    finally:
        conn.close()


def test_resource_dispatch_batch_id_filters_dispatch_and_execution_rows(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        _add_second_adopted_task(conn)

        from core.services.scheduler.resource_dispatch_execution_service import ResourceDispatchExecutionService
        from core.services.scheduler.resource_dispatch_service import ResourceDispatchService

        dispatch_payload = ResourceDispatchService(conn, logger=None, op_logger=None).get_dispatch_payload(
            scope_type="operator",
            operator_id="O-ADOPTED",
            period_preset="week",
            query_date="2026-05-01",
            version=VERSION,
            plan_role=ROLE_ADOPTED,
            batch_id="B1",
        )

        detail_rows = dispatch_payload.get("detail_rows") or []
        assert (dispatch_payload.get("filters") or {}).get("batch_id") == "B1"
        assert [row.get("batch_id") for row in detail_rows] == ["B1"]
        assert (dispatch_payload.get("summary") or {}).get("total_tasks") == 1

        execution_context = ResourceDispatchExecutionService(conn, logger=None, op_logger=None).get_execution_context(
            scope_type="operator",
            operator_id="O-ADOPTED",
            period_preset="week",
            query_date="2026-05-01",
            version=VERSION,
            plan_role=ROLE_ADOPTED,
            batch_id="B1",
        )
        assert [row.get("batch_id") for row in execution_context.get("rows") or []] == ["B1"]
    finally:
        conn.close()


def test_dispatch_repository_pushes_batch_schedule_and_op_filters_to_sql() -> None:
    from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository

    repo = SchedulePlanQueryRepository.__new__(SchedulePlanQueryRepository)
    captured: Dict[str, Any] = {}

    def fake_fetchall(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    repo.fetchall = fake_fetchall  # type: ignore[method-assign]

    repo.list_dispatch_rows(
        version=VERSION,
        source_table=SOURCE_SCHEDULE,
        candidate_id=None,
        start_time="2026-05-01 00:00:00",
        end_time="2026-05-08 00:00:00",
        scope_type="operator",
        scope_id="O-ADOPTED",
        batch_id="B1",
        schedule_id=90,
        op_id=30,
    )

    assert "TRIM(CAST(bo.batch_id AS TEXT)) = ?" in captured["sql"]
    assert "s.id = ?" in captured["sql"]
    assert "s.op_id = ?" in captured["sql"]
    assert captured["params"][-4:] == ("O-ADOPTED", "B1", 90, 30)


def test_dispatch_repository_rejects_invalid_window_params() -> None:
    from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository

    repo = SchedulePlanQueryRepository.__new__(SchedulePlanQueryRepository)
    repo.fetchall = lambda _sql, _params: []  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="派工查询时间写法不对"):
        repo.list_dispatch_rows(
            version=VERSION,
            source_table=SOURCE_SCHEDULE,
            candidate_id=None,
            start_time="not-a-time",
            end_time="2026-05-08 00:00:00",
        )

    with pytest.raises(ValueError, match="派工查询时间写法不对"):
        repo.list_dispatch_rows(
            version=VERSION,
            source_table=SOURCE_SCHEDULE,
            candidate_id=None,
            start_time="2026-05-01 00:00:00",
            end_time="not-a-time",
        )


def test_feedback_task_card_queries_exact_schedule_identity() -> None:
    from core.models.operation_execution_state import OperationExecutionState
    from core.services.scheduler.operation_execution_feedback_support import ExecutionFeedbackContext
    from core.services.scheduler.resource_dispatch_execution_service import ResourceDispatchExecutionService

    calls: List[Dict[str, Any]] = []
    svc = ResourceDispatchExecutionService.__new__(ResourceDispatchExecutionService)
    svc.dispatch_service = SimpleNamespace(_latest_version=lambda: VERSION)
    svc.schedule_repo = SimpleNamespace(
        get=lambda _schedule_id: SimpleNamespace(start_time="2026-05-01 08:00:00", end_time="2026-05-01 12:00:00")
    )

    class _PlanQuery:
        def list_plan_dispatch_rows_for_resolution(self, **kwargs):
            calls.append(kwargs)
            return [
                {
                    "schedule_id": 90,
                    "op_id": 30,
                    "batch_id": "B1",
                    "start_time": "2026-05-01 08:00:00",
                    "end_time": "2026-05-01 12:00:00",
                    "source": "internal",
                }
            ]

    svc.plan_query_service = _PlanQuery()
    context = ExecutionFeedbackContext(
        schedule_version=VERSION,
        schedule_id=90,
        op_id=30,
        batch_id="B1",
        expected_state_revision="rev",
        created_by="pytest",
        idempotency_key="idem",
        requested_plan_role=ROLE_ADOPTED,
        source_table=SOURCE_SCHEDULE,
        effective_plan_role=ROLE_ADOPTED,
    )

    card = svc.task_card_for_feedback_context(context, OperationExecutionState(op_id=30, batch_id="B1"))

    assert card["rows"][0]["schedule_id"] == 90
    assert calls
    assert calls[0]["schedule_id"] == 90
    assert calls[0]["op_id"] == 30
    assert calls[0]["batch_id"] == "B1"


def test_overdue_marker_query_keeps_batch_filter() -> None:
    from core.services.scheduler.resource_dispatch_service import ResourceDispatchService

    calls: List[Dict[str, Any]] = []
    svc = ResourceDispatchService.__new__(ResourceDispatchService)

    class _PlanQuery:
        def list_plan_overdue_base_rows_for_resolution(self, **kwargs):
            calls.append(kwargs)
            return []

    svc.plan_query_service = _PlanQuery()
    svc._load_overdue_meta = lambda _version: {"ids": []}
    svc._log_overdue_marker_degraded = lambda **_kwargs: None

    svc._load_overdue_meta_for_plan(
        version=VERSION,
        role=ROLE_BASELINE_BEST,
        source_table=SOURCE_CANDIDATE_ROWS,
        candidate_id=7,
        batch_id="B1",
    )

    assert calls
    assert calls[0]["batch_id"] == "B1"


def test_execution_error_response_sanitizes_internal_detail_fields() -> None:
    from core.infrastructure.errors import ValidationError
    from web.routes.domains.scheduler.scheduler_resource_dispatch_execution_context import _execution_error_response

    exc = ValidationError(
        "现场记录写入缺少任务定位信息，请刷新资源排班页面后重试。",
        field="schedule_id",
        details={
            "reason": "missing_required_field",
            "missing_fields": ["schedule_id", "op_id", "scenario_id", "start_date"],
            "source_table": SOURCE_SCHEDULE,
            "schedule_id": 90,
            "op_id": 30,
            "scenario_id": "SC-SECRET",
            "nested": {"scenario_id": "SC-NESTED", "safe_label": "可见说明"},
        },
    )

    payload, status = _execution_error_response(exc, action="fill_actual")
    details = (payload.get("error") or {}).get("details") or {}
    payload_text = _json_text(payload)

    assert status == 400
    assert "field" not in details
    assert "missing_fields" not in details
    assert details["field_label"] == "排程记录"
    assert "missing_field_labels" in details
    assert details["nested"] == {"safe_label": "可见说明"}
    for forbidden in ("schedule_id", "op_id", "scenario_id", "source_table", "SC-SECRET", "SC-NESTED"):
        assert forbidden not in payload_text


def test_resource_dispatch_page_data_and_export_keep_plan_role_in_urls_and_log(tmp_path: Path, monkeypatch) -> None:
    conn = _seed_db(tmp_path)
    app = _build_route_app()
    query = (
        "scope_type=operator&operator_id=O-CANDIDATE&period_preset=week"
        f"&query_date=2026-05-01&version={VERSION}&plan_role={ROLE_BASELINE_BEST}"
    )
    try:
        from core.services.scheduler.resource_dispatch_service import ResourceDispatchService
        from web.routes.domains.scheduler import scheduler_resource_dispatch as rd_routes

        captured: Dict[str, Any] = {}

        def _capture_template(template_name: str, **kwargs: Any) -> str:
            captured["template_name"] = template_name
            captured.update(kwargs)
            return "OK"

        monkeypatch.setattr(rd_routes, "render_template", _capture_template)

        with app.test_request_context(f"/scheduler/resource-dispatch?{query}"):
            g.services = SimpleNamespace(resource_dispatch_service=ResourceDispatchService(conn, logger=None, op_logger=None))
            page_result = rd_routes.resource_dispatch_page()

        assert page_result == "OK"
        assert captured["template_name"] == "scheduler/resource_dispatch.html"
        assert "plan_role=baseline_best" in str(captured.get("data_url") or "")
        assert "plan_role=baseline_best" in str(captured.get("export_url") or "")
        assert "只用来和正式采用方案比一比" in str(captured.get("plan_role_notice") or "")
        assert (captured.get("filters") or {}).get("requested_plan_role") == ROLE_BASELINE_BEST

        with app.test_request_context(f"/scheduler/resource-dispatch/data?{query}"):
            g.services = SimpleNamespace(resource_dispatch_service=ResourceDispatchService(conn, logger=None, op_logger=None))
            data_resp = rd_routes.resource_dispatch_data()

        assert data_resp.status_code == 200
        data = _json_data(data_resp)
        filters = data.get("filters") or {}
        assert "requested_plan_role" not in filters
        assert "effective_plan_role" not in filters
        assert "plan_role_status" not in filters
        assert _json_key_hits(data, {"schedule_id", "op_id", "_row_identity", "source_table"}) == []
        assert (data.get("detail_rows") or [])[0].get("current_resource_label") == "O-CANDIDATE 候选人员"

        export_logs: List[Dict[str, Any]] = []

        def _capture_export_log(**kwargs: Any) -> None:
            export_logs.append(kwargs)

        monkeypatch.setattr(rd_routes, "log_excel_export", _capture_export_log)
        with app.test_request_context(f"/scheduler/resource-dispatch/export?{query}"):
            g.services = SimpleNamespace(resource_dispatch_service=ResourceDispatchService(conn, logger=None, op_logger=None))
            g.op_logger = None
            export_resp = rd_routes.resource_dispatch_export()

        assert export_resp.status_code == 200
        assert "原算法代表方案" in unquote(str(export_resp.headers.get("Content-Disposition") or ""))
        assert export_logs
        logged_filters = export_logs[0].get("filters") or {}
        assert logged_filters.get("requested_plan_role") == ROLE_BASELINE_BEST
        assert logged_filters.get("effective_plan_role") == ROLE_BASELINE_BEST
        assert logged_filters.get("plan_role_status") == "resolved_comparison"
        assert logged_filters.get("candidate_key") == "baseline_best"
    finally:
        conn.close()


def test_execution_context_feedback_write_enabled_stays_lockstep_with_can_write_feedback(tmp_path: Path) -> None:
    # N1 同源守卫:get_execution_context 输出的 feedback_write_enabled 与 can_write_feedback
    # 在 service 侧取自同一个 plan_role_fields["can_write_feedback"],必须永远同值。
    # 该不变式是 R08 删除"can_write=True 而 write_enabled=False"死分支的安全前提;
    # 真正写闸在 OperationExecutionFeedbackService._load_current_official_schedule 双 raise,
    # 这两个键只是查询侧优化短路,谁单边改动谁就复活了已死的组合分支。
    conn = _seed_db(tmp_path)
    try:
        from core.services.scheduler.resource_dispatch_execution_service import ResourceDispatchExecutionService

        svc = ResourceDispatchExecutionService(conn, logger=None, op_logger=None)
        for role, expected_writable in ((ROLE_ADOPTED, True), (ROLE_BASELINE_BEST, False)):
            context = svc.get_execution_context(
                scope_type="operator",
                operator_id="O-ADOPTED",
                period_preset="week",
                query_date="2026-05-01",
                version=VERSION,
                plan_role=role,
            )
            assert "can_write_feedback" in context and "feedback_write_enabled" in context
            assert context["can_write_feedback"] is expected_writable
            assert context["feedback_write_enabled"] is context["can_write_feedback"]
    finally:
        conn.close()
