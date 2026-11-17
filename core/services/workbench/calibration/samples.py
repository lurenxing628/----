"""D05 eligibility over execution facts and states, including exclusion evidence."""

from datetime import datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any, Dict, Mapping, Optional, Tuple, overload

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.content import content_text
from core.models.hours import HourTotals, public_hours, stored_exact_hours, sum_hours
from core.models.workbench_calibration import CalibrationLineage, issue
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.execution.quality import operation_target
from core.services.scheduler.template_lineage_query import lineage_problems
from core.shared.strict_parse import is_stored_number

# 报工工时合计由 core.models.hours 精确求和；除法结果（单件工时、建议定额、偏差百分比）在无限精度
# Fraction 域计算，再统一整形到 3 位小数、四舍五入，避免默认 28 位 Decimal 上下文截断。


def number(value) -> Optional[Fraction]:
    """读单个存储的模板工时；报工工时与合计值不经过这里。"""
    if value is None:
        return None
    if not is_stored_number(value):
        raise WorkbenchCommandRejected("storage_failure", "已保存的模板工时无效，请核对工艺模板；仍不行请联系维护人员。", 500)
    return Fraction(Decimal(str(value)))


@overload
def quantize(value: Fraction) -> Decimal:
    ...


@overload
def quantize(value: None) -> None:
    ...


def quantize(value: Optional[Fraction]) -> Optional[Decimal]:
    """把精确有理数结果按 3 位小数四舍五入（ROUND_HALF_UP），None 原样返回。"""
    if value is None:
        return None
    scaled = abs(value) * 1000
    q_int, rem = divmod(scaled.numerator, scaled.denominator)
    if rem * 2 >= scaled.denominator:
        q_int += 1
    signed = q_int if value >= 0 else -q_int
    with localcontext() as context:
        context.prec = max(400, len(str(q_int)))
        return Decimal(signed).scaleb(-3)


def _lineage_reasons(lineage, template):
    if lineage is None:
        return [issue("template_lineage_missing", "这条报工记录没有记下它是按哪道模板工序、哪个版本建的；同零件或同工序号不算对得上。")]
    if template is None or lineage.template_operation_ref != template.operation_ref:
        return [issue("template_operation_mismatch", "来源模板与当前模板不一致。")]
    if lineage.template_revision != template.revision:
        return [issue("template_revision_mismatch", "来源模板的版本和当前版本不同，不能混用。")]
    if template.source != "internal":
        return [issue("processing_basis_unconfirmed", "来源模板不是已确认的自制加工工序。")]
    return []


def _processing_metrics(
    *,
    has_reports: bool,
    total_hours: Optional[Decimal],
    all_quantities_known: bool,
    known_completed_quantity: int,
    unknown_record_count: int,
):
    reasons = []
    if not has_reports:
        reasons.append(issue("production_reports_missing", "尚无逐次报工记录，暂不能计算单件工时。"))
    elif total_hours is None:
        reasons.append(issue("processing_hours_unknown", "部分报工未填写有效加工工时。"))
    if has_reports and not all_quantities_known:
        reasons.append(issue("quantity_unknown", "至少有一次报工的数量暂无数据。"))

    exact_ratio = (
        Fraction(total_hours) / known_completed_quantity
        if total_hours is not None and known_completed_quantity
        else None
    )
    ratio = quantize(exact_ratio)
    values = {
        "completed_quantity": known_completed_quantity,
        "unknown_record_count": unknown_record_count,
        "effective_processing_hours": public_hours(total_hours),
        "unit_hours": float(ratio) if ratio is not None else None,
    }
    return values, reasons, exact_ratio


