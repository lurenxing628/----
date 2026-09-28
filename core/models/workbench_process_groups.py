"""Explicit edits to outsourcing stages; omitted historical stages stay intact."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_commands import (
    process_list,
    process_number,
    process_object,
    process_ref,
    process_unique,
)


def normalize_group_input(payload):
    process_object(payload, {"groups", "discard_group_refs"})
    discarded = process_unique(process_list(payload["discard_group_refs"]), refs_only=True)
    groups, existing, members = [], set(), set()
    for row in process_list(payload["groups"]):
        process_object(row, {"ref", "operation_refs", "supplier_ref", "total_days"})
        ref = None if row["ref"] is None else process_ref(row["ref"])
        refs = process_unique(process_list(row["operation_refs"]), refs_only=True)
        if not refs or members.intersection(refs) or ref is not None and (ref in existing or ref in discarded):
            raise WorkbenchCommandRejected("invalid_input", "外协段必须包含工序，工序不能属于两段；同一段不能同时修改和解除。", 422)
        members.update(refs)
        if ref is not None:
            existing.add(ref)
        groups.append({"ref": ref, "operation_refs": refs, "supplier_ref": process_ref(row["supplier_ref"]),
                       "total_days": process_number(row["total_days"], positive=True)})
    if len(members) > 10000:
        raise WorkbenchCommandRejected("stage_too_large", "一次最多维护 10000 道工序，请缩小范围后重试。", 413)
    return {"groups": sorted(groups, key=lambda row: (row["ref"] or "", row["operation_refs"])),
            "discard_group_refs": discarded}
