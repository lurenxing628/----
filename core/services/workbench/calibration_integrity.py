"""Reject broken stored report chains before asking the shared ledger to project."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import REPORT_FIELDS, factory_time, public_ref, validate_actual_values

from .calibration_samples import number


def _values(values, as_of):
    if type(values) is not dict or set(values) != set(REPORT_FIELDS):
        raise ValueError("Stored report fields differ from the report contract")
    quantity = values["completed_quantity"]
    if quantity is not None and (type(quantity) is not int or not 0 <= quantity <= (1 << 53) - 1):
        raise ValueError("Invalid stored quantity")
    number(values["effective_processing_hours"])
    for key in ("actual_machine_ref", "actual_operator_ref"):
        if values[key] is not None:
            public_ref(values[key])
    remark = values["remark"]
    if type(remark) is not str or "\x00" in remark or len(remark) > 2000:
        raise ValueError("Invalid stored remark")
    validate_actual_values(values, as_of)


def validate_report_histories(facts, heads, as_of):
    seen = set()
    try:
        for operation_ref, reports in facts["reports"].items():
            for report_ref, history in reports.items():
                seen.add(report_ref)
                previous = None
                for sequence, row in enumerate(history, 1):
                    if (row["sequence"] != sequence or row["previous_revision_ref"] != previous
                            or row["operation_ref"] != operation_ref or row["report_ref"] != report_ref
                            or row["action"] not in (("create",) if sequence == 1 else ("supplement", "correct"))):
                        raise ValueError("Stored report revision chain is broken")
                    public_ref(row["revision_ref"])
                    if factory_time(row["revision_at"]) > as_of or factory_time(row["recorded_at"]) > as_of:
                        raise ValueError("Stored report is newer than the captured read time")
                    _values(row["values"], as_of)
                    previous = row["revision_ref"]
        if seen != heads:
            raise ValueError("Stored production report has no revision history")
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise WorkbenchCommandRejected("storage_failure", "报工来源或修订链损坏，未生成校准建议，请核对数据。", 500) from exc
