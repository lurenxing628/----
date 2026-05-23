from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    SchedulePlanQueryService,
)
from data.repositories.schedule_candidate_repo import ScheduleCandidateRepository
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 7


def _require_id(value) -> int:
    assert value is not None
    return int(value)


def _seed_plan_role_context(
    conn,
    *,
    due_date: str = "2026-05-20",
    candidate_start: str = "2026-05-12 13:00:00",
    candidate_end: str = "2026-05-13 15:00:00",
    result_summary=None,
) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M-ADOPTED', '正式设备', 'active'), ('M-CANDIDATE', '候选设备', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O-ADOPTED', '正式人员', 'active'), ('O-CANDIDATE', '候选人员', 'active');

        INSERT INTO Parts(part_no, part_name, route_parsed)
        VALUES ('P001', '零件一', 'yes');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 1, '2026-05-20', 'urgent', 'yes', 'scheduled');

        INSERT INTO BatchOperations(op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status)
        VALUES ('OP-B1-10', 'B1', 'piece-a', 10, '车削', 'internal', 'M-ADOPTED', 'O-ADOPTED', 'scheduled');
        """
    )
    conn.execute("UPDATE Batches SET due_date = ? WHERE batch_id = 'B1'", (due_date,))
    op_id = int(conn.execute("SELECT id FROM BatchOperations WHERE op_code='OP-B1-10'").fetchone()["id"])
    conn.execute(
        """
        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, op_id, "M-ADOPTED", "O-ADOPTED", "2026-05-11 08:00:00", "2026-05-11 10:00:00", "locked", VERSION),
    )
    conn.execute(
        """
        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            VERSION,
            "greedy",
            1,
            1,
            "success",
            json.dumps(result_summary if result_summary is not None else {"overdue_batches": []}, ensure_ascii=False),
            "pytest",
        ),
    )

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
            candidate_label="候选代表",
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
                op_id=op_id,
                machine_id="M-CANDIDATE",
                operator_id="O-CANDIDATE",
                start_time=candidate_start,
                end_time=candidate_end,
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


def _build_app(
    tmp_path,
    monkeypatch,
    *,
    due_date: str = "2026-05-20",
    candidate_start: str = "2026-05-12 13:00:00",
    candidate_end: str = "2026-05-13 15:00:00",
    result_summary=None,
):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    db_path = tmp_path / "aps_test.db"
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
        _seed_plan_role_context(
            conn,
            due_date=due_date,
            candidate_start=candidate_start,
            candidate_end=candidate_end,
            result_summary=result_summary,
        )
        conn.commit()
    finally:
        conn.close()

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _build_empty_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    db_path = tmp_path / "aps_empty.db"
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
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_gantt_data_reads_candidate_rows_and_returns_plan_role_metadata(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    payload = resp.get_json()
    data = payload.get("data") or {}
    tasks = data.get("tasks") or []

    assert resp.status_code == 200
    assert payload.get("success") is True
    assert data.get("requested_plan_role") == ROLE_BASELINE_BEST
    assert data.get("effective_plan_role") == ROLE_BASELINE_BEST
    assert (data.get("plan_role_resolution") or {}).get("is_comparison") is True
    assert (data.get("plan_role_resolution") or {}).get("source_table") == SOURCE_CANDIDATE_ROWS
    assert (data.get("version_time_span") or {}).get("start_date") == "2026-05-12"
    assert len(tasks) == 1
    assert (tasks[0].get("meta") or {}).get("machine_id") == "M-CANDIDATE"
    assert (tasks[0].get("meta") or {}).get("operator_id") == "O-CANDIDATE"
    assert (data.get("critical_chain") or {}).get("makespan_end") == "2026-05-13 15:00:00"
    assert (data.get("critical_chain") or {}).get("cache_hit") is False


def test_gantt_candidate_critical_chain_unavailable_uses_public_contract(tmp_path, monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    def _candidate_chain_unavailable(_rows):
        return {
            "available": False,
            "reason": "rows_exception",
            "ids": ["INTERNAL-CANDIDATE-ID"],
            "edges": [{"from": "A", "to": "B"}],
            "edge_count": 1,
            "edge_type_stats": {"process": 1},
        }

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _candidate_chain_unavailable)

    resp = client.get(f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    payload = resp.get_json()
    data = payload.get("data") or {}
    critical_chain = data.get("critical_chain") or {}

    assert resp.status_code == 200
    assert payload.get("success") is True
    assert critical_chain.get("available") is False
    assert critical_chain.get("reason_code") == "rows_exception"
    assert critical_chain.get("reason") == "关键链计算异常"
    assert critical_chain.get("ids") == []
    assert critical_chain.get("edges") == []
    assert critical_chain.get("edge_count") == 0
    assert critical_chain.get("edge_type_stats") == {}
    assert critical_chain.get("cache_hit") is False
    assert "INTERNAL-CANDIDATE-ID" not in str(data)
    assert data.get("degraded") is True
    events = list(data.get("degradation_events") or ())
    assert any(str(event.get("code") or "").strip() == "critical_chain_unavailable" for event in events), events


def test_gantt_candidate_rows_load_failure_uses_public_critical_chain_contract(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    def _raise_rows_load_failure(self, *, version: int, source_table: str, candidate_id):
        raise RuntimeError("candidate rows load failed")

    monkeypatch.setattr(
        SchedulePlanQueryService,
        "list_plan_detail_rows_all_for_resolution",
        _raise_rows_load_failure,
    )

    resp = client.get(f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    payload = resp.get_json()
    data = payload.get("data") or {}
    critical_chain = data.get("critical_chain") or {}

    assert resp.status_code == 200
    assert payload.get("success") is True
    assert critical_chain.get("available") is False
    assert critical_chain.get("reason_code") == "rows_load_exception"
    assert critical_chain.get("reason") == "关键链数据读取异常"
    assert critical_chain.get("ids") == []
    assert critical_chain.get("edges") == []
    assert critical_chain.get("edge_count") == 0
    assert critical_chain.get("edge_type_stats") == {}
    assert critical_chain.get("cache_hit") is False
    assert "candidate rows load failed" not in str(data)
    assert data.get("degraded") is True
    events = list(data.get("degradation_events") or ())
    assert any(str(event.get("code") or "").strip() == "critical_chain_unavailable" for event in events), events


def test_gantt_missing_valid_plan_role_falls_back_to_adopted(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role={ROLE_CRITICAL_BEST}")
    data = (resp.get_json() or {}).get("data") or {}
    tasks = data.get("tasks") or []

    assert resp.status_code == 200
    assert data.get("requested_plan_role") == ROLE_CRITICAL_BEST
    assert data.get("effective_plan_role") == ROLE_ADOPTED
    assert (data.get("plan_role_resolution") or {}).get("is_fallback") is True
    assert "最终采用方案" in str(data.get("plan_role_message") or "")
    assert len(tasks) == 1
    assert (tasks[0].get("meta") or {}).get("machine_id") == "M-ADOPTED"


def test_plan_role_same_as_adopted_is_not_marked_as_comparison(tmp_path) -> None:
    db_path = tmp_path / "aps_test.db"
    ensure_schema(str(db_path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(db_path))
    try:
        _seed_plan_role_context(conn)
        repo = ScheduleCandidateRepository(conn)

        adopted_id = conn.execute(
            """
            SELECT candidate_id
            FROM ScheduleCandidateSelection
            WHERE version = ? AND role = ?
            """,
            (VERSION, ROLE_ADOPTED),
        ).fetchone()["candidate_id"]

        conn.execute(
            "DELETE FROM ScheduleCandidateSelection WHERE version = ? AND role = ?",
            (VERSION, ROLE_BASELINE_BEST),
        )
        repo.create_selection(
            ScheduleCandidateSelection(
                id=None,
                version=VERSION,
                role=ROLE_BASELINE_BEST,
                candidate_id=int(adopted_id),
                source_table=SOURCE_SCHEDULE,
            )
        )
        conn.commit()

        resolution = SchedulePlanQueryService(conn).resolve_plan(VERSION, ROLE_BASELINE_BEST).to_dict()

        assert resolution["selected_role"] == ROLE_BASELINE_BEST
        assert resolution["source_table"] == SOURCE_SCHEDULE
        assert resolution["is_comparison"] is False
    finally:
        conn.close()


def test_gantt_page_and_boot_preserve_plan_role(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(f"/scheduler/gantt?version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    html = resp.get_data(as_text=True)
    boot_js = (REPO_ROOT / "static/js/gantt_boot.js").read_text(encoding="utf-8")

    assert resp.status_code == 200
    assert 'name="plan_role"' in html
    assert 'data-plan-role="baseline_best"' in html
    assert "plan_role=baseline_best" in html
    assert "对比方案" in html
    assert "planRole: ds.planRole" in boot_js
    assert 'url.searchParams.set("plan_role", String(cfg.planRole))' in boot_js


def test_gantt_candidate_plan_overdue_markers_are_computed_from_candidate_rows(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, due_date="2026-05-12")
    client = app.test_client()

    resp = client.get(f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    data = (resp.get_json() or {}).get("data") or {}
    tasks = data.get("tasks") or []

    assert resp.status_code == 200
    assert data.get("effective_plan_role") == ROLE_BASELINE_BEST
    assert data.get("overdue_markers_degraded") is False
    assert len(tasks) == 1
    assert (tasks[0].get("meta") or {}).get("batch_id") == "B1"
    assert (tasks[0].get("meta") or {}).get("is_overdue") is True
    assert "overdue" in str(tasks[0].get("custom_class") or "")


def test_gantt_candidate_plan_overdue_markers_do_not_reuse_adopted_history(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, result_summary={"overdue_batches": ["B1"]})
    client = app.test_client()

    resp = client.get(f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    data = (resp.get_json() or {}).get("data") or {}
    tasks = data.get("tasks") or []

    assert resp.status_code == 200
    assert data.get("effective_plan_role") == ROLE_BASELINE_BEST
    assert data.get("overdue_markers_degraded") is False
    assert len(tasks) == 1
    assert (tasks[0].get("meta") or {}).get("batch_id") == "B1"
    assert (tasks[0].get("meta") or {}).get("is_overdue") is False
    assert "overdue" not in str(tasks[0].get("custom_class") or "")


def test_gantt_non_adopted_schedule_source_overdue_markers_use_adopted_history(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, result_summary={"overdue_batches": ["B1"]})
    db_path = tmp_path / "aps_test.db"
    conn = get_connection(str(db_path))
    try:
        conn.execute(
            """
            UPDATE ScheduleCandidateSelection
               SET source_table = ?
             WHERE version = ? AND role = ?
            """,
            (SOURCE_SCHEDULE, VERSION, ROLE_BASELINE_BEST),
        )
        conn.commit()
    finally:
        conn.close()
    client = app.test_client()

    resp = client.get(f"/scheduler/gantt/data?view=machine&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    data = (resp.get_json() or {}).get("data") or {}
    tasks = data.get("tasks") or []
    plan_resolution = data.get("plan_role_resolution") or {}

    assert resp.status_code == 200
    assert data.get("effective_plan_role") == ROLE_BASELINE_BEST
    assert plan_resolution.get("source_table") == SOURCE_SCHEDULE
    assert plan_resolution.get("is_comparison") is False
    assert data.get("overdue_markers_degraded") is False
    assert len(tasks) == 1
    assert (tasks[0].get("meta") or {}).get("machine_id") == "M-ADOPTED"
    assert (tasks[0].get("meta") or {}).get("batch_id") == "B1"
    assert (tasks[0].get("meta") or {}).get("is_overdue") is True
    assert "overdue" in str(tasks[0].get("custom_class") or "")


def test_gantt_page_rejects_unknown_plan_role_without_history(tmp_path, monkeypatch) -> None:
    app = _build_empty_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/scheduler/gantt?plan_role=evil")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 400
    assert "排产方案不正确" in html
