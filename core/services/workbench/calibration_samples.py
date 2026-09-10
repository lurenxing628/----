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
        raise WorkbenchCommandRejected("storage_failure", "校准读取到非法数量或工时，未把损坏数据当作未知或零。", 500)
    return Decimal(str(value))


def _lineage_reasons(lineage, template):
    if lineage is None:
        return [issue("template_lineage_missing", "执行实例没有保存来源模板工序及创建时修订；同零件或同序号不构成样本关联。")]
    if not lineage.evidence_ref or type(lineage.template_revision) is not int or lineage.template_revision < 1:
        return [issue("template_lineage_unconfirmed", "模板来源证据或修订未确认。")]
    if template is None or lineage.template_operation_ref != template.operation_ref:
        return [issue("template_operation_mismatch", "来源模板永久引用不同，不能按名称或序号替代。")]
    if lineage.template_revision != template.revision:
        return [issue("template_revision_mismatch", "来源模板修订与当前修订不同，不能混用。")]
    if template.source != "internal":
        return [issue("processing_basis_unconfirmed", "来源模板不是已确认的自制加工工序。")]
    return []


def _execution_reasons(candidate, as_of):
    projection = candidate.execution
    reasons = []
    if candidate.operation_source != "internal" or projection.completion_basis != "complete_reports":
        reasons.append(issue("processing_basis_unconfirmed", "未证明完整的自制逐次加工口径，不能用事件跨度或外协周期推算加工小时。"))
    if projection.execution_state != "complete" or not projection.quantity_complete:
        reasons.append(issue("operation_not_complete", "工序尚未由完整累计量证明整道完工。"))
    if projection.unknown_record_count or projection.target_quantity is None:
        reasons.append(issue("quantity_unknown", "完成数量或目标数量未知。"))
    if number(projection.known_completed_quantity) == 0:
        reasons.append(issue("quantity_not_positive", "已知完成数量为0，不能除算单件工时。"))
    if not projection.records_complete or projection.data_quality != "complete":
        reasons.append(issue("execution_data_incomplete", "执行投影有缺口或冲突，请核对原始记录。"))
    if projection.confirmed_finish is None:
        reasons.append(issue("completion_time_unknown", "完整完工时间未知，不能排序近20个样本。"))
    elif datetime.fromisoformat(projection.confirmed_finish) > as_of:
        reasons.append(issue("outside_as_of", "完工时间晚于当前读取时点。"))
    return reasons + _legacy_reasons(projection)


def _legacy_reasons(projection):
    if any(row["code"] == "legacy_source_changed" for row in projection.data_gaps):
        raise WorkbenchCommandRejected("calibration_source_changed", "旧执行原表与保留归档不同，请核实来源后刷新；未静默沿用校准结果。")
    reasons = []
    for kind, code, message in (("pause", "pause_contamination", "已知暂停污染，未纳入样本。"),
                                ("exception", "known_exception", "已知异常记录，未纳入样本。")):
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
        reasons.append(issue("processing_hours_unknown", "逐次有效加工小时未完整填写，未把未知补成零。"))
    if reported_quantity is None:
        reasons.append(issue("quantity_unknown", "至少一次报工数量未知。"))
    elif reported_quantity != quantity:
        reasons.append(issue("processing_basis_unconfirmed", "逐次量与投影累计量不一致，不能重复计算旧累计完工的工时。"))
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
