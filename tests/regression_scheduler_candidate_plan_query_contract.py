from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, List, Sequence

import pytest

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

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"
VERSION = 7

COMMON_DETAIL_KEYS = {
    "schedule_id",
    "op_id",
    "start_time",
    "end_time",
    "lock_status",
    "version",
    "op_code",
    "batch_id",
    "piece_id",
    "seq",
    "op_type_name",
    "source",
    "op_status",
    "machine_id",
    "operator_id",
    "supplier_id",
    "part_no",
    "part_name",
    "due_date",
    "priority",
    "machine_name",
    "operator_name",
    "supplier_name",
}

DISPATCH_DETAIL_KEYS = COMMON_DETAIL_KEYS | {
    "machine_team_id",
    "machine_team_name",
    "operator_team_id",
    "operator_team_name",
}


def _connect_fresh_schema(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _require_id(value: Any) -> int:
    assert value is not None
    return int(value)


def _seed_schedule_context(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO ResourceTeams(team_id, name)
        VALUES ('T-ADOPTED', '正式班组'), ('T-CANDIDATE', '候选班组');

        INSERT INTO Machines(machine_id, name, team_id)
        VALUES ('M-ADOPTED', '正式设备', 'T-ADOPTED'), ('M-CANDIDATE', '候选设备', 'T-CANDIDATE');

        INSERT INTO Operators(operator_id, name, team_id)
        VALUES ('O-ADOPTED', '正式人员', 'T-ADOPTED'), ('O-CANDIDATE', '候选人员', 'T-CANDIDATE');

        INSERT INTO Suppliers(supplier_id, name)
        VALUES ('S1', '供应商一');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority)
        VALUES ('B1', 'P001', '零件一', 1, '2026-05-01', 'urgent');

        INSERT INTO BatchOperations(
            id, op_code, batch_id, piece_id, seq, op_type_name, source, status, supplier_id
        )
        VALUES (10, 'OP10', 'B1', 'piece-a', 1, '车削', 'internal', 'scheduled', 'S1');

        INSERT INTO Schedule(
            id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
        )
        VALUES (1, 10, 'M-ADOPTED', 'O-ADOPTED', '2026-05-01 08:00', '2026-05-01 10:00', 'unlocked', 7);
        """
    )


def _seed_candidates(conn: sqlite3.Connection) -> ScheduleCandidateRepository:
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
    return repo


def _seed_candidate_rows_selection_without_rows(conn: sqlite3.Connection, *, detail_saved: str) -> None:
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
    candidate = repo.create_candidate(
        ScheduleCandidate(
            id=None,
            version=VERSION,
            candidate_key="baseline_without_rows",
            candidate_label="缺明细候选",
            candidate_kind="baseline",
            status="completed",
            graph_enabled="no",
            detail_saved=detail_saved,
        )
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
            candidate_id=_require_id(candidate.id),
            source_table=SOURCE_CANDIDATE_ROWS,
        )
    )


def _seed_db(tmp_path: Path) -> sqlite3.Connection:
    conn = _connect_fresh_schema(tmp_path)
    _seed_schedule_context(conn)
    _seed_candidates(conn)
    conn.commit()
    return conn


def _ids(rows: Sequence[Any]) -> List[int]:
    return [int(row["schedule_id"]) for row in rows]


def test_candidate_repository_roundtrips_candidates_rows_and_selections(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        repo = ScheduleCandidateRepository(conn)
        candidate = repo.get_candidate_by_key(version=VERSION, candidate_key="baseline_best")
        assert candidate is not None
        assert candidate.candidate_label == "候选代表"
        assert candidate.detail_saved == "yes"

        rows = repo.list_candidate_rows(version=VERSION, candidate_id=_require_id(candidate.id))
        assert [row.op_id for row in rows] == [10]
        assert rows[0].machine_id == "M-CANDIDATE"

        selection = repo.get_selection(version=VERSION, role=ROLE_BASELINE_BEST)
        assert selection is not None
        assert selection.source_table == SOURCE_CANDIDATE_ROWS
    finally:
        conn.close()


def test_plan_query_reads_adopted_and_candidate_rows_with_same_detail_shape(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        service = SchedulePlanQueryService(conn)

        adopted_resolution = service.resolve_plan(VERSION, None)
        assert adopted_resolution.selected_role == ROLE_ADOPTED
        assert adopted_resolution.source_table == SOURCE_SCHEDULE

        adopted_rows = service.list_plan_detail_rows_all(version=VERSION, role=None)
        assert _ids(adopted_rows) == [1]
        assert set(adopted_rows[0]) == COMMON_DETAIL_KEYS
        assert adopted_rows[0].get("machine_id") == "M-ADOPTED"
        assert adopted_rows[0].get("machine_name") == "正式设备"

        baseline_resolution = service.resolve_plan(VERSION, ROLE_BASELINE_BEST)
        assert baseline_resolution.selected_role == ROLE_BASELINE_BEST
        assert baseline_resolution.source_table == SOURCE_CANDIDATE_ROWS
        assert baseline_resolution.candidate_key == "baseline_best"

        baseline_rows = service.list_plan_detail_rows_all(version=VERSION, role=ROLE_BASELINE_BEST)
        assert _ids(baseline_rows) == [1]
        assert set(baseline_rows[0]) == COMMON_DETAIL_KEYS
        assert baseline_rows[0].get("machine_id") == "M-CANDIDATE"
        assert baseline_rows[0].get("operator_id") == "O-CANDIDATE"
        assert baseline_rows[0].get("machine_name") == "候选设备"
        assert baseline_rows[0].get("operator_name") == "候选人员"
    finally:
        conn.close()


def test_plan_query_has_visible_legacy_fallback_and_rejects_unknown_role(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        service = SchedulePlanQueryService(conn)

        fallback = service.resolve_plan(VERSION, ROLE_CRITICAL_BEST)
        assert fallback.requested_role == ROLE_CRITICAL_BEST
        assert fallback.selected_role == ROLE_ADOPTED
        assert fallback.status == "fallback_to_adopted"
        assert "最终采用方案" in fallback.message

        fallback_rows = service.list_plan_detail_rows_all(version=VERSION, role=ROLE_CRITICAL_BEST)
        assert fallback_rows[0].get("machine_id") == "M-ADOPTED"

        with pytest.raises(ValueError, match="未知的排产方案角色"):
            service.resolve_plan(VERSION, "typo-role")
    finally:
        conn.close()


def test_plan_query_keeps_legacy_no_selection_fallback_to_adopted(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_schedule_context(conn)
        conn.commit()

        service = SchedulePlanQueryService(conn)
        resolution = service.resolve_plan(VERSION, ROLE_BASELINE_BEST)

        assert resolution.selected_role == ROLE_ADOPTED
        assert resolution.status == "fallback_to_adopted"
    finally:
        conn.close()


def test_plan_query_rejects_selection_pointing_to_missing_candidate(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_schedule_context(conn)
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
        repo.create_selection(
            ScheduleCandidateSelection(
                id=None,
                version=VERSION,
                role=ROLE_ADOPTED,
                candidate_id=_require_id(adopted.id),
                source_table=SOURCE_SCHEDULE,
            )
        )
        conn.commit()

        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            """
            INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
            VALUES (?, ?, ?, ?)
            """,
            (VERSION, ROLE_BASELINE_BEST, 999999, SOURCE_CANDIDATE_ROWS),
        )
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

        service = SchedulePlanQueryService(conn)
        with pytest.raises(ValueError, match="候选方案角色映射.*不存在|指向的候选不存在"):
            service.resolve_plan(VERSION, ROLE_BASELINE_BEST)
    finally:
        conn.close()


def test_plan_query_rejects_candidate_selection_set_without_adopted_role(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_schedule_context(conn)
        repo = ScheduleCandidateRepository(conn)
        candidate = repo.create_candidate(
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
        repo.bulk_create_candidate_rows(
            [
                ScheduleCandidateRows(
                    id=None,
                    version=VERSION,
                    candidate_id=_require_id(candidate.id),
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
                role=ROLE_BASELINE_BEST,
                candidate_id=_require_id(candidate.id),
                source_table=SOURCE_CANDIDATE_ROWS,
            )
        )
        conn.commit()

        service = SchedulePlanQueryService(conn)
        with pytest.raises(ValueError, match="缺少 adopted|最终采用"):
            service.resolve_plan(VERSION, ROLE_ADOPTED)
    finally:
        conn.close()


def test_plan_query_rejects_candidate_rows_selection_without_saved_details(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_schedule_context(conn)
        _seed_candidate_rows_selection_without_rows(conn, detail_saved="no")
        conn.commit()

        service = SchedulePlanQueryService(conn)
        with pytest.raises(ValueError, match="没有保存明细"):
            service.resolve_plan(VERSION, ROLE_BASELINE_BEST)
    finally:
        conn.close()


def test_plan_query_rejects_candidate_rows_selection_without_actual_rows(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_schedule_context(conn)
        _seed_candidate_rows_selection_without_rows(conn, detail_saved="yes")
        conn.commit()

        service = SchedulePlanQueryService(conn)
        with pytest.raises(ValueError, match="没有找到对应的候选明细"):
            service.resolve_plan(VERSION, ROLE_BASELINE_BEST)
    finally:
        conn.close()


def test_candidate_plan_time_span_and_dispatch_scope_use_candidate_rows(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        service = SchedulePlanQueryService(conn)

        adopted_span = service.get_plan_time_span(VERSION, ROLE_ADOPTED)
        baseline_span = service.get_plan_time_span(VERSION, ROLE_BASELINE_BEST)
        assert adopted_span == {
            "version": VERSION,
            "start_time": "2026-05-01 08:00",
            "end_time": "2026-05-01 10:00",
        }
        assert baseline_span == {
            "version": VERSION,
            "start_time": "2026-05-01 13:00",
            "end_time": "2026-05-01 15:00",
        }

        dispatch_rows = service.list_plan_dispatch_rows(
            version=VERSION,
            role=ROLE_BASELINE_BEST,
            start_time="2026-05-01 00:00",
            end_time="2026-05-02 00:00",
            scope_type="machine",
            scope_id="M-CANDIDATE",
        )
        assert _ids(dispatch_rows) == [1]
        assert set(dispatch_rows[0]) == DISPATCH_DETAIL_KEYS
        assert dispatch_rows[0].get("machine_team_id") == "T-CANDIDATE"
        assert dispatch_rows[0].get("operator_team_id") == "T-CANDIDATE"
    finally:
        conn.close()


def test_plan_query_service_lists_overdue_base_rows_from_candidate_rows(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        service = SchedulePlanQueryService(conn)

        adopted_rows = service.list_plan_overdue_base_rows(version=VERSION, role=ROLE_ADOPTED)
        baseline_rows = service.list_plan_overdue_base_rows(version=VERSION, role=ROLE_BASELINE_BEST)

        assert len(adopted_rows) == 1
        assert adopted_rows[0]["batch_id"] == "B1"
        assert adopted_rows[0]["finish_time"] == "2026-05-01 10:00"

        assert len(baseline_rows) == 1
        assert baseline_rows[0]["batch_id"] == "B1"
        assert baseline_rows[0]["finish_time"] == "2026-05-01 15:00"
    finally:
        conn.close()
