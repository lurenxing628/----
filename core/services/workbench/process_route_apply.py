"""Preserving route differences and explicit external-group invalidation."""

from __future__ import annotations

from bisect import bisect_left

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.process_route_preview import ProcessRoutePreviewService
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.part_operation_repo import PartOperationRepository
from data.repositories.part_repo import PartRepository


def prepare_route(conn, logger, payload, operations):
    preview = ProcessRoutePreviewService(conn, logger).preview(payload["route"])
    if not preview["can_confirm_route"]:
        raise WorkbenchCommandRejected("route_invalid", "路线预检未通过，请核对完整诊断后重新确认。", 422)
    existing = {row["seq"]: row for row in operations}
    incoming = {row["sequence"]: row for row in preview["operations"]}
    changed = {seq for seq, row in existing.items() if row["status"] == "active" and
               (seq not in incoming or row["op_type_name"] != incoming[seq]["op_type_name"])}
    changed.update(seq for seq in incoming if seq not in existing or existing[seq]["status"] != "active")
    return preview, changed


def affected_group_rows(groups, operations, changed_sequences):
    linked = {row["ext_group_id"] for row in operations if row["seq"] in changed_sequences and row["ext_group_id"] is not None}
    sequences = sorted(changed_sequences)
    affected = []
    for group in groups:
        index = bisect_left(sequences, group["start_seq"])
        if group["group_id"] in linked or (index < len(sequences) and sequences[index] <= group["end_seq"]):
            affected.append(group)
    return affected


def require_group_ack(payload, affected):
    if set(payload["discard_group_refs"]) != {row["ref"] for row in affected}:
        raise WorkbenchCommandRejected("group_discard_required", "受影响的外协组已经变了。请重新核对并勾选全部受影响的组，不要多选或漏选。")


def discard_groups(conn, part_no, affected):
    op_repo = PartOperationRepository(conn)
    group_repo = ExternalGroupRepository(conn)
    for group in affected:
        op_repo.clear_external_group(part_no, group["group_id"])
        group_repo.delete_for_part(part_no, group["group_id"])


def _suggested_key(identities, ref, kind):
    if ref is None:
        return None
    identity = identities.get(ref)
    if identity is None or not identity.active or identity.kind != kind:
        raise WorkbenchCommandRejected("storage_failure", "预检给出的记录已失效。请刷新后重新预检。", 500)
    return identity.entity_key


def apply_route(conn, part, operations, preview, identities):
    op_repo = PartOperationRepository(conn)
    existing = {row["seq"]: row for row in operations}
    incoming = {row["sequence"] for row in preview["operations"]}
    changed = False
    for row in operations:
        if row["status"] == "active" and row["seq"] not in incoming:
            op_repo.mark_deleted_by_id(row["id"])
            changed = True
    for row in preview["operations"]:
        old = existing.get(row["sequence"])
        if old is not None:
            # A renamed/restored sequence retains all previous choices and hidden facts.
            if old["op_type_name"] != row["op_type_name"] or old["status"] != "active":
                op_repo.restore_with_op_type_name(old["id"], row["op_type_name"])
                changed = True
            continue
        op_repo.insert_route_operation(
            part_no=part["part_no"],
            seq=row["sequence"],
            op_type_name=row["op_type_name"],
            source=row["source_suggestion"],
            op_type_id=_suggested_key(identities, row["op_type_ref"], "op_type"),
            supplier_id=_suggested_key(identities, row["supplier_ref"], "supplier"),
            ext_days=row["external_days"],
        )
        changed = True
    if part["route_raw"] != preview["route_raw"] or part["route_parsed"] != "yes":
        PartRepository(conn).update(part["part_no"], {"route_raw": preview["route_raw"], "route_parsed": "yes"})
        changed = True
    return changed
