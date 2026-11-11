"""Known and unknown quantities and record completeness."""

from dataclasses import dataclass, field

from core.models.workbench_execution_input import required_report_fields

from .quality import gap


@dataclass
class ReportTotals:
    known: int = 0
    unknown: int = 0
    records_complete: bool = False
    starts: list = field(default_factory=list)
    gaps: list = field(default_factory=list)


def _missing_fields(report, source):
    values = {
        "actual_start": report.actual_start,
        "actual_end": report.actual_end,
        "completed_quantity": report.completed_quantity,
        "effective_processing_hours": report.effective_processing_hours,
        "actual_machine_ref": report.actual_machine_ref,
        "actual_operator_ref": report.actual_operator_ref,
    }
    return [key for key in required_report_fields(source) if values[key] is None]


def report_totals(reports, source):
    totals = ReportTotals(records_complete=bool(reports))
    for report in reports:
        if report.completed_quantity is None:
            totals.unknown += 1
        else:
            totals.known += report.completed_quantity
        missing = _missing_fields(report, source)
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
