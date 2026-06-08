"""回归测试：GanttCriticalChainProvider.get_critical_chain 按 plan_resolution 选源——adopted 角色走 schedule_repo、候选角色按 (source_table, candidate_id) 取全量明细行计算关键链；并验证缓存键按 role/candidate_id/source_table/数据库 scope 分桶、命中结果与调用方隔离不被 mutate、unavailable 结果不缓存、clear_cache 阻止 in-flight compute 回填缓存。"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, List

from core.services.scheduler.gantt_critical_chain_provider import GanttCriticalChainProvider
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE


class _DummyCursor:
    def __init__(self, db_file: str = ":memory:"):
        self._db_file = db_file

    def fetchall(self):
        return [(0, "main", self._db_file)]


class _DummyConn:
    def __init__(self, db_file: str = ":memory:"):
        self._db_file = db_file

    def execute(self, sql: str):
        if "pragma database_list" not in str(sql or "").strip().lower():
            raise RuntimeError(f"unexpected sql in test: {sql!r}")
        return _DummyCursor(self._db_file)


class _DummyScheduleRepo:
    pass


class _PlanQueryProbe:
    def __init__(
        self,
        rows_by_role: Dict[str, List[Dict[str, Any]]] = None,
        rows_by_resolution: Dict[tuple, List[Dict[str, Any]]] = None,
    ):
        self.rows_by_role = rows_by_role or {}
        self.rows_by_resolution = rows_by_resolution or {}
        self.calls: List[Dict[str, Any]] = []

    def list_plan_detail_rows_all(self, *, version: int, role):
        self.calls.append({"version": int(version), "role": role})
        return list(self.rows_by_role.get(str(role or ""), []))

    def list_plan_detail_rows_all_for_resolution(self, *, version: int, source_table: str, candidate_id):
        self.calls.append(
            {
                "version": int(version),
                "source_table": source_table,
                "candidate_id": candidate_id,
            }
        )
        return list(self.rows_by_resolution.get((source_table, candidate_id), []))


def _reset_provider_cache(monkeypatch) -> None:
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE", OrderedDict())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_MAX", 8)
    monkeypatch.setattr(GanttCriticalChainProvider, "_CRITICAL_CHAIN_CACHE_EPOCH", 0)


def _plan_resolution(role: str, *, candidate_id=None, source_table: str = SOURCE_SCHEDULE) -> Dict[str, Any]:
    return {
        "requested_role": role,
        "selected_role": role,
        "source_table": source_table,
        "candidate_id": candidate_id,
        "candidate_key": None,
        "status": "resolved_adopted" if role == ROLE_ADOPTED else "resolved_comparison",
        "message": "",
    }


def test_adopted_critical_chain_uses_schedule_repo(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    calls: List[Dict[str, Any]] = []

    def _fake_compute(schedule_repo, version: int) -> Dict[str, Any]:
        calls.append({"schedule_repo": schedule_repo, "version": int(version)})
        return {"ids": ["ADOPTED"], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain", _fake_compute)
    plan_query = _PlanQueryProbe()
    schedule_repo = _DummyScheduleRepo()
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=schedule_repo, plan_query_service=plan_query)

    result = provider.get_critical_chain(7, plan_resolution=_plan_resolution(ROLE_ADOPTED))

    assert result["ids"] == ["ADOPTED"]
    assert result["available"] is True
    assert result["reason"] == ""
    assert result["cache_hit"] is False
    assert calls == [{"schedule_repo": schedule_repo, "version": 7}]
    assert plan_query.calls == []


def test_candidate_critical_chain_uses_full_plan_detail_rows(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    rows_seen: List[List[Dict[str, Any]]] = []

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        rows_seen.append(rows)
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(
        rows_by_resolution={
            (SOURCE_CANDIDATE_ROWS, 101): [
                {
                    "op_code": "BASELINE-OP",
                    "start_time": "2026-05-01 08:00",
                    "end_time": "2026-05-01 10:00",
                }
            ]
        }
    )
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)

    result = provider.get_critical_chain(
        7,
        plan_resolution=_plan_resolution(
            ROLE_BASELINE_BEST,
            candidate_id=101,
            source_table=SOURCE_CANDIDATE_ROWS,
        ),
    )

    assert result["ids"] == ["BASELINE-OP"]
    assert result["cache_hit"] is False
    assert plan_query.calls == [{"version": 7, "source_table": SOURCE_CANDIDATE_ROWS, "candidate_id": 101}]
    assert rows_seen == [
        [
            {
                "op_code": "BASELINE-OP",
                "start_time": "2026-05-01 08:00",
                "end_time": "2026-05-01 10:00",
            }
        ]
    ]


def test_critical_best_critical_chain_uses_candidate_rows(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 202): [{"op_code": "CRITICAL-OP"}]})
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)

    result = provider.get_critical_chain(
        7,
        plan_resolution=_plan_resolution(
            ROLE_CRITICAL_BEST,
            candidate_id=202,
            source_table=SOURCE_CANDIDATE_ROWS,
        ),
    )

    assert result["ids"] == ["CRITICAL-OP"]
    assert plan_query.calls == [{"version": 7, "source_table": SOURCE_CANDIDATE_ROWS, "candidate_id": 202}]


def test_non_adopted_schedule_source_uses_resolved_source_table(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(
        rows_by_resolution={
            (SOURCE_SCHEDULE, None): [{"op_code": "SCHEDULE-SOURCE-ROW"}],
            (SOURCE_CANDIDATE_ROWS, None): [{"op_code": "WRONG-CANDIDATE-ROW"}],
        }
    )
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)

    result = provider.get_critical_chain(
        7,
        plan_resolution=_plan_resolution(
            ROLE_BASELINE_BEST,
            candidate_id=None,
            source_table=SOURCE_SCHEDULE,
        ),
    )

    assert result["ids"] == ["SCHEDULE-SOURCE-ROW"]
    assert plan_query.calls == [{"version": 7, "source_table": SOURCE_SCHEDULE, "candidate_id": None}]


def test_candidate_rows_are_loaded_from_resolved_candidate_id_not_current_role_selection(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(
        rows_by_role={ROLE_BASELINE_BEST: [{"op_code": "ROLE-RESELECTED-ROW"}]},
        rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "RESOLVED-CANDIDATE-ROW"}]},
    )
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)

    result = provider.get_critical_chain(
        7,
        plan_resolution=_plan_resolution(
            ROLE_BASELINE_BEST,
            candidate_id=101,
            source_table=SOURCE_CANDIDATE_ROWS,
        ),
    )

    assert result["ids"] == ["RESOLVED-CANDIDATE-ROW"]
    assert plan_query.calls == [{"version": 7, "source_table": SOURCE_CANDIDATE_ROWS, "candidate_id": 101}]


def test_candidate_cache_key_keeps_candidate_ids_separate(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    compute_count = {"value": 0}

    def _fake_compute_from_rows(_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        compute_count["value"] += 1
        return {"ids": [f"CHAIN-{compute_count['value']}"], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(
        rows_by_resolution={
            (SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "CANDIDATE-A"}],
            (SOURCE_CANDIDATE_ROWS, 202): [{"op_code": "CANDIDATE-B"}],
        }
    )
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)
    plan_a = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)
    plan_b = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=202, source_table=SOURCE_CANDIDATE_ROWS)

    first_a = provider.get_critical_chain(7, plan_resolution=plan_a)
    first_b = provider.get_critical_chain(7, plan_resolution=plan_b)
    second_a = provider.get_critical_chain(7, plan_resolution=plan_a)

    assert first_a["ids"] == ["CHAIN-1"]
    assert first_a["cache_hit"] is False
    assert first_b["ids"] == ["CHAIN-2"]
    assert first_b["cache_hit"] is False
    assert second_a["ids"] == ["CHAIN-1"]
    assert second_a["cache_hit"] is True
    assert compute_count["value"] == 2


def test_candidate_cache_key_keeps_roles_separate_even_when_candidate_matches(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    compute_count = {"value": 0}

    def _fake_compute_from_rows(_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        compute_count["value"] += 1
        return {"ids": [f"ROLE-CHAIN-{compute_count['value']}"], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "SAME-CANDIDATE"}]})
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)
    baseline_plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)
    critical_plan = _plan_resolution(ROLE_CRITICAL_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)

    first_baseline = provider.get_critical_chain(7, plan_resolution=baseline_plan)
    first_critical = provider.get_critical_chain(7, plan_resolution=critical_plan)
    second_baseline = provider.get_critical_chain(7, plan_resolution=baseline_plan)

    assert first_baseline["ids"] == ["ROLE-CHAIN-1"]
    assert first_baseline["cache_hit"] is False
    assert first_critical["ids"] == ["ROLE-CHAIN-2"]
    assert first_critical["cache_hit"] is False
    assert second_baseline["ids"] == ["ROLE-CHAIN-1"]
    assert second_baseline["cache_hit"] is True
    assert compute_count["value"] == 2


def test_candidate_cache_key_keeps_source_tables_separate(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(
        rows_by_resolution={
            (SOURCE_SCHEDULE, 101): [{"op_code": "SCHEDULE-CHAIN"}],
            (SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "CANDIDATE-CHAIN"}],
        }
    )
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)
    schedule_plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_SCHEDULE)
    candidate_plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)

    first_schedule = provider.get_critical_chain(7, plan_resolution=schedule_plan)
    first_candidate = provider.get_critical_chain(7, plan_resolution=candidate_plan)
    second_schedule = provider.get_critical_chain(7, plan_resolution=schedule_plan)

    assert first_schedule["ids"] == ["SCHEDULE-CHAIN"]
    assert first_schedule["cache_hit"] is False
    assert first_candidate["ids"] == ["CANDIDATE-CHAIN"]
    assert first_candidate["cache_hit"] is False
    assert second_schedule["ids"] == ["SCHEDULE-CHAIN"]
    assert second_schedule["cache_hit"] is True
    assert plan_query.calls == [
        {"version": 7, "source_table": SOURCE_SCHEDULE, "candidate_id": 101},
        {"version": 7, "source_table": SOURCE_CANDIDATE_ROWS, "candidate_id": 101},
    ]


def test_candidate_cache_key_keeps_database_scopes_separate(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)
    plan_query_a = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "DB-A-CHAIN"}]})
    plan_query_b = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "DB-B-CHAIN"}]})
    provider_a = GanttCriticalChainProvider(
        conn=_DummyConn("/tmp/aps-a.db"),
        schedule_repo=_DummyScheduleRepo(),
        plan_query_service=plan_query_a,
    )
    provider_b = GanttCriticalChainProvider(
        conn=_DummyConn("/tmp/aps-b.db"),
        schedule_repo=_DummyScheduleRepo(),
        plan_query_service=plan_query_b,
    )

    first_a = provider_a.get_critical_chain(7, plan_resolution=plan)
    first_b = provider_b.get_critical_chain(7, plan_resolution=plan)
    second_a = provider_a.get_critical_chain(7, plan_resolution=plan)

    assert first_a["ids"] == ["DB-A-CHAIN"]
    assert first_a["cache_hit"] is False
    assert first_b["ids"] == ["DB-B-CHAIN"]
    assert first_b["cache_hit"] is False
    assert second_a["ids"] == ["DB-A-CHAIN"]
    assert second_a["cache_hit"] is True
    assert plan_query_a.calls == [{"version": 7, "source_table": SOURCE_CANDIDATE_ROWS, "candidate_id": 101}]
    assert plan_query_b.calls == [{"version": 7, "source_table": SOURCE_CANDIDATE_ROWS, "candidate_id": 101}]


def test_unavailable_candidate_result_is_not_cached(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    compute_count = {"value": 0}

    def _fake_compute_from_rows(_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        compute_count["value"] += 1
        if compute_count["value"] == 1:
            return {"available": False, "reason": "rows_exception"}
        return {"ids": ["RECOVERED"], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "BASELINE-OP"}]})
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)
    plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)

    first = provider.get_critical_chain(7, plan_resolution=plan)
    second = provider.get_critical_chain(7, plan_resolution=plan)
    third = provider.get_critical_chain(7, plan_resolution=plan)

    assert first["available"] is False
    assert first["reason"] == "rows_exception"
    assert first["reason_code"] == "rows_exception"
    assert first["cache_hit"] is False
    assert second["ids"] == ["RECOVERED"]
    assert second["cache_hit"] is False
    assert third["ids"] == ["RECOVERED"]
    assert third["cache_hit"] is True
    assert compute_count["value"] == 2


def test_candidate_rows_load_failure_returns_unavailable_and_is_not_cached(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)

    def _fake_compute_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"ids": [rows[0]["op_code"]], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "RECOVERED"}]})
    original_loader = plan_query.list_plan_detail_rows_all_for_resolution

    def _raise_rows_load_failure(*, version: int, source_table: str, candidate_id):
        plan_query.calls.append(
            {
                "version": int(version),
                "source_table": source_table,
                "candidate_id": candidate_id,
            }
        )
        raise RuntimeError("candidate rows load failed")

    plan_query.list_plan_detail_rows_all_for_resolution = _raise_rows_load_failure
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)
    plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)

    first = provider.get_critical_chain(7, plan_resolution=plan)
    plan_query.list_plan_detail_rows_all_for_resolution = original_loader
    second = provider.get_critical_chain(7, plan_resolution=plan)
    third = provider.get_critical_chain(7, plan_resolution=plan)

    assert first["available"] is False
    assert first["reason"] == "rows_load_exception"
    assert first["reason_code"] == "rows_load_exception"
    assert first["cache_hit"] is False
    assert second["ids"] == ["RECOVERED"]
    assert second["cache_hit"] is False
    assert third["ids"] == ["RECOVERED"]
    assert third["cache_hit"] is True


def test_cache_hit_result_is_isolated_from_caller_mutation(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)

    def _fake_compute_from_rows(_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "ids": ["ORIGINAL"],
            "edges": [{"from": "A", "to": "B", "edge_type": "process"}],
            "edge_type_stats": {"process": 1, "machine": 0, "operator": 0, "unknown": 0},
            "edge_count": 1,
            "dropped_count": 2,
            "critical_chain_partial": True,
        }

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "BASELINE-OP"}]})
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)
    plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)

    first = provider.get_critical_chain(7, plan_resolution=plan)
    first["ids"].append("MUTATED")
    first["edges"][0]["from"] = "MUTATED"
    first["edge_type_stats"]["process"] = 99
    second = provider.get_critical_chain(7, plan_resolution=plan)

    assert second["cache_hit"] is True
    assert second["ids"] == ["ORIGINAL"]
    assert second["edges"] == [{"from": "A", "to": "B", "edge_type": "process"}]
    assert second["edge_type_stats"]["process"] == 1
    assert second["dropped_count"] == 2
    assert second["critical_chain_partial"] is True
    second["ids"].append("CACHE-HIT-MUTATED")
    second["edges"][0]["to"] = "CACHE-HIT-MUTATED"
    second["edge_type_stats"]["machine"] = 99
    third = provider.get_critical_chain(7, plan_resolution=plan)
    assert third["cache_hit"] is True
    assert third["ids"] == ["ORIGINAL"]
    assert third["edges"] == [{"from": "A", "to": "B", "edge_type": "process"}]
    assert third["edge_type_stats"] == {"process": 1, "machine": 0, "operator": 0, "unknown": 0}
    assert third["dropped_count"] == 2
    assert third["critical_chain_partial"] is True


def test_clear_cache_blocks_in_flight_compute_from_repopulating_cache(monkeypatch) -> None:
    import core.services.scheduler.gantt_critical_chain_provider as provider_module

    _reset_provider_cache(monkeypatch)
    compute_started = threading.Event()
    allow_compute_return = threading.Event()

    def _fake_compute_from_rows(_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        compute_started.set()
        assert allow_compute_return.wait(timeout=5)
        return {"ids": ["STALE"], "edges": [], "edge_count": 0}

    monkeypatch.setattr(provider_module, "compute_critical_chain_from_rows", _fake_compute_from_rows)
    plan_query = _PlanQueryProbe(rows_by_resolution={(SOURCE_CANDIDATE_ROWS, 101): [{"op_code": "BASELINE-OP"}]})
    provider = GanttCriticalChainProvider(conn=_DummyConn(), schedule_repo=_DummyScheduleRepo(), plan_query_service=plan_query)
    plan = _plan_resolution(ROLE_BASELINE_BEST, candidate_id=101, source_table=SOURCE_CANDIDATE_ROWS)
    result_box: Dict[str, Any] = {}

    def _worker() -> None:
        result_box["result"] = provider.get_critical_chain(7, plan_resolution=plan)

    worker = threading.Thread(target=_worker)
    worker.start()
    assert compute_started.wait(timeout=5)
    GanttCriticalChainProvider.clear_cache()
    allow_compute_return.set()
    worker.join(timeout=5)

    assert result_box["result"]["ids"] == ["STALE"]
    assert len(GanttCriticalChainProvider._CRITICAL_CHAIN_CACHE) == 0
