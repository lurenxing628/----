"""Admission-baseline read scope and descriptive comparison DTOs, not plan scores."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.models.workbench_run_candidate import RunCandidateReadScope, local_time


@dataclass(frozen=True)
class RunCandidateBaselineScope(RunCandidateReadScope):
    def scope(self):
        return {**super().scope(), "kind": "run-candidate-baseline"}


def baseline_reason(code):
    messages = {
        "no_admission_baseline": "排产时没有正式的初始计划，算不出相对改善。",
        "no_baseline_operation": "排产时的正式计划里没有这道工序，新排上不算改善。",
        "candidate_operation_unscheduled": "该候选没有安排此工序，不能把未排当作工期缩短。",
        "outside_selected_batches": "这道工序只在排产时的正式计划里，不在这次选择的范围内。",
        "baseline_multiple_segments": "初始计划里这道工序分成了几段，这里不合并也不任选一段来对照。",
        "baseline_interval_unavailable": "初始计划的起止时间不对或时长为 0，没有推算工时。",
        "execution_affected": "排产时这道工序已经开工或数量不明，时间差不能算成排产优化。",
        "effective_hours_not_recorded": "初始计划没有记有效加工小时，起止时长不等于有效工时。",
        "historical_supplier_not_recorded": "初始计划没有保存供应商安排，这里不用排产时的工艺设置代替。",
        "not_an_optimization_score": "仅描述已保存安排的变化，不评价收益或把未排视为改善。",
        "no_comparable_operations": "这次范围里没有能一一对上的有工时安排。",
        "resource_identity_unavailable": "有一边没有可核对的设备人员编号，资源有没有变不清楚。",
        "input_digest_not_recorded": "排产时的输入没有单独存摘要；这里只核对了结构、编号范围和明细，不算完整独立核对。",
    }
    return {"code": code, "message": messages[code]}


def elapsed_hours(start, end):
    """Wall-clock interval only. A real zero is kept, never replaced by a default."""
    return (local_time(end) - local_time(start)).total_seconds() / 3600


def _resource_change(before, after):
    if before is None or after is None:
        return None
    if before["ref"] is None or after["ref"] is None:
        return None
    return before["ref"] != after["ref"]


def _comparison_state(candidate, segments, selected):
    reasons = []
    if candidate is None:
        status = "unscheduled" if selected else "baseline_only"
        reasons.append(baseline_reason("candidate_operation_unscheduled" if selected else "outside_selected_batches"))
    elif not segments:
        status = "newly_scheduled"
        reasons.append(baseline_reason("no_baseline_operation"))
    elif len(segments) != 1:
        status = "not_comparable"
    elif not segments[0]["interval_comparable"]:
        status = "not_comparable"
    else:
        status = "matched"
    if len(segments) > 1:
        reasons.append(baseline_reason("baseline_multiple_segments"))
    if any(not row["interval_comparable"] for row in segments):
        reasons.append(baseline_reason("baseline_interval_unavailable"))
    return status, reasons


def _execution_affected(execution):
    return (execution is None or execution["execution_state"] != "unreported"
            or execution["known_completed_quantity"] != 0 or execution["remaining_quantity"] is None
            or execution["data_quality"] in (None, "invalid", "legacy_incomplete"))


@dataclass(frozen=True)
class RunBaselineComparison:
    operation_ref: str
    row_ref: Optional[str]
    labels: Dict[str, Any]
    candidate: Optional[Dict[str, Any]]
    baseline_segments: List[Dict[str, Any]]
    selected: bool
    candidate_status: Optional[str]

    def to_dict(self):
        candidate, segments = self.candidate, self.baseline_segments
        status, reasons = _comparison_state(candidate, segments, self.selected)
        affected = _execution_affected(self.labels["execution_at_generation"])
        if affected:
            reasons.append(baseline_reason("execution_affected"))
        delta: Dict[str, Any] = dict(start_hours=None, end_hours=None, elapsed_hours=None, machine_changed=None,
                                    operator_changed=None, supplier_changed=None, effective_processing_hours=None)
        if status == "matched" and candidate is not None:
            baseline = segments[0]
            delta.update(start_hours=elapsed_hours(baseline["start"], candidate["start"]),
                         end_hours=elapsed_hours(baseline["end"], candidate["end"]),
                         elapsed_hours=candidate["elapsed_hours"] - baseline["elapsed_hours"],
                         machine_changed=_resource_change(baseline["machine"], candidate["machine"]),
                         operator_changed=_resource_change(baseline["operator"], candidate["operator"]))
            if delta["machine_changed"] is None or delta["operator_changed"] is None:
                reasons.append(baseline_reason("resource_identity_unavailable"))
        return {**self.labels, "operation_ref": self.operation_ref, "row_ref": self.row_ref,
                "candidate": candidate, "baseline_segments": segments,
                "selected_at_admission": self.selected, "candidate_operation_status": self.candidate_status,
                "status": status, "comparison_available": status == "matched", "delta": delta,
                "execution_affected": affected, "improvement_assessment": None, "reasons": reasons}
