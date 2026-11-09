"""工作台实际计算保留 report/on 图分析、冻结种子及排程结果。"""

from dataclasses import asdict

import pytest

from tests.workbench.run_compute_support import compute_run, unchanged
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401


def _signature(outcome):
    summary = outcome.orchestration.result_summary_obj
    algo = summary["algo"]
    return {
        "rows": [asdict(row) for row in outcome.orchestration.validated_schedule_payload.schedule_rows],
        "counts": summary["counts"],
        "selected_batch_ids": summary["selected_batch_ids"],
        "freeze_window": algo["freeze_window"],
        "resource_pool": algo["resource_pool"],
    }


@pytest.mark.parametrize("frozen", [False, True])
def test_graph_modes_preserve_current_candidate_contract(run_case, frozen):
    case = run_case
    case.batch("B2")
    case.operation("B2")
    settings = case.settings("B1", "B2")
    if frozen:
        case.plan(1, [case.op_id])
        settings["hold_window"] = {"start": "2026-09-09T08:00", "end": "2026-09-09T09:00"}
    case.conn.commit()
    outcomes = {}
    for mode in ("off", "report", "on"):
        case.config(graph_analysis_mode=mode)
        outcomes[mode] = unchanged(case, lambda: compute_run(case.conn, settings, case.projections()))

    assert _signature(outcomes["report"]) == _signature(outcomes["off"])
    assert _signature(outcomes["on"]) == _signature(outcomes["off"])
    assert "graph_analysis" not in outcomes["off"].orchestration.result_summary_obj["algo"]
    for mode in ("report", "on"):
        summary = outcomes[mode].orchestration.result_summary_obj
        graph = summary["algo"]["graph_analysis"]
        assert graph["status"] == "available"
        assert graph["mode"] == mode
        assert graph["effective_mode"] == ("report" if mode == "report" else "graph_ready_queue")
        assert graph["input_scope"] == "all_algo_ops_with_frozen_markers"
        assert graph["total_algo_op_count"] == 2
        assert graph["reschedulable_unfrozen_op_count"] == 2 - int(frozen)
        assert graph["frozen_node_count"] == int(frozen)
        assert graph["seed_result_count"] == int(frozen)
    diagnostics = outcomes["report"].orchestration.result_summary_obj["diagnostics"]["graph_analysis"]
    assert diagnostics["node_metrics_sample"] == []
    assert diagnostics["node_metrics_count"] == 0
    assert diagnostics["node_metrics_status"] == "skipped_basic_report"


def test_merged_external_deduplicates_duration_and_external_never_consumes_internal_capacity():
    from datetime import datetime

    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
    from core.services.scheduler.graph.precedence_builder import build_linear_edges_by_batch
    from core.services.scheduler.graph.resource_matching import summarize_operation_machine_matching
    from core.services.scheduler.run.optimizer.graph.v2_capacity import (
        FixedResourceBlockingFacts,
        _candidate_machine_ids,
        _requires_auto_operator,
        _ResourcePoolView,
        residual_capacity_for_operation,
    )

    rows = [
        OpForScheduleAlgo(
            id=1,
            op_code="EXT-1",
            batch_id="B1",
            piece_id=None,
            seq=10,
            source="external",
            op_type_id="T1",
            op_type_name="Outsource",
            machine_id="M1",
            operator_id=None,
            supplier_id="S1",
            setup_hours=0.0,
            unit_hours=0.0,
            ext_merge_mode="merged",
            ext_group_id="G1",
            ext_group_total_days=2.0,
            ext_days=2.0,
        ),
        OpForScheduleAlgo(
            id=2,
            op_code="EXT-2",
            batch_id="B1",
            piece_id=None,
            seq=20,
            source="external",
            op_type_id="T1",
            op_type_name="Outsource",
            machine_id="M1",
            operator_id=None,
            supplier_id="S1",
            setup_hours=0.0,
            unit_hours=0.0,
            ext_merge_mode="merged",
            ext_group_id="G1",
            ext_group_total_days=2.0,
            ext_days=2.0,
        ),
        OpForScheduleAlgo(
            id=3,
            op_code="INT-3",
            batch_id="B1",
            piece_id=None,
            seq=30,
            source="internal",
            op_type_id="T1",
            op_type_name="Turning",
            machine_id="M1",
            operator_id="O1",
            supplier_id=None,
            setup_hours=0.0,
            unit_hours=1.0,
            ext_days=None,
            ext_group_id=None,
            ext_merge_mode=None,
            ext_group_total_days=None,
        ),
    ]
    batch = Batch(batch_id="B1", part_no="P1", quantity=1, due_date="2026-09-20")
    pool_dict = {
        "machines_by_op_type": {"T1": ["M1"]},
        "operators_by_machine": {"M1": ["O1"]},
        "machines_by_operator": {"O1": ["M1"]},
    }
    nodes = build_operation_nodes_from_rows(
        rows,
        batches={"B1": batch},
        resource_pool=pool_dict,
    )
    by_id = {n.node_id: n for n in nodes}
    assert by_id["op:1"].machine_id is None and by_id["op:1"].candidate_machine_ids == ()
    assert by_id["op:1"].external_group_key == ("B1", "G1")
    assert by_id["op:2"].external_group_key == ("B1", "G1")
    matching = summarize_operation_machine_matching(nodes)
    assert matching.ready_operation_count == 1
    assert matching.matched_operation_count == 1

    edges = build_linear_edges_by_batch(nodes)
    analysis = ScheduleGraphAnalysisService().analyze_precedence(nodes, edges, metrics_mode="full")
    assert analysis.critical_path == ["op:1", "op:2", "op:3"]
    # 2 days merged external (2880 min once, not 5760) + 60 min internal = 2940 min
    assert analysis.critical_path_minutes == 2940
    assert analysis.node_metrics["op:1"]["downstream_critical_minutes"] == 2940

    pool_view = _ResourcePoolView(pool_dict)
    ext_op = rows[0]
    assert _requires_auto_operator(ext_op, pool=pool_view) is False
    assert _candidate_machine_ids(ext_op, pool=pool_view) == ()
    prepared = FixedResourceBlockingFacts(downtime_map={}, seed_results_by_resource_id={"machine": {}, "operator": {}})
    cap = residual_capacity_for_operation(
        ext_op,
        batch=batch,
        start_dt=datetime(2026, 9, 9, 8),
        window_end=datetime(2026, 9, 20),
        calendar_service=None,
        resource_pool=pool_dict,
        prepared=prepared,
    )
    assert cap["residual_capacity_pressure"] == 0.0 and cap["candidate_machine_count"] == 0


