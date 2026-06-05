"""回归测试：周计划页/导出对候选方案 plan_role 的解析与透传——_plan_context_from_data 在请求 role 不可用时回退 adopted 并标记 fallback、保留既有 plan_role_resolution；/scheduler/week-plan?plan_role=baseline_best 从 ScheduleCandidateRows 取候选设备/人员并在各导航链接保留 plan_role，缺失 role 只显示回退提示；导出文件名按方案命名、非正式方案插“查询摘要”页，并把 requested/effective plan_role 与 candidate_key 写入 OperationLogs。"""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path
from urllib.parse import unquote

import openpyxl

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST
from data.repositories.schedule_candidate_repo import ScheduleCandidateRepository
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from web.routes.domains.scheduler.scheduler_week_plan import _plan_context_from_data

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 7


def _require_id(value) -> int:
    assert value is not None
    return int(value)


def _seed_plan_role_context(conn) -> None:
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
        (VERSION, "greedy", 1, 1, "success", json.dumps({"overdue_batches": []}, ensure_ascii=False), "pytest"),
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
                start_time="2026-05-12 13:00:00",
                end_time="2026-05-13 15:00:00",
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


def _build_app(tmp_path, monkeypatch):
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
        _seed_plan_role_context(conn)
        conn.commit()
    finally:
        conn.close()

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), db_path


def test_week_plan_fallback_context_uses_common_plan_resolution_fields() -> None:
    resolution = _plan_context_from_data({"version": VERSION}, ROLE_CRITICAL_BEST)

    assert resolution["version"] == VERSION
    assert resolution["requested_role"] == ROLE_CRITICAL_BEST
    assert resolution["selected_role"] == ROLE_ADOPTED
    assert resolution["source_table"] == SOURCE_SCHEDULE
    assert resolution["candidate_id"] is None
    assert resolution["candidate_key"] is None
    assert resolution["status"] == "fallback_to_adopted"
    assert resolution["is_fallback"] is True
    assert resolution["is_comparison"] is True


def test_week_plan_context_keeps_existing_plan_resolution_dict() -> None:
    existing = {
        "version": VERSION,
        "requested_role": ROLE_BASELINE_BEST,
        "selected_role": ROLE_BASELINE_BEST,
        "source_table": SOURCE_CANDIDATE_ROWS,
        "candidate_id": 12,
        "candidate_key": "baseline_best",
        "status": "scenario_preview",
        "message": "当前正在预览模拟方案，正式计划还没有改变。",
        "is_fallback": False,
        "is_comparison": True,
        "is_scenario_preview": True,
        "scenario_id": "scenario-001",
        "scenario_name": "晚班模拟",
        "scenario_display_name": "晚班模拟",
    }

    resolution = _plan_context_from_data({"version": VERSION, "plan_role_resolution": existing}, ROLE_CRITICAL_BEST)

    assert {key: resolution.get(key) for key in existing} == existing


def test_week_plan_page_uses_candidate_rows_and_export_url_preserves_plan_role(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(f"/scheduler/week-plan?week_start=2026-05-11&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'name="plan_role"' in html
    assert "候选设备" in html
    assert "候选人员" in html
    assert "plan_role=baseline_best" in html
    assert f"/scheduler/resource-dispatch?version={VERSION}&amp;plan_role={ROLE_BASELINE_BEST}" in html
    assert f"/scheduler/gantt?view=machine&amp;version={VERSION}&amp;plan_role={ROLE_BASELINE_BEST}" in html
    assert f"/scheduler/gantt?view=operator&amp;version={VERSION}&amp;plan_role={ROLE_BASELINE_BEST}" in html
    assert f"/scheduler/analysis?version={VERSION}&amp;plan_role={ROLE_BASELINE_BEST}" in html
    assert f"/scheduler/week-plan?version={VERSION}&amp;plan_role={ROLE_BASELINE_BEST}" in html
    assert "当前查看的是“原算法代表方案”" in html
    assert "这是一套对比参考方案" in html
    assert "当前周计划正在预览" not in html


def test_week_plan_missing_valid_plan_role_page_only_shows_fallback_notice(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(f"/scheduler/week-plan?week_start=2026-05-11&version={VERSION}&plan_role={ROLE_CRITICAL_BEST}")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "你原本选择的是“重点工序优先代表方案”" in html
    assert "已显示正式采用方案" in html
    assert "这套结果只用来对照查看" not in html
    assert "这是一套对比参考方案" not in html


def test_week_plan_export_uses_same_plan_role_and_logs_requested_effective_roles(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(f"/scheduler/week-plan/export?week_start=2026-05-11&version={VERSION}&plan_role={ROLE_BASELINE_BEST}")

    assert resp.status_code == 200
    assert "原算法代表方案" in unquote(str(resp.headers.get("Content-Disposition") or ""))
    workbook = openpyxl.load_workbook(io.BytesIO(resp.data))
    # 非正式方案导出会在第 0 页插入"查询摘要"明示方案身份，数据页按名称取。
    assert "查询摘要" in workbook.sheetnames
    sheet = workbook["周计划"]
    assert sheet is not None
    assert sheet["A2"].value == "2026-05-12"
    assert sheet["E2"].value == "M-CANDIDATE 候选设备"
    assert sheet["F2"].value == "O-CANDIDATE 候选人员"

    conn = get_connection(str(db_path))
    try:
        row = conn.execute(
            """
            SELECT detail
            FROM OperationLogs
            WHERE module='scheduler' AND action='export' AND target_type='week_plan'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    detail = json.loads(row["detail"])
    filters = detail.get("filters") or {}
    assert filters.get("version") == VERSION
    assert filters.get("requested_plan_role") == ROLE_BASELINE_BEST
    assert filters.get("effective_plan_role") == ROLE_BASELINE_BEST
    assert filters.get("plan_role_status") == "resolved_comparison"
    assert filters.get("candidate_key") == "baseline_best"

    fallback_resp = client.get(f"/scheduler/week-plan/export?week_start=2026-05-11&version={VERSION}&plan_role=critical_best")
    assert fallback_resp.status_code == 200
    fallback_disposition = unquote(str(fallback_resp.headers.get("Content-Disposition") or ""))
    assert "正式采用方案" in fallback_disposition
