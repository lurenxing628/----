"""D05 eligibility over the one execution projection, including exclusion evidence."""

import math
from datetime import datetime
from decimal import Decimal

from core.models.workbench_calibration import issue
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint


def number(value):
    if value is None:
        return None
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise WorkbenchCommandRejected("storage_failure", "校准读到的数量或工时不是有效数字，系统不会把坏数据当成 0 或未知。请核对报工记录。", 500)
    return Decimal(str(value))


def _lineage_reasons(lineage, template):
    if lineage is None:
        return [issue("template_lineage_missing", "这条报工记录没有记下它是按哪道模板工序、哪个版本建的；同零件或同工序号不算对得上。")]
    if not lineage.evidence_ref or type(lineage.template_revision) is not int or lineage.template_revision < 1:
        return [issue("template_lineage_unconfirmed", "模板来源或版本还没确认。")]
    if template is None or lineage.template_operation_ref != template.operation_ref:
        return [issue("template_operation_mismatch", "来源模板的编号和当前模板不是同一条，系统不会按名称或工序号替代。")]
    if lineage.template_revision != template.revision:
        return [issue("template_revision_mismatch", "来源模板的版本和当前版本不同，不能混用。")]
    if template.source != "internal":
        return [issue("processing_basis_unconfirmed", "来源模板不是已确认的自制加工工序。")]
    return []


def _execution_reasons(candidate, as_of):
    projection = candidate.execution
    reasons = []
    if candidate.operation_source != "internal" or projection.completion_basis != "complete_reports":
        reasons.append(issue("processing_basis_unconfirmed", "这道工序不能确认是按自制逐次报工算的，系统不会用事件时长或外协周期倒推加工小时。"))
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
    return reasons + _legacy_reasons(projection)


def _legacy_reasons(projection):
    if any(row["code"] == "legacy_source_changed" for row in projection.data_gaps):
        raise WorkbenchCommandRejected("calibration_source_changed", "历史报工数据和归档不一致。请先核对来源再刷新，系统不会沿用上一次的校准结果。")
    reasons = []
    for kind, code, message in (("pause", "pause_contamination", "这条记录中间有暂停，已知会影响工时，没有算进完工记录。"),
                                ("exception", "known_exception", "这条记录报过异常，没有算进完工记录。")):
        refs = [row["legacy_fact_ref"] for row in projection.legacy_facts if row["event_type"] == kind]
        if refs:
            reasons.append({**issue(code, message), "legacy_fact_refs": refs})
    return reasons


def _known_sum(values):
    if not values:
        return None
    total = Decimal(0)
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
    if total is None:
        reasons.append(issue("processing_hours_unknown", "有报工没填有效加工小时，系统不会把没填的当成 0。"))
    if reported_quantity is None:
        reasons.append(issue("quantity_unknown", "至少有一次报工的数量暂无数据。"))
    elif reported_quantity != quantity:
        reasons.append(issue("processing_basis_unconfirmed", "逐次报工数量和累计完工数量对不上，系统不会把历史累计完工的工时重复算一遍。"))
    ratio = total / quantity if total is not None and quantity else None
    return {"completed_quantity": projection.known_completed_quantity, "unknown_record_count": projection.unknown_record_count,
            "effective_processing_hours": float(total) if total is not None else None,
            "unit_hours": float(ratio) if ratio is not None else None}, reasons


def _sample_origin(candidate):
    projection, lineage = candidate.execution, candidate.lineage
    reports = [report.to_dict() for report in projection.reports]
    for report in reports:
        report.pop("write_context")
    state = {"reports": reports, "legacy_facts": projection.legacy_facts, "data_gaps": projection.data_gaps,
             "quantity": projection.known_completed_quantity, "finish": projection.confirmed_finish,
             "lineage": vars(lineage) if lineage else None, "operation_source": candidate.operation_source}
    return {"sample_ref": projection.operation_ref, "execution_operation_ref": projection.operation_ref,
            "batch_code": candidate.batch_code, "operation_code": candidate.operation_code,
            "template_operation_ref": lineage.template_operation_ref if lineage else None,
            "template_revision": lineage.template_revision if lineage else None,
            "lineage_evidence_ref": lineage.evidence_ref if lineage else None,
            "sample_revision": input_fingerprint(state), "report_refs": [row.report_ref for row in projection.reports],
            "report_revision_refs": [row.revision_ref for row in projection.reports],
            "confirmed_finish": projection.confirmed_finish,
            "reports": reports, "legacy_facts": projection.legacy_facts, "data_gaps": projection.data_gaps}


def review_sample(candidate, *, template, as_of):
    values, reasons = _processing_values(candidate.execution)
    reasons += _lineage_reasons(candidate.lineage, template) + _execution_reasons(candidate, as_of)
    return {**_sample_origin(candidate), **values, "eligible": not reasons, "selected": False, "exclusion_reasons": reasons}
