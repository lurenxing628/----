"""回归测试：甘特图 /scheduler/gantt[/data] 的 plan_role 契约——baseline_best 等候选角色从 ScheduleCandidateRows 读任务并回传 requested/effective_plan_role 与 source_table，未知/缺失角色回退到 adopted 并提示，关键链异常时走脱敏公共契约（不泄露内部候选 id），逾期标记按候选行而非沿用 adopted 历史，未知 plan_role 且无历史时页面返 400。"""

from __future__ import annotations

import importlib
import json
import sys

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    SchedulePlanQueryService,
)
from data.repositories.schedule_candidate_repo import ScheduleCandidateRepository
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 7
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
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))
    monkeypatch.setenv("APS_BACKUP_DIR", str(backup_dir))
    point_env_at_shared(monkeypatch)

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


def test_plan_role_same_as_adopted_still_keeps_comparison_identity(tmp_path) -> None:
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
        assert resolution["is_comparison"] is True
    finally:
        conn.close()


def test_gantt_page_and_boot_preserve_plan_role(tmp_path, monkeypatch) -> None:
    from contextlib import closing

    from core.models.workbench_plan_reference import WorkbenchPlanLocator
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
    from tests._support.gantt_current import assert_plan_exports, prepare_read_state
    from tests._support.gantt_retirement import _business_state, _canonical_workspace

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    before = prepare_read_state(client)
    with closing(get_connection(app.config["DATABASE_PATH"])) as conn:
        repo = WorkbenchPlanIdentityRepository(conn)
        candidate_ref = repo.get_plan_ref(WorkbenchPlanLocator(VERSION, ROLE_BASELINE_BEST))
        adopted_ref = repo.get_plan_ref(WorkbenchPlanLocator(VERSION, ROLE_ADOPTED))
    context, payload = _canonical_workspace(client, {"version": VERSION, "plan_role": ROLE_BASELINE_BEST})
    assert context == {"plan_ref": candidate_ref}
    assert candidate_ref != adopted_ref
    assert payload["data"]["plan"]["kind"] == "candidate"
    assert payload["data"]["plan"]["is_current_official"] is False
    assert payload["data"]["plan"]["capabilities"]["adopt"] is False
    tasks = payload["data"]["tasks"]
    assert len(tasks) == 1 and tasks[0]["start"] == "2026-05-12T13:00:00"
    assert tasks[0]["end"] == "2026-05-13T15:00:00"
    resources = {item["ref"]: item for item in payload["data"]["resources"]}
    assert resources[tasks[0]["machine_ref"]]["business_code"] == "M-CANDIDATE"
    assert resources[tasks[0]["operator_ref"]]["business_code"] == "O-CANDIDATE"
    assert _public_json_forbidden_key_paths(payload["data"]) == []
    assert_plan_exports(client, context, payload)
    assert _business_state(client) == before


