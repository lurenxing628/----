"""Known and unknown quantities and record completeness."""

from dataclasses import dataclass, field

from core.models.workbench_execution_input import REQUIRED_FIELDS

from .quality import gap


@dataclass
class ReportTotals:
    known: int = 0
    unknown: int = 0
    records_complete: bool = False
    starts: list = field(default_factory=list)
    gaps: list = field(default_factory=list)


def report_totals(reports, source):
    totals = ReportTotals(records_complete=bool(reports))
    required = REQUIRED_FIELDS[:4] if source == "external" else REQUIRED_FIELDS
    for report in reports:
        if report.completed_quantity is None:
            totals.unknown += 1
        else:
            totals.known += report.completed_quantity
        missing = [key for key in required if getattr(report, key) is None]
        if missing:
            totals.records_complete = False
            totals.gaps.append(gap("report_fields_missing", "这条逐次报工还有必填项没填，系统按记录不完整处理，请补齐。", report_ref=report.report_ref, fields=missing))
        if report.actual_start:
            totals.starts.append(report.actual_start)
    return totals


def quantity_consistency(totals, target):
    gaps = []
    if target is not None and totals.known > target:
        gaps.append(gap("quantity_exceeded", "已报的累计完工数量超过了这道工序的目标数量，旧完工记录仍然保留，请核对数量。"))
    return gaps
