"""Reject broken stored report chains before asking the shared ledger to project."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import REPORT_FIELDS, factory_time, public_ref, validate_actual_values

from .samples import number


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


def validate_report_histories(facts, as_of):
    try:
        for reports in facts["reports"].values():
            for history in reports.values():
                for row in history:
                    if factory_time(row["revision_at"]) > as_of or factory_time(row["recorded_at"]) > as_of:
                        raise ValueError("Stored report is newer than the captured read time")
                    _values(row["values"], as_of)
    except (ValueError, TypeError, KeyError, OverflowError, WorkbenchCommandRejected) as exc:
        raise WorkbenchCommandRejected("storage_failure", "报工来源或更正记录损坏，没有生成校准建议。请核对报工数据；仍不行请联系维护人员。", 500) from exc
