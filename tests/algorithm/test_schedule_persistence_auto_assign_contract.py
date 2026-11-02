"""共同排产 payload 校验与 Schedule 唯一索引迁移合同。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.services.scheduler.run.schedule_payload_contract import (
    build_validated_schedule_payload,
)
from tests._support.algo_operations import make_batch_operation, make_schedule_result
from tests._support.paths import REPO_ROOT


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


def _result(
    op_id: int,
    *,
    machine_id: Optional[str] = "MC_A",
    operator_id: Optional[str] = "OP_A",
    source: str = "internal",
    start_offset: int = 0,
    end_offset: int = 1,
) -> ScheduleResult:
    return make_schedule_result(
        op_id=op_id,
        op_code=f"B001_{op_id:02d}",
        batch_id="B001",
        seq=op_id,
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=_make_dt(start_offset),
        end_time=_make_dt(end_offset),
        source=source,
        op_type_name="A",
    )


def _operations(sources: Dict[int, str]) -> List[BatchOperation]:
    return [
        make_batch_operation(id=op_id, op_code=f"B001_{op_id:02d}", batch_id="B001", seq=op_id, source=source)
        for op_id, source in sorted(sources.items())
    ]


def _no_point_evidence(row: Any) -> None:
    """这些工序都不是零工时工序：生产见证核对对它们给不出证据。"""
    return None


def _build_payload(results: List[Any], *, allowed_op_ids: Set[int], operations: List[BatchOperation]):
    # 与生产 workbench/run/input 同口径：工序来源表由本次全部工序派生，本次输入没有缺资源工序、排产没有报错。
    return build_validated_schedule_payload(
        results,
        allowed_op_ids=allowed_op_ids,
        operations=operations,
        operation_sources={op.id: op.source for op in operations},
        missing_internal_resource_op_ids=set(),
        point_validator=_no_point_evidence,
    )


def _assert_validation_reason(results: List[Any], *, allowed_op_ids: Set[int], reason: str) -> Dict[str, Any]:
    operations = _operations({op_id: "internal" for op_id in allowed_op_ids})
    with pytest.raises(ValidationError) as exc_info:
        _build_payload(results, allowed_op_ids=allowed_op_ids, operations=operations)
    details = dict(getattr(exc_info.value, "details", {}) or {})
    assert details.get("reason") == reason, details
    return details


def test_schedule_payload_error_priority_and_no_actionable_details() -> None:
    invalid = _result(1, start_offset=1, end_offset=1)
    valid = _result(2, start_offset=2, end_offset=3)
    out_of_scope = _result(99, start_offset=3, end_offset=4)

    details = _assert_validation_reason(
        [invalid, valid, out_of_scope],
        allowed_op_ids={1, 2},
        reason="out_of_scope_schedule_rows",
    )
    assert details.get("sample_op_ids") == [99], details
    assert details.get("allowed_scope_kind") == "reschedulable_op_ids", details

    details = _assert_validation_reason(
        [invalid, valid],
        allowed_op_ids={1, 2},
        reason="invalid_schedule_rows",
    )
    assert details.get("invalid_schedule_row_count") == 1, details
    assert "start_time must be earlier than end_time" in "\n".join(details.get("validation_errors") or [])

    details = _assert_validation_reason(
        [_result(1, start_offset=1, end_offset=1), _result(2, start_offset=2, end_offset=2)],
        allowed_op_ids={1, 2},
        reason="no_actionable_schedule_rows",
    )
    assert len(details.get("validation_errors") or []) == 2, details


def test_schedule_payload_rejects_duplicate_op_id_before_persistence() -> None:
    details = _assert_validation_reason(
        [
            _result(1, machine_id="MC_A", start_offset=0, end_offset=1),
            _result(1, machine_id="MC_B", start_offset=2, end_offset=3),
        ],
        allowed_op_ids={1},
        reason="duplicate_schedule_rows",
    )

    assert details.get("sample_op_ids") == [1], details
    assert details.get("count") == 1, details


@pytest.mark.parametrize(
    "invalid_result, expected_text",
    [
        (_result(2, source="internal", machine_id=None, operator_id="OP_A"), "internal 工序必须有设备和人员"),
        (_result(2, source="internal", machine_id="MC_A", operator_id=None), "internal 工序必须有设备和人员"),
        (
            make_schedule_result(
                op_id=2,
                op_code="B001_02",
                batch_id="B001",
                seq=2,
                machine_id="MC_A",
                operator_id="OP_A",
                start_time="2026-01-01 08:00:00",
                end_time=_make_dt(1),
                source="internal",
                op_type_name="A",
            ),
            "start_time/end_time 必须是有效时间",
        ),
        (_result(2, source="legacy", machine_id="MC_A", operator_id="OP_A"), "source 必须是 internal 或 external"),
    ],
)
def test_schedule_payload_rejects_invalid_persist_rows_before_any_valid_save(invalid_result, expected_text) -> None:
    valid = _result(1, machine_id="MC_A", operator_id="OP_A", start_offset=0, end_offset=1)

    details = _assert_validation_reason(
        [valid, invalid_result],
        allowed_op_ids={1, 2},
        reason="invalid_schedule_rows",
    )

    assert expected_text in "\n".join(details.get("validation_errors") or []), details


def test_schedule_payload_rejects_result_source_that_disagrees_with_operation_source() -> None:
    valid = _result(1, machine_id="MC_A", operator_id="OP_A", source="internal")
    wrong_source = _result(2, machine_id="MC_A", operator_id="OP_A", source="external")
    operations = _operations({1: "internal", 2: "internal"})

    with pytest.raises(ValidationError) as exc_info:
        _build_payload([valid, wrong_source], allowed_op_ids={1, 2}, operations=operations)

    details = dict(getattr(exc_info.value, "details", {}) or {})
    assert details.get("reason") == "invalid_schedule_rows", details
    assert "source 与原工序不一致" in "\n".join(details.get("validation_errors") or []), details


def _seed_common(conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P001", "part", "yes"))
    conn.execute(
        """
        INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("B001", "P001", "part", 1, "2026-01-10", "normal", "yes", "pending"),
    )
    for machine_id in ("MC_A", "MC_B", "MC_C", "MC_D", "MC_KEEP"):
        conn.execute(
            "INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)",
            (machine_id, machine_id, "active"),
        )
    for operator_id in ("OP_A", "OP_B", "OP_C", "OP_D", "OP_KEEP"):
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)",
            (operator_id, operator_id, "active"),
        )
    conn.executemany(
        """
        INSERT INTO BatchOperations
        (id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                op_id,
                f"B001_{op_id:02d}",
                "B001",
                None,
                op_id,
                "OT_A",
                "A",
                source,
                machine_id,
                operator_id,
                None,
                1.0,
                0.0,
                None,
                "pending",
            )
            for op_id, source, _label, machine_id, operator_id in rows
        ],
    )
    conn.commit()


def test_schedule_schema_rejects_duplicate_version_op_rows() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(conn, [(1, "internal", "missing", None, None)])
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "MC_A", "OP_A", "2026-01-01 08:00:00", "2026-01-01 09:00:00", "unlocked", 21),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "MC_B", "OP_B", "2026-01-01 10:00:00", "2026-01-01 11:00:00", "unlocked", 21),
            )
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "MC_B", "OP_B", "2026-01-01 10:00:00", "2026-01-01 11:00:00", "unlocked", 22),
        )
    finally:
        conn.close()


def test_whitespace_padded_resource_identities_stay_distinct_from_trimmed_siblings() -> None:
    from types import SimpleNamespace

    from core.algorithm_contracts.ordering import clean_resource_id
    from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence
    from core.algorithms.evaluation import compute_metrics
    from core.algorithms.greedy.auto_assign import prepare_resource_candidates
    from core.errors import AppError
    from core.models.operation_execution_scope import EXECUTION_STATUS_COMPLETED
    from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.id_policy import display_id, make_machine_node_id
    from core.services.scheduler.graph.resource_matching import summarize_operation_machine_matching
    from core.services.scheduler.graph.types import OperationGraphNode
    from core.services.scheduler.resource_pool_builder import CapturedResourceFacts, build_resource_pool
    from core.services.scheduler.run.optimizer.neighborhood_move_support import pick_resource_pair
    from core.services.scheduler.run.optimizer.neighborhood_moves import resource_alternative_move
    from core.services.scheduler.run.schedule_execution_guardrails import (
        build_execution_guardrails_from_projections,
    )
    from core.services.scheduler.run.schedule_execution_persistence_guard import (
        validate_execution_guard_before_persist,
    )
    from core.services.scheduler.run.schedule_input_runtime_support import (
        prepare_runtime_seeds,
    )
    from core.services.scheduler.run.schedule_payload_contract import arrangement_row
    from core.services.workbench.facts.zero_duration import PointEventError, estimate_point_event
    from tests._support.algo_operations import make_algo_op, make_batch

    # 1. clean_resource_id / id_policy / OperationGraphNode / 点事件见证均保留 " M1 " 且将纯空白视作未分配
    assert clean_resource_id(" M1 ") == " M1 "
    assert clean_resource_id("M1") == "M1"
    assert clean_resource_id("   ") == ""
    assert clean_resource_id(None) == ""
    assert clean_resource_id(" M1 ") != clean_resource_id("M1")
    assert clean_resource_id(None) == clean_resource_id("   ")

    node_id = make_machine_node_id(" M1 ")
    assert node_id == "machine: M1 "
    assert display_id(node_id) == " M1 "

    at = _make_dt(0)
    point_evidence = SchedulePointEvidence(
        op_id=1,
        machine_id=" M1 ",
        operator_id=" O1 ",
        at=at,
        setup_hours=0.0,
        unit_hours=0.0,
        quantity=1,
    )
    padded_row = arrangement_row(
        {
            "op_id": 1,
            "machine_id": " M1 ",
            "operator_id": " O1 ",
            "start_time": at,
            "end_time": at,
            "source": "internal",
        }
    )
    trimmed_row = arrangement_row(
        {
            "op_id": 1,
            "machine_id": "M1",
            "operator_id": "O1",
            "start_time": at,
            "end_time": at,
            "source": "internal",
        }
    )
    assert point_evidence.matches(padded_row)
    assert not point_evidence.matches(trimmed_row)

    class _PointCalendar:
        def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None) -> datetime:
            return dt

        def add_effective_hours(self, dt: datetime, hours: float, priority=None, operator_id=None) -> datetime:
            return dt + timedelta(hours=float(hours))

        def working_hours_between(self, start: datetime, end: datetime, priority=None, operator_id=None) -> float:
            return (end - start).total_seconds() / 3600.0

    assert estimate_point_event(
        _PointCalendar(),
        setup_hours=0.0,
        unit_hours=0.0,
        quantity=1,
        machine_id=" M1 ",
        operator_id=" O1 ",
        priority="normal",
        start=at,
    ) == (at, at)
    with pytest.raises(PointEventError):
        estimate_point_event(
            _PointCalendar(),
            setup_hours=0.0,
            unit_hours=0.0,
            quantity=1,
            machine_id="   ",
            operator_id=" O1 ",
            priority="normal",
            start=at,
        )

    # 2. 完工种子、冻结种子合并与持久化守卫不允许 " M1 " 漂移到 "M1"
    op = make_batch_operation(id=1, op_code="B001_01", batch_id="B001", seq=1, source="internal")
    fact = ExecutionFact(
        op_id=1,
        batch_id="B001",
        actual_status=EXECUTION_STATUS_COMPLETED,
        actual_start_time=_make_dt(0),
        actual_end_time=_make_dt(1),
        actual_machine_id=" M1 ",
        actual_operator_id=" O1 ",
        ledger_operation_ref="op-ref-1",
        ledger_execution_state="complete",
        execution_effective_intervals=((_make_dt(0), _make_dt(1)),),
        target_quantity=1,
    )
    guardrail_facts = SimpleNamespace(resource_execution={1: ({1: fact}, {1: {"op_id": 1}}, "snap-1")})
    _, completed_ids, seeds, _ = build_execution_guardrails_from_projections(
        None,
        [op],
        prev_version=1,
        execution_projections=[],
        facts=guardrail_facts,
    )
    assert completed_ids == {1} and len(seeds) == 1
    seed = seeds[0]
    assert (seed["machine_id"], seed["operator_id"]) == (" M1 ", " O1 ")

    with pytest.raises(AppError) as conflict_exc:
        prepare_runtime_seeds(
            sqlite3.connect(":memory:"),
            run_label="排产",
            batches={"B001": make_batch(batch_id="B001")},
            operations=[op],
            algo_ops=[make_algo_op(id=1, op_code="B001_01", batch_id="B001", seq=1)],
            frozen_op_ids={1},
            freeze_seed_results=[{**seed, "machine_id": "M1"}],
            execution_completed_op_ids={1},
            execution_seed_results=[seed],
            raise_schedule_empty_result_fn=lambda *_a, **_kw: None,
            validate_fixed_operator_qualifications_fn=lambda *_a, **_kw: None,
        )
    assert conflict_exc.value.details is not None
    assert conflict_exc.value.details["reason"] == "execution_seed_conflict"

    prepared_guard = SimpleNamespace(
        execution_facts={1: fact},
        execution_completed_op_ids={1},
        algo_ops=[],
        operations=[],
    )
    validate_execution_guard_before_persist(
        prepared_guard,
        validated_schedule_payload=SimpleNamespace(schedule_rows=[arrangement_row(seed)]),
    )
    with pytest.raises(AppError) as guard_exc:
        validate_execution_guard_before_persist(
            prepared_guard,
            validated_schedule_payload=SimpleNamespace(schedule_rows=[arrangement_row({**seed, "machine_id": "M1"})]),
        )
    assert guard_exc.value.details is not None
    assert guard_exc.value.details["reason"] == "execution_completed_resource_moved"

    # 3. 图指标、二分图设备匹配与评估指标中 " M1 " 与 "M1" 计为 2 台不同设备
    graph_nodes = [
        OperationGraphNode(
            node_id="op:1",
            batch_id="B001",
            op_code="B001_01",
            seq=1,
            duration_minutes=60,
            machine_id=" M1 ",
            candidate_machine_ids=(" M1 ", "M1"),
        ),
        OperationGraphNode(
            node_id="op:2",
            batch_id="B002",
            op_code="B002_01",
            seq=1,
            duration_minutes=60,
            machine_id="M1",
            candidate_machine_ids=(" M1 ", "M1"),
        ),
    ]
    assert graph_nodes[0].candidate_machine_ids == (" M1 ", "M1")
    matching = summarize_operation_machine_matching(graph_nodes)
    assert matching.machine_count == 2
    assert matching.matched_operation_count == 2
    assert {item.machine_id for item in matching.matches} == {" M1 ", "M1"}

    graph_summary = ScheduleGraphAnalysisService().analyze_precedence(graph_nodes, [])
    # 两道 60 分钟工序共享 2 台候选设备 (" M1 ", "M1")，每台分摊 60 分钟 = 1.0h，折扣 sqrt(2)
    assert graph_summary.node_metrics["op:1"]["bottleneck_machine_score"] == round(1.0 / (2.0 ** 0.5), 6)

    eval_metrics = compute_metrics(
        [
            _result(1, machine_id=" M1 ", operator_id=" O1 ", start_offset=0, end_offset=1),
            _result(2, machine_id="M1", operator_id="O1", start_offset=0, end_offset=1),
        ],
        {"B001": make_batch(batch_id="B001", due_date="2026-01-02")},
        expected_operations=[
            make_algo_op(id=1, op_code="B001_01", batch_id="B001", seq=1),
            make_algo_op(id=2, op_code="B001_02", batch_id="B001", seq=2),
        ],
        seed_occupancies_by_op_id={},
        failure_details=(),
    )
    assert eval_metrics.machine_used_count == 2
    assert eval_metrics.operator_used_count == 2

    # 4. 资源池构建、资格过滤与邻域备选动作均忽略纯空白 '   ' 并原样保留 ' M1 '
    open_op = make_algo_op(
        id=10,
        op_code="B001_10",
        batch_id="B001",
        seq=10,
        op_type_id="OT_A",
        op_type_name="A",
        source="internal",
        machine_id=None,
        operator_id=None,
    )
    resource_facts = CapturedResourceFacts(
        {
            "Machines": [
                {"machine_id": "   ", "name": "BlankM", "op_type_id": "OT_A", "category": None, "status": "active", "remark": None, "team_id": None, "created_at": None, "updated_at": None},
                {"machine_id": " M1 ", "name": "PaddedM", "op_type_id": "OT_A", "category": None, "status": "active", "remark": None, "team_id": None, "created_at": None, "updated_at": None},
            ],
            "MachineOpTypes": [{"machine_id": "   ", "op_type_id": "OT_A"}],
            "Operators": [
                {"operator_id": "   ", "name": "BlankO", "status": "active", "remark": None, "team_id": None},
                {"operator_id": "O1", "name": "Op1", "status": "active", "remark": None, "team_id": None},
                {"operator_id": "O2", "name": "Op2", "status": "active", "remark": None, "team_id": None},
            ],
            "OperatorMachine": [
                {"operator_id": "   ", "machine_id": "   ", "skill_level": "high", "is_primary": "yes"},
                {"operator_id": "O1", "machine_id": "   ", "skill_level": "high", "is_primary": "yes"},
                {"operator_id": "   ", "machine_id": " M1 ", "skill_level": "high", "is_primary": "yes"},
                {"operator_id": "O1", "machine_id": " M1 ", "skill_level": "high", "is_primary": "yes"},
                {"operator_id": "O2", "machine_id": " M1 ", "skill_level": "normal", "is_primary": "no"},
            ],
            "WorkbenchOperatorProfiles": [
                {"operator_id": "   ", "skills_declared": 1},
                {"operator_id": "O1", "skills_declared": 1},
                {"operator_id": "O2", "skills_declared": 1},
            ],
            "OpTypes": [{"op_type_id": "OT_A", "name": "A", "category": "internal"}],
            "OperatorSkill": [
                {"operator_id": "   ", "op_type_id": "OT_A", "skill_level": "high", "is_primary": "yes"},
                {"operator_id": "O1", "op_type_id": "OT_A", "skill_level": "high", "is_primary": "yes"},
                {"operator_id": "O2", "op_type_id": "OT_A", "skill_level": "normal", "is_primary": "no"},
            ],
        },
        {},
    )
    pool = build_resource_pool(
        cfg=SimpleNamespace(auto_assign_enabled="yes"),
        algo_ops=[open_op],
        resource_facts=resource_facts,
    )
    assert pool is not None
    assert pool["machines_by_op_type"]["OT_A"] == [" M1 "]
    assert pool["operators_by_machine"] == {" M1 ": ["O1", "O2"]}
    assert prepare_resource_candidates(open_op, pool).pairs == ((" M1 ", "O1"), (" M1 ", "O2"))

    picked = pick_resource_pair(pool)
    assert picked is not None and picked[:2] == ("O2", " M1 ")
    move = resource_alternative_move(["B001"], pool)
    assert move.resource_pair_rank == {("O2", " M1 "): -1}
