"""Known and unknown quantities, record completeness and provenance deduplication."""

from dataclasses import dataclass, field

from core.models.workbench_execution_input import REQUIRED_FIELDS

from .quality import gap


@dataclass
class ReportTotals:
    report_count: int = 0
    known: int = 0
    unknown: int = 0
    records_complete: bool = False
    legacy_uncovered: bool = False
    starts: list = field(default_factory=list)
    linked: dict = field(default_factory=dict)
    gaps: list = field(default_factory=list)


def report_totals(reports, source):
    totals = ReportTotals(report_count=len(reports), records_complete=bool(reports))
    required = REQUIRED_FIELDS[:4] if source == "external" else REQUIRED_FIELDS
    for report in reports:
        if report.legacy_fact_ref:
            totals.linked[report.legacy_fact_ref] = report
        elif report.completed_quantity is None:
            totals.unknown += 1
        else:
            totals.known += report.completed_quantity
        missing = [key for key in required if getattr(report, key) is None]
        if missing:
            totals.records_complete = False
            totals.gaps.append(gap("report_fields_missing", "逐次报工尚有必要字段未填写。", report_ref=report.report_ref, fields=missing))
        if report.actual_start:
            totals.starts.append(report.actual_start)
    return totals


def _finish_quantities(totals, finishes):
    quantities = []
    for row in finishes:
        supplement = totals.linked.get(row["legacy_fact_ref"])
        quantity = supplement.completed_quantity if supplement else row["quantity_done"]
        if quantity is None:
            totals.unknown += 1
        else:
            quantities.append(quantity)
        if supplement and row["quantity_done"] is not None and row["quantity_done"] != quantity:
            totals.gaps.append(gap("legacy_quantity_conflict", "补充数量与原完工证据矛盾，原完成事实仍保留。"))
    return quantities


def merge_legacy_totals(totals, evidence):
    quantities = _finish_quantities(totals, evidence.finishes)
    if evidence.records and not evidence.finishes and not totals.report_count:
        totals.unknown += 1
    if quantities:
        # A legacy finish confirms a cumulative quantity, not an additional lot.
        totals.known += max(quantities)
        if len(set(quantities)) > 1:
            totals.gaps.append(gap("legacy_quantity_conflict", "同工序跨版本的旧累计确认数量不一致，未重复相加。"))
    totals.legacy_uncovered = bool(evidence.records) and (not evidence.finishes or any(
        row["legacy_fact_ref"] not in totals.linked for row in evidence.finishes))
    if totals.legacy_uncovered:
        if evidence.finishes:
            totals.records_complete = False
        totals.gaps.append(gap("legacy_fields_unknown", "旧事实未证明逐次加工小时及完整数量，未补成零或伪造报工。"))
    totals.starts.extend(evidence.starts)


def quantity_consistency(totals, target, finishes):
    gaps = []
    if target is not None and totals.known > target:
        gaps.append(gap("quantity_exceeded", "已知累计数量超过工序目标，需核对；旧完成证据不撤销。"))
    if finishes and target is not None and totals.unknown == 0 and totals.known != target:
        gaps.append(gap("legacy_target_conflict", "旧完工证据与已知目标数量不一致，完成事实仍保留并待复核。"))
    return gaps
