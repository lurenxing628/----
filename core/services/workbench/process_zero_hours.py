"""Zero unit hours require acknowledgement only for unconfirmed content."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.workflow_state import operation_confirmations


def zero_confirmation_required(before, after, confirmation):
    if after.get("source", before.get("source")) != "internal" or after.get("unit_hours") != 0:
        return False
    return confirmation.get("hours", {}).get("state") != "confirmed" or any(
        before.get(key) != after.get(key, before.get(key)) for key in ("setup_hours", "unit_hours"))


def require_zero_confirmation(conn, proposals, acknowledged):
    if acknowledged:
        return
    states, pending = {}, []
    for before, after in proposals:
        if after.get("unit_hours") != 0:
            continue
        part_no = before["part_no"]
        if part_no not in states:
            states[part_no] = operation_confirmations(conn, part_no)
        if zero_confirmation_required(before, after, states[part_no].get(before["ref"], {})):
            pending.append(before)
    if pending:
        operations = "、".join(str(row["seq"]) for row in pending)
        raise WorkbenchCommandRejected(
            "zero_unit_hours_confirmation_required",
            "工序 " + operations + " 的单件工时为 0，排产只计算换型工时，数量增加不会增加加工时长。请按 0 保存。", 422,
            operation_refs=[row["ref"] for row in pending])
