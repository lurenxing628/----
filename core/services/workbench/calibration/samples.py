"""D05 eligibility over the one execution projection, including exclusion evidence."""

from datetime import datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any, Dict, Optional, Tuple, overload

from core.models.content import content_text
from core.models.workbench_calibration import issue
from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_parse import is_exact_non_negative_number

# 除法结果（单件工时、建议定额、偏差百分比）统一整形到 3 位小数，四舍五入；
# 求和与比率在无限精度 Fraction 域精确计算，避免默认 28 位 Decimal 上下文截断。
_FLOAT_INF_THRESHOLD = (1 << 1024) - (1 << 970)


def number(value) -> Optional[Fraction]:
    if value is None:
        return None
    if not is_exact_non_negative_number(value):
        raise WorkbenchCommandRejected("storage_failure", "报工数量或工时无效，请核对报工记录。", 500)
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
    if not lineage.evidence_ref or type(lineage.template_revision) is not int or lineage.template_revision < 1:
        return [issue("template_lineage_unconfirmed", "模板来源或版本还没确认。")]
    if template is None or lineage.template_operation_ref != template.operation_ref:
        return [issue("template_operation_mismatch", "来源模板与当前模板不一致。")]
    if lineage.template_revision != template.revision:
        return [issue("template_revision_mismatch", "来源模板的版本和当前版本不同，不能混用。")]
    if template.source != "internal":
        return [issue("processing_basis_unconfirmed", "来源模板不是已确认的自制加工工序。")]
    return []


def _execution_reasons(candidate, as_of):
    projection = candidate.execution
    if not projection.reports:
        return []
    reasons = []
    if candidate.operation_source != "internal" or projection.completion_basis != "complete_reports":
        reasons.append(issue("processing_basis_unconfirmed", "尚未确认该工序按自制逐次报工核算加工工时。"))
    if projection.execution_state != "complete" or not projection.quantity_complete:
        reasons.append(issue("operation_not_complete", "累计报工数量还证明不了这道工序已经全部完工。"))
    if projection.unknown_record_count or projection.target_quantity is None:
        reasons.append(issue("quantity_unknown", "完成数量或目标数量暂无数据。"))
    if number(projection.known_completed_quantity) == 0:
        reasons.append(issue("quantity_not_positive", "已知完成数量是 0，算不出单件工时。"))
    if not projection.records_complete or projection.data_quality != "complete":
        reasons.append(issue("execution_data_incomplete", "报工记录有缺口或前后冲突，请核对现场记录。"))
    if projection.confirmed_finish is None:
        reasons.append(issue("completion_time_unknown", "完工时间暂无数据，排不进最近 20 条完工记录。"))
    elif datetime.fromisoformat(projection.confirmed_finish) > as_of:
        reasons.append(issue("outside_as_of", "完工时间晚于这次读取的时间。"))
    return reasons


def _known_sum(values) -> Optional[Fraction]:
    if not values:
        return None
    total = Fraction(0)
    known = True
    for value in values:
        parsed = number(value)
        if parsed is None:
            known = False
        else:
            total += parsed
    return total if known else None


def _processing_values(projection):
    total = _known_sum([report.effective_processing_hours for report in projection.reports])
    reported_quantity = _known_sum([report.completed_quantity for report in projection.reports])
    quantity = number(projection.known_completed_quantity)
    reasons = []
    if not projection.reports:
        reasons.append(issue("production_reports_missing", "尚无逐次报工记录，暂不能计算单件工时。"))
    elif total is None:
        reasons.append(issue("processing_hours_unknown", "部分报工未填写有效加工工时。"))
    if projection.reports and reported_quantity is None:
        reasons.append(issue("quantity_unknown", "至少有一次报工的数量暂无数据。"))
    elif reported_quantity is not None and reported_quantity != quantity:
        reasons.append(issue("processing_basis_unconfirmed", "逐次报工数量与累计完工数量不一致。"))
    exact_ratio = total / quantity if total is not None and quantity else None
    ratio = quantize(exact_ratio)
    effective_hours = (float(total) if total < _FLOAT_INF_THRESHOLD else float("inf")) if total is not None else None
    return {"completed_quantity": projection.known_completed_quantity, "unknown_record_count": projection.unknown_record_count,
            "effective_processing_hours": effective_hours,
            "unit_hours": float(ratio) if ratio is not None else None}, reasons, exact_ratio


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


def _sample_origin(candidate, *, lineage_origin, lineage_events):
    projection, lineage = candidate.execution, candidate.lineage
    revision_refs = [row.revision_ref for row in projection.reports]
    state = {"source_ref": projection.operation_ref,
             "report_revision_refs": revision_refs,
             "data_gaps": projection.data_gaps,
             "quantity": projection.known_completed_quantity, "finish": projection.confirmed_finish,
             "lineage": vars(lineage) if lineage else None, "operation_source": candidate.operation_source}
    if lineage_origin is not None:
        state["lineage"] = {**state["lineage"], "birth_event_id": lineage_origin["birth_event_id"],
                            "event_ids": [event["event_id"] for event in lineage_events]}
    return {"sample_ref": projection.operation_ref, "execution_operation_ref": projection.operation_ref,
            "batch_code": candidate.batch_code, "operation_code": candidate.operation_code,
            "template_operation_ref": lineage.template_operation_ref if lineage else None,
            "template_revision": lineage.template_revision if lineage else None,
            "lineage_evidence_ref": lineage.evidence_ref if lineage else None,
            "sample_revision": state, "report_refs": [row.report_ref for row in projection.reports],
            "report_revision_refs": revision_refs,
            "confirmed_finish": projection.confirmed_finish,
            "reports": projection.reports, "data_gaps": projection.data_gaps}


def review_sample(candidate, *, template, as_of, lineage_origin, lineage_events) -> Tuple[Dict[str, Any], Optional[Fraction]]:
    values, reasons, exact_ratio = _processing_values(candidate.execution)
    reasons += _lineage_reasons(candidate.lineage, template) + _execution_reasons(candidate, as_of)
    eligible = not reasons
    sample = {**_sample_origin(candidate, lineage_origin=lineage_origin, lineage_events=lineage_events),
              **values, "eligible": eligible, "selected": False, "exclusion_reasons": reasons}
    return sample, (exact_ratio if eligible else None)
