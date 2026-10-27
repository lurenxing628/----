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
        "no_admission_baseline": "排产时没有正式计划可供对比。",
        "no_baseline_operation": "此工序在初始计划中未安排。",
        "candidate_operation_unscheduled": "此候选方案未安排该工序。",
        "outside_selected_batches": "这道工序只在排产时的正式计划里，不在这次选择的范围内。",
        "baseline_multiple_segments": "此工序在初始计划中有多段安排，请逐段查看。",
        "baseline_interval_unavailable": "初始计划的起止时间无效，或等时安排缺少零工时采用依据，无法比较。",
        "execution_affected": "排产时此工序已开工或数量不明。",
        "effective_hours_not_recorded": "初始计划未记录有效加工工时。",
        "historical_supplier_not_recorded": "初始计划未记录供应商安排。",
        "historical_source_unavailable": "原安排的自制或外协来源缺少可核对依据。",
        "not_an_optimization_score": "安排变动对比。",
        "no_comparable_operations": "这次范围里没有能核对并一一对应的安排。",
        "resource_identity_unavailable": "有一边没有可核对的设备人员编号，资源有没有变不清楚。",
    }
    return {"code": code, "message": messages[code]}


def elapsed_hours(start, end):
    """Wall-clock interval only. A real zero is kept, never replaced by a default."""
    return (local_time(end) - local_time(start)).total_seconds() / 3600


def _resource_identity(side, kind):
    resource = side[kind]
    if resource is not None:
        return resource["ref"] is not None, resource["ref"]
    known = not any(row["field"] in (kind, kind + ".ref") for row in side["data_gaps"])
    return known, None


def _resource_change(before, after, kind):
    previous, current = _resource_identity(before, kind), _resource_identity(after, kind)
    return previous[1] != current[1] if previous[0] and current[0] else None


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
            or execution["data_quality"] in (None, "invalid"))


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
                         machine_changed=_resource_change(baseline, candidate, "machine"),
                         operator_changed=_resource_change(baseline, candidate, "operator"),
                         supplier_changed=_resource_change(baseline, candidate, "supplier"))
            if delta["machine_changed"] is None or delta["operator_changed"] is None:
                reasons.append(baseline_reason("resource_identity_unavailable"))
            if candidate["source"] == "external" and delta["supplier_changed"] is None:
                reasons.append(baseline_reason("historical_supplier_not_recorded"))
        return {**self.labels, "operation_ref": self.operation_ref, "row_ref": self.row_ref,
                "candidate": candidate, "baseline_segments": segments,
                "selected_at_admission": self.selected, "candidate_operation_status": self.candidate_status,
                "status": status, "comparison_available": status == "matched", "delta": delta,
                "execution_affected": affected, "improvement_assessment": None, "reasons": reasons}