def test_piece_run_with_zero_graph_weights_disables_score_without_missing_node_metrics(run_case):
    case = run_case
    case.conn.execute("UPDATE Batches SET quantity=1 WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET piece_id='piece-1' WHERE id=?", (case.op_id,))
    case.config(
        graph_analysis_mode="on",
        graph_critical_weight=0.0,
        graph_impact_weight=0.0,
    )
    case.conn.commit()
    outcome = compute_run(case.conn, case.settings("B1"), case.projections())
    summary = outcome.orchestration.result_summary_obj
    graph = summary["algo"]["graph_analysis"]
    diagnostics = summary["diagnostics"]["graph_analysis"]
    assert graph["status"] == "available"
    assert graph["score_enabled"] is False
    assert graph["score_metric_status"] == "disabled"
    assert graph["score_disabled_reason"] == "score_weights_zero"
    assert diagnostics["node_metrics_status"] == "skipped_basic_report"


def test_piece_merged_external_groups_preserve_piece_identity_and_prune_completed_groups():
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
    from core.services.scheduler.graph.types import OperationGraphEdge

    batch = Batch(batch_id="B1", part_no="P1", quantity=2, due_date="2026-09-20")
    rows = []
    edges = []
    next_id = 1
    prev_join = None
    # 16 sequential split-join stages: 16 * 5 = 80 nodes, 32 merged external groups.
    for stage in range(16):
        branch_tails = []
        for piece in ("P1", "P2"):
            ext1_id = next_id
            ext2_id = next_id + 1
            next_id += 2
            for op_id, seq_offset in ((ext1_id, 1), (ext2_id, 2)):
                rows.append(
                    OpForScheduleAlgo(
                        id=op_id,
                        op_code=f"EXT-{stage}-{piece}-{seq_offset}",
                        batch_id="B1",
                        piece_id=piece,
                        seq=stage * 10 + seq_offset,
                        source="external",
                        op_type_id="T1",
                        op_type_name="Outsource",
                        machine_id=None,
                        operator_id=None,
                        supplier_id="S1",
                        setup_hours=0.0,
                        unit_hours=0.0,
                        ext_merge_mode="merged",
                        ext_group_id=f"G{stage}",
                        ext_group_total_days=1.0,
                        ext_days=1.0,
                    )
                )
            if prev_join is not None:
                edges.append(OperationGraphEdge(f"op:{prev_join}", f"op:{ext1_id}"))
            edges.append(OperationGraphEdge(f"op:{ext1_id}", f"op:{ext2_id}"))
            branch_tails.append(ext2_id)
        # Chain P1 -> P2 -> join so a single path traverses both piece groups of the same ext_group_id.
        edges.append(OperationGraphEdge(f"op:{branch_tails[0]}", f"op:{branch_tails[1] - 1}"))
        join_id = next_id
        next_id += 1
        rows.append(
            OpForScheduleAlgo(
                id=join_id,
                op_code=f"JOIN-{stage}",
                batch_id="B1",
                piece_id=None,
                seq=stage * 10 + 5,
                source="internal",
                op_type_id="T1",
                op_type_name="Assembly",
                machine_id="M1",
                operator_id="O1",
                supplier_id=None,
                setup_hours=0.0,
                unit_hours=0.5,
                ext_days=None,
                ext_group_id=None,
                ext_merge_mode=None,
                ext_group_total_days=None,
            )
        )
        edges.append(OperationGraphEdge(f"op:{branch_tails[1]}", f"op:{join_id}"))
        prev_join = join_id

    nodes = build_operation_nodes_from_rows(rows, batches={"B1": batch})
    assert len(nodes) == 80
    assert nodes[0].external_group_key == ("B1", "G0", "P1")
    assert nodes[2].external_group_key == ("B1", "G0", "P2")
    # Common join operation uses full batch quantity (2 * 0.5h = 60 min).
    assert nodes[4].duration_minutes == 60

    analysis = ScheduleGraphAnalysisService().analyze_precedence(nodes, edges, metrics_mode="full")
    # Per stage: P1 merged group (1440m once) + P2 merged group (1440m once) + join (60m) = 2940m.
    assert analysis.critical_path_minutes == 16 * 2940
    assert analysis.node_metrics["op:1"]["downstream_critical_minutes"] == 16 * 2940
    assert len(analysis.critical_path) == 80