def _execution_reasons(
    *,
    operation_source: Optional[str],
    completion_basis: Optional[str],
    execution_state: str,
    quantity_complete: bool,
    unknown_record_count: int,
    target_quantity: Optional[int],
    known_completed_quantity: int,
    records_complete: bool,
    data_quality: str,
    confirmed_finish: Optional[str],
    as_of: datetime,
):
    reasons = []
    if operation_source != "internal" or completion_basis != "complete_reports":
        reasons.append(issue("processing_basis_unconfirmed", "尚未确认该工序按自制逐次报工核算加工工时。"))
    if execution_state != "complete" or not quantity_complete:
        reasons.append(issue("operation_not_complete", "累计报工数量还证明不了这道工序已经全部完工。"))
    if unknown_record_count or target_quantity is None:
        reasons.append(issue("quantity_unknown", "完成数量或目标数量暂无数据。"))
    if known_completed_quantity == 0:
        reasons.append(issue("quantity_not_positive", "已知完成数量是 0，算不出单件工时。"))
    if not records_complete or data_quality != "complete":
        reasons.append(issue("execution_data_incomplete", "报工记录有缺口或前后冲突，请核对现场记录。"))
    if confirmed_finish is None:
        reasons.append(issue("completion_time_unknown", "完工时间暂无数据，排不进最近 20 条完工记录。"))
    elif datetime.fromisoformat(confirmed_finish) > as_of:
        reasons.append(issue("outside_as_of", "完工时间晚于这次读取的时间。"))
    return reasons


def _evaluate_metrics(
    *,
    has_reports: bool,
    total_hours: Optional[Decimal],
    all_quantities_known: bool,
    known_completed_quantity: int,
    unknown_record_count: int,
    target_quantity: Optional[int],
    quantity_complete: bool,
    records_complete: bool,
    data_quality: str,
    execution_state: str,
    completion_basis: Optional[str],
    confirmed_finish: Optional[str],
    operation_source: Optional[str],
    lineage: Optional[CalibrationLineage],
    problems: list,
    template,
    as_of: datetime,
):
    values, reasons, exact_ratio = _processing_metrics(
        has_reports=has_reports,
        total_hours=total_hours,
        all_quantities_known=all_quantities_known,
        known_completed_quantity=known_completed_quantity,
        unknown_record_count=unknown_record_count,
    )
    reasons.extend(_lineage_reasons(lineage, template))
    if has_reports:
        reasons.extend(
            _execution_reasons(
                operation_source=operation_source,
                completion_basis=completion_basis,
                execution_state=execution_state,
                quantity_complete=quantity_complete,
                unknown_record_count=unknown_record_count,
                target_quantity=target_quantity,
                known_completed_quantity=known_completed_quantity,
                records_complete=records_complete,
                data_quality=data_quality,
                confirmed_finish=confirmed_finish,
                as_of=as_of,
            )
        )
    reasons.extend(problems)
    eligible = not reasons
    return values, reasons, eligible, (exact_ratio if eligible else None)


def sample_revision_state(
    *,
    operation_ref: str,
    report_revision_refs: list,
    data_gaps: list,
    quantity: int,
    finish: Optional[str],
    lineage: Optional[CalibrationLineage],
    lineage_origin: Optional[Mapping[str, Any]],
    operation_source: Optional[str],
) -> Dict[str, Any]:
    lineage_state = vars(lineage) if lineage is not None else None
    if lineage_state is not None and lineage_origin is not None:
        lineage_state = {
            **lineage_state,
            "source_eligible": bool(lineage_origin["source_eligible"]),
            "instance_modified": bool(lineage_origin["instance_modified"]),
        }
    return {
        "source_ref": operation_ref,
        "report_revision_refs": report_revision_refs,
        "data_gaps": data_gaps,
        "quantity": quantity,
        "finish": finish,
        "lineage": lineage_state,
        "operation_source": operation_source,
    }


def template_snapshot_text(operation_ref: str, revision: int) -> str:
    return content_text({"source_ref": operation_ref, "revision": revision})


def ensure_sample_revision(sample):
    revision = sample["sample_revision"]
    if type(revision) is not str:
        sample["sample_revision"] = content_text(revision)
    return sample


