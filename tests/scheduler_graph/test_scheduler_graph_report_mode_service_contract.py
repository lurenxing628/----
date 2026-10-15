"""工作台实际计算保留 report/on 图分析、冻结种子及排程结果。"""

from dataclasses import asdict

import pytest

from core.services.workbench.run.compute import compute_candidate_run
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


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
        outcomes[mode] = unchanged(case, lambda: compute_candidate_run(case.conn, settings, case.projections()))

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
