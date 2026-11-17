"""Validate and apply explicit outsourcing-stage edits in the command transaction."""

import json

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.workflow_state import (
    reset_group_hours_confirmations,
    reset_part_confirmations_from,
)
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.part_operation_repo import PartOperationRepository

from .group_defaults import create_group
from .stage_apply import require_supplier


def _member_paths(row, field):
    return tuple("operations." + ref + "." + field for ref in row["operation_refs"])


def _members(row, active, positions):
    missing = set(row["operation_refs"]) - active.keys()
    if missing:
        raise WorkbenchCommandRejected("group_member_invalid", "所选工序已停用、已删除或属于其他零件。请刷新外协段。", 422)
    members = sorted((active[ref] for ref in row["operation_refs"]), key=lambda op: op["seq"])
    span = positions[members[-1]["ref"]] - positions[members[0]["ref"]] + 1
    if span != len(members) or any(op["source"] != "external" for op in members):
        raise WorkbenchCommandRejected("group_not_contiguous", "同一次外协必须是路线中连续的外协工序，不能跳过自制工序或其他工序。请分别建立外协段。", 422,
                                       fields=_member_paths(row, "external_group_ref"))
    if len({op["supplier_id"] for op in members}) > 1:
        raise WorkbenchCommandRejected("group_supplier_mismatch", "所选工序当前分属不同供应商，请先在归属页核对为同一家供应商，再合成一段。", 422,
                                       fields=_member_paths(row, "supplier_ref"))
    return members


def _prepare_group(row, members, old, replaced, identities, catalog):
    if any(op["ext_group_id"] is not None and op["ext_group_id"] not in replaced for op in members):
        raise WorkbenchCommandRejected("group_overlap", "所选工序仍属于其他外协段。请先调整或明确解除原段，不能覆盖其他段。", 422,
                                       fields=_member_paths(row, "external_group_ref"))
    supplier = identities.get(row["supplier_ref"])
    if supplier is None or not supplier.active or supplier.kind != "supplier":
        raise WorkbenchCommandRejected("invalid_relation", "所选供应商已失效，请重新选择。", 422)
    for member in members:
        require_supplier(member, supplier.entity_key, member["op_type_id"], catalog)
    return {"old": old, "members": members, "supplier_id": supplier.entity_key, "total_days": row["total_days"]}


def prepare_groups(payload, operations, groups, identities, *, catalog):
    active = {row["ref"]: row for row in operations if row["status"] == "active"}
    positions = {row["ref"]: index for index, row in enumerate(sorted(active.values(), key=lambda op: op["seq"]))}
    stored = {row["ref"]: row for row in groups}
    touched = {row["ref"] for row in payload["groups"] if row["ref"] is not None} | set(payload["discard_group_refs"])
    if touched - set(stored):
        raise WorkbenchCommandRejected("group_invalid", "要修改或解除的外协段已删除或属于其他零件。请刷新后重新选择。", 422)
    replaced = {stored[ref]["group_id"] for ref in touched}
    prepared = []
    for row in payload["groups"]:
        members = _members(row, active, positions)
        prepared.append(_prepare_group(row, members, stored.get(row["ref"]), replaced, identities, catalog))
    return prepared, [stored[ref] for ref in payload["discard_group_refs"]]


def group_changes(prepared, discarded, operations, *, names):
    by_group = {}
    for op in operations:
        if op["status"] == "active" and op["ext_group_id"] is not None:
            by_group.setdefault(op["ext_group_id"], []).append(op)
    def summary(group, members, supplier_id, total_days):
        label = names.get(supplier_id)
        mismatched = [row for row in members if group and row["supplier_id"] != supplier_id]
        if mismatched:
            label = (label or "未选供应商") + "；" + "、".join("工序 {} 当前供应商 {}".format(
                row["seq"], names.get(row["supplier_id"]) or row["supplier_id"] or "未选") for row in mismatched)
        return {"operation_refs": [row["ref"] for row in members], "sequences": [str(row["seq"]) for row in members],
                "supplier_id": supplier_id, "supplier_label": label, "total_days": total_days,
                "merge_mode": group["merge_mode"] if group else "merged"}
    def before(group):
        members = by_group.get(group["group_id"], [])
        return summary(group, members, group["supplier_id"], group["total_days"])
    changes = []
    for item in prepared:
        old = item["old"]
        previous = before(old) if old else None
        after = summary(None, item["members"], item["supplier_id"], item["total_days"])
        if previous != after:
            changes.append({"ref": old["ref"] if old else None, "action": "update" if old else "create", "before": previous, "after": after})
    changes.extend({"ref": group["ref"], "action": "discard", "before": before(group), "after": None} for group in discarded)
    return changes


