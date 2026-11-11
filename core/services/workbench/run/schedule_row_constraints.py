"""Shared row-level resource, readiness, timing and predecessor constraint operators."""

from __future__ import annotations

from collections.abc import Mapping as AbcMapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import issue
from core.services.personnel.operator_qualification import OperatorQualificationError
from core.services.workbench.facts.zero_duration import internal_duration_hours
from core.shared.stored_dates import stored_date, stored_day

from .input_config import window_label

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch
    from core.services.workbench.facts.archived_calendar import DowntimeIndex

HOLD_WINDOW_RERUN_NOTE = "这道工序如要改排，请重新排产，并在排产检查里把不重排时段改短或不设。"


@dataclass(frozen=True)
class PredecessorNode:
    key: Any
    op_id: int
    predecessor_keys: Sequence[Any]
    span: Optional[Tuple[datetime, datetime]]
    cycle_token: Any
    merged_group_key: Optional[Tuple[Any, Any, Any]]
    task_ref: Optional[str] = None


@dataclass(frozen=True)
class PredecessorViolation:
    kind: str
    op_id: int
    task_ref: Optional[str] = None
    related_task_ref: Optional[str] = None


def resource_gaps(
    checks: Any,
    batch: Any,
    op: Any,
    *,
    protected_cycle: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    if protected_cycle:
        return checks.protected_resources(op), [], []
    return [], checks.fields(batch, op), checks.resources(op)


def readiness_issues(
    checks: Any,
    batch: Any,
    op: Any,
    start: datetime,
    policy: Mapping[str, Any],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    problems, material_day = checks.operation_readiness(batch, op, policy)
    # SQLite DECLTYPES returns date objects in the application; snapshots use ISO text.
    # batch_model has already rejected invalid dates using the same parser.
    late_material_day = material_day if material_day and start < datetime.fromisoformat(material_day) else None
    return problems, late_material_day


def readiness_problem(
    checks: Any,
    batch: Mapping[str, Any],
    op: Mapping[str, Any],
    start: datetime,
    policy: Mapping[str, Any],
) -> Optional[str]:
    problems, late_material_day = readiness_issues(checks, batch, op, start, policy)
    if problems:
        return "material_not_ready"
    if late_material_day is not None:
        return "before_material"
    ready_day = stored_date(batch["ready_date"])
    if policy["ready_check"] and ready_day is not None and start < datetime.fromisoformat(ready_day):
        return "before_ready_date"
    return None


def arrangement_problem(
    checks: Any,
    batch: Mapping[str, Any],
    raw: Mapping[str, Any],
    start_time: datetime,
    settings: Mapping[str, Any],
) -> Optional[str]:
    """一条非实际安排按现在的资料还成不成立：工序资料和设备人员资格、物料到齐日、齐套日期。

    batch、raw 是原始行，raw 的设备人员换成安排行自己的。返回第一处不成立的原因码，都成立返回 None。
    候选采用逐行复核与排产检查核对不重排时段保留的原安排共用这一口径。
    """
    _protected_gaps, field_gaps, res_gaps = resource_gaps(checks, batch, raw, protected_cycle=False)
    if field_gaps or res_gaps:
        return "resource_invalid"
    return readiness_problem(checks, batch, raw, start_time, settings)


def calendar_duration_conflict(
    calendar: Any,
    row: Any,
    op: OpForScheduleAlgo,
    batch: Batch,
    machine_downtimes: Sequence[Any],
    *,
    quantity: Any,
) -> bool:
    """按真实班次、效率、停机和工时从安排的开工时刻重算一遍；开完工对不上即冲突。"""
    total = internal_duration_hours(op.setup_hours, op.unit_hours, quantity)
    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id=row.machine_id,
        operator_id=row.operator_id,
        base_time=row.start_time,
        prev_end=row.start_time,
        machine_timeline=(),
        operator_timeline=(),
        end_dt_exclusive=None,
        machine_downtimes=machine_downtimes,
        last_op_type_by_machine=None,
        abort_after=None,
        total_hours_base=total,
    )
    return estimate.start_time != row.start_time or estimate.end_time != row.end_time


def external_holds_resources(row_or_dict: Any) -> bool:
    """外协安排不能占本厂设备人员。"""
    if isinstance(row_or_dict, AbcMapping):
        return row_or_dict["machine_ref"] is not None or row_or_dict["operator_ref"] is not None
    return row_or_dict.machine_id is not None or row_or_dict.operator_id is not None


def batch_ready_datetime(batch: Mapping[str, Any], cache: Dict[str, datetime]) -> datetime:
    batch_id = batch["batch_id"]
    if batch_id not in cache:
        day = stored_day(batch["ready_date"])
        if day is None:
            raise ValueError("Invalid batch ready_date")
        cache[batch_id] = datetime(day.year, day.month, day.day)
    return cache[batch_id]


def stored_operator_profile_valid(
    qualification: Any,
    qualification_cache: Dict[str, bool],
    operator_id: str,
) -> bool:
    if operator_id not in qualification_cache:
        try:
            qualification.qualifications_for([operator_id])
            qualification_cache[operator_id] = True
        except OperatorQualificationError:
            qualification_cache[operator_id] = False
    return qualification_cache[operator_id]


def machine_downtime_issues(
    downtime_index: DowntimeIndex, start: datetime, end: datetime, *, task_ref: str
) -> List[Dict[str, Any]]:
    if downtime_index.invalid_interval:
        raise ValueError("Invalid machine downtime interval")
    issues: List[Dict[str, Any]] = []
    if downtime_index.unknown_status:
        issues.append(issue("downtime_state_unknown", "设备停机状态不明确。", task_ref))
    if downtime_index.overlaps(start, end):
        issues.append(issue("machine_downtime", "目标安排与实际设备停机重叠。", task_ref))
    return issues


def append_frozen_note(
    item: Mapping[str, Any], frozen_seed: Mapping[str, Any]
) -> Dict[str, Any]:
    """按时段保留、试调不能改的工序上查出的问题：补一句为什么改不了、该怎么办。"""
    label = window_label(frozen_seed["hold_window"])
    suffix = (
        f"这道工序因来源排产的不重排时段（{label}）要保持原安排，试调不能改，正式采用会被拦下。"
        + HOLD_WINDOW_RERUN_NOTE
    )
    return {**item, "message": item["message"] + suffix}


def iter_predecessor_violations(
    nodes: Sequence[PredecessorNode],
    *,
    outside_completed_ends: Mapping[Any, datetime],
) -> Iterator[PredecessorViolation]:
    by_key = {node.key: node for node in nodes}
    for node in nodes:
        for pred_key in node.predecessor_keys:
            previous = by_key.get(pred_key)
            if previous is None:
                if pred_key not in outside_completed_ends:
                    yield PredecessorViolation("predecessor_missing", node.op_id, node.task_ref)
                    continue
                if node.span is not None and outside_completed_ends[pred_key] > node.span[0]:
                    yield PredecessorViolation("precedence_violation", node.op_id, node.task_ref)
                continue
            if node.merged_group_key is not None and node.merged_group_key == previous.merged_group_key:
                if previous.cycle_token != node.cycle_token:
                    yield PredecessorViolation(
                        "merged_group_split", node.op_id, node.task_ref, previous.task_ref
                    )
                continue
            if previous.span is not None and node.span is not None and previous.span[1] > node.span[0]:
                yield PredecessorViolation(
                    "precedence_violation", node.op_id, node.task_ref, previous.task_ref
                )


def _draft_row_resource_issues(context: Mapping[str, Any], row: Mapping[str, Any]) -> List[Dict[str, Any]]:
    original, current, ref = row["original"], row["current"], row["task_ref"]
    op = {**original["operation"], "machine_id": current["machine_id"], "operator_id": current["operator_id"]}
    batch = original["batch"]
    protected_cycle = op["id"] in context["anchors"]
    protected_gaps, field_gaps, res_gaps = resource_gaps(
        context["checks"], batch, op, protected_cycle=protected_cycle
    )
    if protected_cycle:
        return [{**item, "task_ref": ref, "severity": "blocker"} for item in protected_gaps]
    found = [{**item, "task_ref": ref, "severity": "blocker"} for item in field_gaps + res_gaps]
    if batch["priority"] not in ("normal", "urgent", "critical"):
        found.append(issue("priority_unknown", "原批次优先级无效，请核对批次资料。", ref))
    if (
        op["source"] == "internal"
        and op["operator_id"]
        and {item["code"] for item in field_gaps}.isdisjoint({"op_type_missing", "source_category_mismatch"})
    ):
        valid_profile = stored_operator_profile_valid(
            context["qualification"], context["qualification_cache"], op["operator_id"]
        )
        res_codes = {item["code"] for item in res_gaps}
        if not valid_profile or res_codes & {
            "operator_missing",
            "operator_skill_missing",
            "machine_authorization_missing",
        }:
            found.append(issue("operator_qualification_invalid", "人员工种资格或设备操作授权不符合真实登记。", ref))
    if op["source"] == "external" and external_holds_resources(current):
        found.append(issue("external_internal_resource", "外协工序不能带内部设备人员安排。", ref))
    return found


def _draft_row_time_issues(
    calendar: Any,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    effective_protected: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    original, current, ref = row["original"], row["current"], row["task_ref"]
    op_ref = row["operation_ref"]
    batch = original["batch"]
    anchor = context["anchors"].get(original["operation"]["id"])
    actual = anchor is not None and anchor["basis"] == "completed_actuals"
    fixed_cycle = anchor is not None and anchor["basis"] == "merged_external_actuals"
    trial_intervals = context["trial_intervals"]
    found: List[Dict[str, Any]] = []
    try:
        if op_ref in trial_intervals["current_errors_by_op"]:
            raise trial_intervals["current_errors_by_op"][op_ref].with_traceback(None)
        start, end = trial_intervals["current_by_op"][op_ref]
        if effective_protected is None and calendar.engine is not None:
            point_proven = row["row_ref"] in trial_intervals["original_points_by_row"]
            est_start, est_end = context["estimate_fn"](row, start, point_proven)
            if start != est_start or end != est_end:
                found.append(issue("calendar_duration_conflict", "开完工与原工时、真实日历或效率不一致。", ref))
        if (
            not actual
            and not fixed_cycle
            and context["settings"]["ready_check"]
            and batch["ready_date"]
            and start < batch_ready_datetime(batch, context["batch_ready_dates"])
        ):
            found.append(issue("before_ready_date", "安排早于原批次可开工日期。", ref))
        if not actual and start != end:
            found.extend(
                machine_downtime_issues(calendar.downtime_index(current["machine_id"]), start, end, task_ref=ref)
            )
    except WorkbenchCommandRejected as exc:
        found.append(issue(exc.code, str(exc), ref))
    except (AppError, ValueError, TypeError, OverflowError):
        found.append(issue("calendar_unproven", "原工时、真实班次、日期或停机数据无效，未用默认数补齐。", ref))
    return found


def evaluate_draft_row(
    calendar: Any, row: Mapping[str, Any], context: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    protection_issues, effective_protected, frozen_seed = context["row_protections"][row["row_ref"]]
    found = _draft_row_resource_issues(context, row)
    found.extend(_draft_row_time_issues(calendar, row, context, effective_protected))
    if effective_protected is None:
        policy = {**context["material_policy_base"], "end_date": row["current"]["end"][:10]}
        original, current_by_op = row["original"], context["trial_intervals"]["current_by_op"]
        op_ref = row["operation_ref"]
        if op_ref in current_by_op:
            problems, late_material_day = readiness_issues(
                context["checks"], original["batch"], original["operation"], current_by_op[op_ref][0], policy
            )
        else:
            problems, _ = context["checks"].operation_readiness(
                original["batch"], original["operation"], policy
            )
            late_material_day = None
        found.extend([issue(item["code"], item["message"], row["task_ref"]) for item in problems])
        if late_material_day is not None:
            found.append(
                issue(
                    "before_material_date",
                    "安排早于本序物料到齐日期，请后移至 " + late_material_day + " 或之后。",
                    row["task_ref"],
                )
            )
    if frozen_seed is not None:
        found = [append_frozen_note(item, frozen_seed) for item in found]
    return [*protection_issues, *found]


def collect_draft_predecessor_issues(
    rows: Sequence[Mapping[str, Any]],
    live: Mapping[str, Any],
    current_by_op: Mapping[str, Tuple[datetime, datetime]],
) -> List[Dict[str, Any]]:
    in_draft = {row["operation_ref"] for row in rows}
    outside_completed_ends: Dict[str, datetime] = {}
    reported = live["execution_reported"]
    nodes: List[PredecessorNode] = []
    for row in rows:
        original, current = row["original"], row["current"]
        group = original["external_group"]
        merged_key = (
            (original["batch"]["batch_id"], group["group_id"], original["operation"]["piece_id"])
            if group and group["merge_mode"] == "merged"
            else None
        )
        pred_refs = original["predecessor_operation_refs"]
        for pred_ref in pred_refs:
            if pred_ref not in in_draft and pred_ref not in outside_completed_ends:
                parsed = reported[pred_ref]
                if parsed.execution["execution_state"] == "complete":
                    outside_completed_ends[pred_ref] = parsed.seed[1]
        nodes.append(
            PredecessorNode(
                key=row["operation_ref"],
                op_id=original["operation"]["id"],
                predecessor_keys=pred_refs,
                span=current_by_op.get(row["operation_ref"]),
                cycle_token=(current["start"], current["end"]),
                merged_group_key=merged_key,
                task_ref=row["task_ref"],
            )
        )
    found: List[Dict[str, Any]] = []
    for violation in iter_predecessor_violations(nodes, outside_completed_ends=outside_completed_ends):
        if violation.kind == "predecessor_missing":
            found.append(
                issue(
                    "predecessor_missing",
                    "前一道工序不在这份草稿里，现场也没有它已确认完工的记录，系统定不了这道工序的开工时间。请把前一道工序也放进草稿。",
                    violation.task_ref,
                )
            )
        elif violation.kind == "merged_group_split":
            found.append(
                issue(
                    "external_group_split",
                    "合并外协组的工序必须保持同一周期。",
                    violation.task_ref,
                    violation.related_task_ref,
                )
            )
        else:
            found.append(
                issue(
                    "precedence_violation",
                    "后序开工早于前序完工。",
                    violation.task_ref,
                    violation.related_task_ref,
                )
            )
    return found
