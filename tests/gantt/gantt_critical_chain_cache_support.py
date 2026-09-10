"""Real, disposable SQLite fixtures for the critical-chain cache contract."""

from __future__ import annotations

import sqlite3
import threading
from collections import OrderedDict
from contextlib import contextmanager

from core.models.schedule_plan_role import SOURCE_ADJUSTMENT_SCENARIO_ROWS, SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from core.services.scheduler.gantt_critical_chain import (
    _normalize_critical_chain_result,
    compute_critical_chain_from_rows,
)
from core.services.scheduler.gantt_critical_chain_provider import GanttCriticalChainProvider
from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
from data.repositories import ScheduleRepository
from tests._support.paths import REPO_ROOT

SOURCES = (SOURCE_SCHEDULE, SOURCE_CANDIDATE_ROWS, SOURCE_ADJUSTMENT_SCENARIO_ROWS)
TABLES = dict(zip(SOURCES, ("Schedule", "ScheduleCandidateRows", "ScheduleAdjustmentScenarioRow")))
STAMP = "2026-09-08 08:00:00"


def reset_cache(monkeypatch, cache_max=8):
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE", OrderedDict())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_MAX", cache_max)
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_EPOCH", 0)


class CachePlanDB:
    def __init__(self, conn, source):
        self.conn = conn
        self.table = TABLES[source]
        self.plan = {
            "selected_role": "baseline_best" if source == SOURCE_CANDIDATE_ROWS else "adopted",
            "source_table": source,
            "candidate_id": 101 if source == SOURCE_CANDIDATE_ROWS else None,
            "scenario_id": "S1" if source == SOURCE_ADJUSTMENT_SCENARIO_ROWS else None,
        }
        self.query = SchedulePlanQueryService(conn)
        self.provider = GanttCriticalChainProvider(
            conn=conn, schedule_repo=ScheduleRepository(conn), plan_query_service=self.query
        )

    def seed_rows(self, machine_b="M1"):
        columns = "op_id, machine_id, start_time, end_time, created_at"
        extra = {"Schedule": ("version", 1), "ScheduleCandidateRows": ("version, candidate_id", 1, 101),
                 "ScheduleAdjustmentScenarioRow": ("scenario_id, source_table", "S1", "schedule")}[self.table]
        for op_id, machine, start, end in ((1, "M1", "08", "09"), (2, machine_b, "09", "11")):
            values = (op_id, machine, "2026-09-08 " + start + ":00:00", "2026-09-08 " + end + ":00:00", STAMP) + extra[1:]
            placeholders = ",".join("?" for _ in values)
            self.conn.execute("INSERT INTO " + self.table + " (" + columns + "," + extra[0] + ") VALUES (" + placeholders + ")", values)
        self.conn.commit()

    def read(self, version=1, plan=None):
        return self.provider.get_critical_chain(version, plan_resolution=self.plan if plan is None else plan)

    def rows(self, version=1):
        return self.query.list_plan_detail_rows_all_for_resolution(version=version, **{
            key: self.plan[key] for key in ("source_table", "candidate_id", "scenario_id")
        })

    def direct(self, version=1):
        return _normalize_critical_chain_result(compute_critical_chain_from_rows(self.rows(version)))

    def old_aggregate(self):
        return tuple(self.conn.execute("SELECT COUNT(*), MAX(id), MAX(created_at) FROM " + self.table).fetchone())


@contextmanager
def cache_db(source=SOURCE_SCHEDULE, path=":memory:", seed=True):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
        # Exercise real joins/constraints on plan rows, not master-data FK setup.
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executemany("INSERT INTO Batches(batch_id, part_no, part_name, quantity) VALUES (?, 'P', 'Part', 1)", [("X",), ("Y",)])
        conn.executemany(
            "INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name) VALUES (?, ?, ?, 'piece', ?, 'Cut')",
            [(1, "A", "X", 1), (2, "B", "Y", 2)],
        )
        conn.execute("INSERT INTO ScheduleCandidate(id, version, candidate_key, candidate_label, candidate_kind, status) VALUES (101, 1, 'C1', 'C1', 'baseline', 'completed')")
        conn.execute("INSERT INTO ScheduleAdjustmentScenario(scenario_id, source_draft_id, base_version, base_plan_role, base_source_table, validation_status) VALUES ('S1', 'D1', 1, 'adopted', 'schedule', 'valid')")
        conn.commit()
        case = CachePlanDB(conn, source)
        if seed:
            case.seed_rows()
        yield case
    finally:
        conn.close()


def assert_matches_direct(case, result):
    assert {key: value for key, value in result.items() if key != "cache_hit"} == case.direct()