def ensure_sample_reports(sample, *, report_histories):
    reports = sample["reports"]
    if reports and type(reports[0]) is not dict:
        from core.services.execution import projection as execution_projection

        histories = report_histories[sample["execution_operation_ref"]]
        materialized = []
        for report in reports:
            item = report.to_dict()
            item["correction_history"] = execution_projection.build_correction_history(
                histories[report.report_ref],
                operation_ref=report.operation_ref,
                report_ref=report.report_ref,
            )
            item.pop("write_context")
            materialized.append(item)
        sample["reports"] = materialized
    return sample


def _state_execution_status(row, *, complete_reports: bool):
    if complete_reports:
        return "complete", row["max_actual_end"], "complete_reports"
    if row["known_completed_quantity"] > 0 or row["any_actual_end"]:
        return "partial", None, None
    state = "started" if row["active_report_count"] > 0 else "unreported"
    return state, None, None


def _state_data_quality(row, *, target, target_gaps: list, records_complete: bool) -> str:
    active_count = row["active_report_count"]
    has_exceeded = target is not None and row["known_completed_quantity"] > target
    if has_exceeded or not row["identity_active"] or row["id"] is None or row["source"] not in OPERATION_SOURCES:
        return "invalid"
    if target_gaps or active_count == 0 or not records_complete:
        return "incomplete"
    return "complete"


def _state_lineage(row):
    if row["lineage_ref"] is None:
        return None, []
    lineage = CalibrationLineage(row["template_operation_ref"], row["template_revision"], row["lineage_ref"])
    problems = lineage_problems(
        source_eligible=bool(row["source_eligible"]),
        operation_active=bool(row["identity_active"]),
        instance_modified=bool(row["instance_modified"]),
    )
    return lineage, problems


def review_state_sample(row, *, template, as_of: datetime) -> Tuple[Dict[str, Any], Optional[Fraction]]:
    """Evaluate one candidate instance from OperationExecutionStates without loading report rows."""
    ref = row["operation_ref"]
    source = row["source"]
    active_count = row["active_report_count"]
    known_qty = row["known_completed_quantity"]
    unknown_qty = row["unknown_quantity_count"]
    target, _, target_gaps = operation_target(row)
    records_complete = bool(
        row["external_complete_flag"] if source == "external" else row["internal_complete_flag"]
    )
    quantity_complete = target is not None and known_qty == target and unknown_qty == 0
    execution_state, confirmed_finish, completion_basis = _state_execution_status(
        row, complete_reports=quantity_complete and records_complete
    )
    data_quality = _state_data_quality(
        row, target=target, target_gaps=target_gaps, records_complete=records_complete
    )
    known_text = row["known_effective_hours_text"]
    total_hours = HourTotals(
        None if known_text is None else stored_exact_hours(known_text), row["unknown_hour_count"]
    ).total
    lineage, problems = _state_lineage(row)
    values, reasons, eligible, exact_ratio = _evaluate_metrics(
        has_reports=active_count > 0,
        total_hours=total_hours,
        all_quantities_known=unknown_qty == 0,
        known_completed_quantity=known_qty,
        unknown_record_count=unknown_qty,
        target_quantity=target,
        quantity_complete=quantity_complete,
        records_complete=records_complete,
        data_quality=data_quality,
        execution_state=execution_state,
        completion_basis=completion_basis,
        confirmed_finish=confirmed_finish,
        operation_source=source,
        lineage=lineage,
        problems=problems,
        template=template,
        as_of=as_of,
    )
    sample = {
        "sample_ref": ref,
        "execution_operation_ref": ref,
        "batch_code": row["batch_id"],
        "operation_code": row["op_code"],
        "operation_source": source,
        "template_operation_ref": lineage.template_operation_ref if lineage else None,
        "template_revision": lineage.template_revision if lineage else None,
        "lineage_evidence_ref": lineage.evidence_ref if lineage else None,
        "lineage_obj": lineage,
        "lineage_origin": row if lineage is not None else None,
        "confirmed_finish": confirmed_finish,
        **values,
        "eligible": eligible,
        "selected": False,
        "exclusion_reasons": reasons,
    }
    return sample, exact_ratio