def apply_groups(conn, part_no, prepared, discarded, operations, *, changes):
    if not changes:
        return False
    op_repo, group_repo = PartOperationRepository(conn), ExternalGroupRepository(conn)
    source_changed_ids, cycle_only_groups = _affected_confirmations(prepared, discarded, operations, changes)
    final = _final_memberships(conn, part_no, prepared, discarded, operations, changes)
    for op in operations:
        if op["id"] in final:
            fields = {key: value for key, value in final[op["id"]].items() if op[key] != value}
            if fields:
                op_repo.update_fields_by_id(op["id"], fields)
    for group in discarded:
        group_repo.delete_for_part(part_no, group["group_id"])
    if source_changed_ids:
        op_repo.reset_confirmations_by_ids(json.dumps(list(source_changed_ids)))
        reset_part_confirmations_from(conn, part_no, "source")
    elif discarded:
        reset_part_confirmations_from(conn, part_no, "source")
    if cycle_only_groups:
        reset_group_hours_confirmations(conn, cycle_only_groups)
    return True


def _is_cycle_only_group_update(old, members, old_members, supplier_id) -> bool:
    if [op["id"] for op in old_members] != [member["id"] for member in members]:
        return False
    if (old["start_seq"], old["end_seq"], old["merge_mode"], old["supplier_id"]) != (
        members[0]["seq"],
        members[-1]["seq"],
        "merged",
        supplier_id,
    ):
        return False
    return all(op["supplier_id"] == supplier_id for op in old_members)


def _affected_confirmations(prepared, discarded, operations, changes):
    active_by_group = {}
    for op in operations:
        if op["status"] == "active" and op["ext_group_id"] is not None:
            active_by_group.setdefault(op["ext_group_id"], []).append(op)
    changed_refs = {row["ref"] for row in changes if row["action"] == "update"}
    source_changed_ids = {
        op["id"] for group in discarded for op in active_by_group.get(group["group_id"], ())
    }
    cycle_only_groups = []
    for item in prepared:
        old, members = item["old"], item["members"]
        if old is None:
            source_changed_ids.update(member["id"] for member in members)
        elif old["ref"] in changed_refs:
            old_members = active_by_group.get(old["group_id"], ())
            if _is_cycle_only_group_update(old, members, old_members, item["supplier_id"]):
                cycle_only_groups.append(old["group_id"])
            else:
                source_changed_ids.update(op["id"] for op in old_members)
                source_changed_ids.update(member["id"] for member in members)
    return source_changed_ids, cycle_only_groups


def _final_memberships(conn, part_no, prepared, discarded, operations, changes):
    changed_refs = {row["ref"] for row in changes if row["action"] == "update"}
    replaced = {group["group_id"] for group in discarded} | {
        item["old"]["group_id"] for item in prepared if item["old"] and item["old"]["ref"] in changed_refs}
    final = {op["id"]: {"ext_group_id": None, "supplier_id": op["supplier_id"]}
             for op in operations if op["ext_group_id"] in replaced}
    for item in prepared:
        old, members = item["old"], item["members"]
        if old and old["ref"] not in changed_refs:
            continue
        group_id = _write_group(conn, part_no, item)
        for member in members:
            final[member["id"]] = {"ext_group_id": group_id, "supplier_id": item["supplier_id"]}
    return final


def _write_group(conn, part_no, item):
    old, members = item["old"], item["members"]
    if old is None:
        return create_group(conn, part_no, members, item["supplier_id"], item["total_days"], attach=False)
    fields = {"start_seq": members[0]["seq"], "end_seq": members[-1]["seq"], "merge_mode": "merged",
              "total_days": item["total_days"], "supplier_id": item["supplier_id"]}
    changes = {key: value for key, value in fields.items() if old[key] != value}
    if changes:
        ExternalGroupRepository(conn).update(old["group_id"], changes)
    return old["group_id"]
