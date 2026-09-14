"""回归测试：排产进度账本——worker 每算完一个候选方案就上报 (done, total)，查询服务只在 running/computing 时附带进度，账本本身拒绝非法计数。"""

from types import SimpleNamespace

import pytest

import core.services.scheduler.run.schedule_candidate_runner as runner
from core.services.workbench import run_progress
from core.services.workbench.run_jobs import _with_progress
from tests.candidate.test_scheduler_candidate_runner_contract import _outcome, _schedule_input, _StepClock

RUN_REF = "a" * 48


@pytest.fixture(autouse=True)
def _clean_ledger():
    run_progress.clear_progress(RUN_REF)
    yield
    run_progress.clear_progress(RUN_REF)


def test_ledger_reports_reads_and_clears_per_run():
    assert run_progress.read_progress(RUN_REF) is None
    run_progress.report_progress(RUN_REF, 1, 4, "2026-09-13T10:00:00")
    run_progress.report_progress(RUN_REF, 2, 4, "2026-09-13T10:00:05")
    assert run_progress.read_progress(RUN_REF) == {"done": 2, "total": 4, "updated_at": "2026-09-13T10:00:05"}
    run_progress.clear_progress(RUN_REF)
    assert run_progress.read_progress(RUN_REF) is None


@pytest.mark.parametrize("done,total,updated_at", [(-1, 4, "t"), (5, 4, "t"), (1, 4, ""), (1.0, 4, "t"), (1, "4", "t")])
def test_ledger_rejects_invalid_progress(done, total, updated_at):
    with pytest.raises(ValueError):
        run_progress.report_progress(RUN_REF, done, total, updated_at)
    assert run_progress.read_progress(RUN_REF) is None


def test_candidate_comparison_reports_each_finished_candidate_in_order():
    seen = []

    def prepare_graph(schedule_input):
        return SimpleNamespace(graph_analysis_public=None, graph_analysis_diagnostics=None,
                               graph_ready_context=None, graph_dispatch_mode_override=None)

    def optimize(**kwargs):
        return _outcome("x", score=(0, 0, 10), tardiness=10.0)

    outcome = runner.run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=prepare_graph, optimize_schedule_fn=optimize,
        weight_count=3, selection_policy="score_only", clock=_StepClock([0] * 100),
        on_progress=lambda done, total: seen.append((done, total)),
    )
    total = len(outcome.candidates)
    assert total >= 2
    assert seen == [(index, total) for index in range(1, total + 1)]


def test_candidate_comparison_without_sink_is_unchanged():
    def prepare_graph(schedule_input):
        return SimpleNamespace(graph_analysis_public=None, graph_analysis_diagnostics=None,
                               graph_ready_context=None, graph_dispatch_mode_override=None)

    def optimize(**kwargs):
        return _outcome("x", score=(0, 0, 10), tardiness=10.0)

    outcome = runner.run_candidate_comparison(
        schedule_input=_schedule_input(), prepare_graph_fn=prepare_graph, optimize_schedule_fn=optimize,
        weight_count=3, selection_policy="score_only", clock=_StepClock([0] * 100),
    )
    assert len(outcome.candidates) >= 2


def _payload(state, stage):
    return {"run_ref": RUN_REF, "state": state, "stage": stage, "progress": None}


def test_query_payload_carries_progress_only_while_computing():
    run_progress.report_progress(RUN_REF, 2, 4, "2026-09-13T10:00:05")
    assert _with_progress(_payload("running", "computing"))["progress"] == {"done": 2, "total": 4, "updated_at": "2026-09-13T10:00:05"}
    assert _with_progress(_payload("queued", "queued"))["progress"] is None
    assert _with_progress(_payload("running", "awaiting_reconciliation"))["progress"] is None
    assert _with_progress(_payload("complete", "finished"))["progress"] is None
    assert _with_progress(None) is None
    run_progress.clear_progress(RUN_REF)
    assert _with_progress(_payload("running", "computing"))["progress"] is None