def populate_selected_revisions(rows, samples_by_ref, report_map, *, snapshot):
    """Populate template_snapshot and sample_revisions for exported suggestion rows."""
    hydrated = []
    for row in rows:
        revisions = []
        for sample_ref in row["sample_refs"]:
            sample = samples_by_ref[sample_ref]
            pairs = report_map[sample_ref]
            revision_refs = [rev_ref for _, rev_ref in pairs]
            state = sample_revision_state(
                operation_ref=sample_ref,
                report_revision_refs=revision_refs,
                data_gaps=[],
                quantity=sample["completed_quantity"],
                finish=sample["confirmed_finish"],
                lineage=sample["lineage_obj"],
                lineage_origin=sample["lineage_origin"],
                operation_source=sample["operation_source"],
            )
            revisions.append(
                {
                    "sample_ref": sample_ref,
                    "sample_revision": content_text(state),
                    "template_revision": sample["template_revision"],
                    "report_revision_refs": revision_refs,
                }
            )
        hydrated.append(
            {
                **row,
                "template_snapshot": template_snapshot_text(
                    row["template_operation_ref"], row["template_revision"]
                ),
                "sample_revisions": revisions,
                **snapshot,
            }
        )
    return hydrated


def review_sample(candidate, *, template, as_of: datetime, lineage_origin, problems) -> Tuple[Dict[str, Any], Optional[Fraction]]:
    projection = candidate.execution
    lineage = candidate.lineage
    has_reports = bool(projection.reports)
    total_hours = sum_hours(report.effective_processing_hours for report in projection.reports).total
    all_quantities_known = has_reports and all(
        report.completed_quantity is not None for report in projection.reports
    )
    values, reasons, eligible, exact_ratio = _evaluate_metrics(
        has_reports=has_reports,
        total_hours=total_hours,
        all_quantities_known=all_quantities_known,
        known_completed_quantity=projection.known_completed_quantity,
        unknown_record_count=projection.unknown_record_count,
        target_quantity=projection.target_quantity,
        quantity_complete=projection.quantity_complete,
        records_complete=projection.records_complete,
        data_quality=projection.data_quality,
        execution_state=projection.execution_state,
        completion_basis=projection.completion_basis,
        confirmed_finish=projection.confirmed_finish,
        operation_source=candidate.operation_source,
        lineage=lineage,
        problems=problems,
        template=template,
        as_of=as_of,
    )
    revision_refs = [row.revision_ref for row in projection.reports]
    state = sample_revision_state(
        operation_ref=projection.operation_ref,
        report_revision_refs=revision_refs,
        data_gaps=projection.data_gaps,
        quantity=projection.known_completed_quantity,
        finish=projection.confirmed_finish,
        lineage=lineage,
        lineage_origin=lineage_origin,
        operation_source=candidate.operation_source,
    )
    sample = {
        "sample_ref": projection.operation_ref,
        "execution_operation_ref": projection.operation_ref,
        "batch_code": candidate.batch_code,
        "operation_code": candidate.operation_code,
        "template_operation_ref": lineage.template_operation_ref if lineage else None,
        "template_revision": lineage.template_revision if lineage else None,
        "lineage_evidence_ref": lineage.evidence_ref if lineage else None,
        "sample_revision": state,
        "report_refs": [row.report_ref for row in projection.reports],
        "report_revision_refs": revision_refs,
        "confirmed_finish": projection.confirmed_finish,
        "reports": projection.reports,
        "data_gaps": projection.data_gaps,
        **values,
        "eligible": eligible,
        "selected": False,
        "exclusion_reasons": reasons,
    }
    return sample, exact_ratio
