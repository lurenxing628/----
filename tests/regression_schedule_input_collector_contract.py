import os
import sqlite3
import sys
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.common.build_outcome import BuildOutcome
    from core.services.scheduler.schedule_input_collector import collect_schedule_run_input
    from core.services.scheduler.schedule_service import ScheduleService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row

    captured: Dict[str, Any] = {}

    class _FakeCalendarService:
        def __init__(self, conn, logger=None, op_logger=None):
            self.conn = conn
            self.logger = logger
            self.op_logger = op_logger

    class _FakeConfigService:
        def __init__(self, conn, logger=None, op_logger=None):
            self.conn = conn
            self.logger = logger
            self.op_logger = op_logger

    def _get_snapshot_with_optional_strict_mode(_cfg_svc, *, strict_mode: bool):
        captured["strict_mode_to_snapshot"] = strict_mode
        return SimpleNamespace(enforce_ready_default="no")

    def _build_algo_operations(_svc, ops: List[Any], *, strict_mode: bool):
        captured["algo_input_ids"] = [int(op.id) for op in ops]
        captured["algo_input_strict_mode"] = strict_mode
        return BuildOutcome(
            value=[
                SimpleNamespace(id=1, op_code="B001_10", batch_id="B001", seq=10, source="internal"),
                SimpleNamespace(id=2, op_code="B001_20", batch_id="B001", seq=20, source="internal"),
            ],
            counters={"collector_contract": 1},
        )

    def _build_freeze_window_seed(
        _svc,
        *,
        cfg,
        prev_version: int,
        start_dt: datetime,
        operations: List[Any],
        reschedulable_operations: List[Any],
        strict_mode: bool,
        meta: Dict[str, Any],
    ):
        captured["freeze_prev_version"] = prev_version
        captured["freeze_start_dt"] = start_dt
        captured["freeze_all_ids"] = [int(op.id) for op in operations]
        captured["freeze_reschedulable_ids"] = [int(op.id) for op in reschedulable_operations]
        captured["freeze_strict_mode"] = strict_mode
        meta["loaded"] = True
        return {2}, [{"op_id": 2}], ["freeze warning"]

    def _load_machine_downtimes(_svc, *, algo_ops, start_dt, warnings, meta):
        captured["downtime_algo_ids"] = [int(op.id) for op in algo_ops]
        captured["downtime_start_dt"] = start_dt
        captured["downtime_warnings_before"] = list(warnings or [])
        meta["load_ok"] = True
        return {"MC001": []}

    def _build_resource_pool(_svc, *, cfg, algo_ops, meta):
        captured["resource_pool_algo_ids"] = [int(op.id) for op in algo_ops]
        meta["build_ok"] = True
        return {"machine_candidates": {1: ["MC001"]}}, ["pool warning"]

    def _extend_downtime_map_for_resource_pool(
        _svc,
        *,
        cfg,
        resource_pool,
        downtime_map,
        start_dt,
        warnings,
        meta,
    ):
        captured["extend_resource_pool"] = resource_pool
        captured["extend_downtime_map"] = dict(downtime_map or {})
        captured["extend_warnings_before"] = list(warnings or [])
        meta["extend_ok"] = True
        merged = dict(downtime_map or {})
        merged["MC_POOL"] = []
        return merged

    svc = ScheduleService(conn, logger=None, op_logger=None)
    svc._get_batch_or_raise = lambda bid: SimpleNamespace(  # type: ignore[assignment]
        batch_id=bid,
        status="pending",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
        part_no="P001",
    )
    svc.op_repo = SimpleNamespace(  # type: ignore[assignment]
        list_by_batch=lambda _bid: [
            SimpleNamespace(
                id=1,
                op_code="B001_10",
                batch_id="B001",
                seq=10,
                source="internal",
                machine_id="",
                operator_id="",
                supplier_id=None,
                setup_hours=1.0,
                unit_hours=0.0,
                ext_days=None,
                status="pending",
                op_type_name="工序A",
            ),
            SimpleNamespace(
                id=2,
                op_code="B001_20",
                batch_id="B001",
                seq=20,
                source="internal",
                machine_id="MC001",
                operator_id="OP001",
                supplier_id=None,
                setup_hours=1.0,
                unit_hours=0.0,
                ext_days=None,
                status="scheduled",
                op_type_name="工序B",
            ),
            SimpleNamespace(
                id=3,
                op_code="B001_30",
                batch_id="B001",
                seq=30,
                source="internal",
                machine_id="MC001",
                operator_id="OP001",
                supplier_id=None,
                setup_hours=1.0,
                unit_hours=0.0,
                ext_days=None,
                status="completed",
                op_type_name="工序C",
            ),
            SimpleNamespace(
                id=4,
                op_code="B001_40",
                batch_id="B001",
                seq=40,
                source="external",
                machine_id=None,
                operator_id=None,
                supplier_id="SUP001",
                setup_hours=0.0,
                unit_hours=0.0,
                ext_days=2.0,
                status="skipped",
                op_type_name="外协D",
            ),
        ]
    )
    svc.history_repo.get_latest_version = lambda: 5  # type: ignore[assignment]

    try:
        collected = collect_schedule_run_input(
            svc,
            batch_ids=["B001", "B001", ""],
            start_dt="2026-01-01 08:00:00",
            end_date=None,
            created_by="tester",
            simulate=True,
            enforce_ready=True,
            strict_mode=True,
            calendar_service_cls=_FakeCalendarService,
            config_service_cls=_FakeConfigService,
            get_snapshot_with_optional_strict_mode=_get_snapshot_with_optional_strict_mode,
            build_algo_operations_fn=_build_algo_operations,
            build_freeze_window_seed_fn=_build_freeze_window_seed,
            load_machine_downtimes_fn=_load_machine_downtimes,
            build_resource_pool_fn=_build_resource_pool,
            extend_downtime_map_for_resource_pool_fn=_extend_downtime_map_for_resource_pool,
        )
    finally:
        conn.close()

    assert collected.normalized_batch_ids == ["B001"], collected
    assert collected.created_by_text == "tester", collected
    assert collected.run_label == "模拟排产", collected
    assert collected.reschedulable_op_ids == {1, 2}, collected
    assert [int(getattr(op, "id", 0) or 0) for op in collected.reschedulable_operations] == [1, 2], collected
    assert collected.missing_internal_resource_op_ids == {1}, collected
    assert int(collected.prev_version) == 5, collected
    assert int(collected.optimizer_seed_version) == 6, collected
    assert collected.frozen_op_ids == {2}, collected
    assert [int(getattr(op, "id", 0) or 0) for op in collected.algo_ops_to_schedule] == [1], collected
    assert list(collected.algo_warnings) == ["freeze warning", "pool warning"], collected
    assert getattr(collected.algo_input_outcome, "counters", {}).get("collector_contract") == 1, collected
    assert collected.downtime_map == {"MC001": [], "MC_POOL": []}, collected
    assert collected.resource_pool == {"machine_candidates": {1: ["MC001"]}}, collected
    assert collected.freeze_meta == {"loaded": True}, collected
    assert collected.downtime_meta == {"load_ok": True, "extend_ok": True}, collected
    assert collected.resource_pool_meta == {"build_ok": True}, collected

    assert captured.get("strict_mode_to_snapshot") is True, captured
    assert captured.get("algo_input_ids") == [1, 2], captured
    assert captured.get("freeze_reschedulable_ids") == [1, 2], captured
    assert captured.get("downtime_warnings_before") == ["freeze warning"], captured
    assert captured.get("extend_warnings_before") == ["freeze warning", "pool warning"], captured

    print("OK")


if __name__ == "__main__":
    main()
