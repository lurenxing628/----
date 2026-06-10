"""回归测试：_baseline_missing_or_failed 四态 parity（R03-B/O25 收口）——None（空候选列表）与 missing（有候选但无 baseline kind）两态走「无基准方案」路径返回 True 且生产可达（真实用户告警源头，禁当死分支裸删下游消费）；failed（baseline 状态为 failed）返回 True（该半边生产不可达但随已落库 ScheduleCandidate.status 枚举契约保留，禁裸删枚举）；completed（baseline 算完）返回 False。四态逐分支钉死，防「笼统删除不可达管道时连带吞掉 baseline 缺失活告警」。"""

from __future__ import annotations

from core.services.scheduler.run import schedule_candidate_runner as runner
from core.services.scheduler.run.schedule_candidate_runner import (
    CANDIDATE_STATUS_COMPLETED,
    CANDIDATE_STATUS_FAILED,
    CandidatePlan,
)


def _plan(kind: str, status: str) -> CandidatePlan:
    return CandidatePlan(
        sequence=0,
        candidate_key=f"{kind}-{status}",
        kind=kind,
        label=f"{kind}方案",
        status=status,
        score=None,
        graph_critical_weight=0,
        graph_impact_weight=0,
        graph_downstream_weight=0,
    )


def test_none_state_empty_candidates_is_missing_true() -> None:
    assert runner._baseline_missing_or_failed([]) is True, "空候选列表走 missing 路径必须 True（生产可达）"


def test_missing_state_no_baseline_kind_is_true() -> None:
    plans = [_plan("graph_focus", CANDIDATE_STATUS_COMPLETED)]
    assert runner._baseline_missing_or_failed(plans) is True, "无 baseline kind 候选必须 True（生产可达）"


def test_failed_state_baseline_failed_is_true() -> None:
    plans = [_plan("baseline", CANDIDATE_STATUS_FAILED)]
    assert runner._baseline_missing_or_failed(plans) is True, (
        "failed 半边语义保留：baseline 状态≠completed 必须 True（生产不可达但枚举契约在册）"
    )


def test_completed_state_baseline_completed_is_false() -> None:
    plans = [_plan("baseline", CANDIDATE_STATUS_COMPLETED)]
    assert runner._baseline_missing_or_failed(plans) is False, "baseline 算完必须 False（不误报告警）"
