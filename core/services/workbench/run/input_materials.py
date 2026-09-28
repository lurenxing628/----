"""Bind release dates to this run's DTOs, never alter production batch facts."""

from core.models.workbench_run_compute import CandidateRunInputError
from core.services.material.stage_availability import MaterialAvailability
from core.services.scheduler.contracts.external_context import context_group_key


def bind_material_releases(operations, tables, batches, settings):
    if not settings["ready_check"]:
        return
    availability = MaterialAvailability(tables)
    raw = {row["id"]: row for row in tables["BatchOperations"]}
    groups = {}
    for op in operations:
        batch = batches[op.batch_id]
        day = availability.operation_release({"batch_id": batch.batch_id, "quantity": batch.quantity}, raw[op.id], settings.get("material_strategy", "strict"))
        if day is None:
            raise CandidateRunInputError("material_not_ready", "物料条件发生变化，请重新检查后排产。")
        op.material_ready_date = day if day != "1900-01-01" else None
        context = availability.contexts.get(op.id)
        if context and context["merge_mode"] == "merged":
            groups.setdefault((op.batch_id, op.piece_id, context_group_key(context)), []).append(op)
    # A merged outsourcing segment leaves as one block, with every member's material.
    for members in groups.values():
        day = max((op.material_ready_date or "1900-01-01") for op in members)
        for op in members:
            op.material_ready_date = day if day != "1900-01-01" else None
