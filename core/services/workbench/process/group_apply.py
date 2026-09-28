"""Validate and apply explicit outsourcing-stage edits in the command transaction."""

from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.part_operation_repo import PartOperationRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .group_defaults import create_group
from .route_apply import discard_groups
from .stage_apply import require_supplier, source_catalog


def _members(row, active, positions):
    missing = set(row["operation_refs"]) - set(active)
    if missing:
        raise WorkbenchCommandRejected("group_member_invalid", "所选工序已停用、已删除或属于其他零件。请刷新外协段。", 422)
    members = sorted((active[ref] for ref in row["operation_refs"]), key=lambda op: op["seq"])
    span = positions[members[-1]["ref"]] - positions[members[0]["ref"]] + 1
    if span != len(members) or any(op["source"] != "external" for op in members):
        raise WorkbenchCommandRejected("group_not_contiguous", "同一次外协必须是路线中连续的外协工序，不能跳过自制工序或其他工序。请分别建立外协段。", 422,
                                       operation_refs=row["operation_refs"])
    if len({op["supplier_id"] for op in members}) > 1:
        raise WorkbenchCommandRejected("group_supplier_mismatch", "所选工序当前分属不同供应商，请先在归属页核对为同一家供应商，再合成一段。", 422,
                                       operation_refs=row["operation_refs"])
    return members


def _prepare_group(conn, row, members, old, replaced, identities, catalog):
    if any(op["ext_group_id"] is not None and op["ext_group_id"] not in replaced for op in members):
        raise WorkbenchCommandRejected("group_overlap", "所选工序仍属于其他外协段。请先调整或明确解除原段，不能覆盖其他段。", 422,
                                       operation_refs=row["operation_refs"])
    supplier = identities.get(row["supplier_ref"])
    if supplier is None or not supplier.active or supplier.kind != "supplier":
        raise WorkbenchCommandRejected("invalid_relation", "所选供应商已失效，请重新选择。", 422)
    for member in members:
        require_supplier(conn, member, supplier.entity_key, member["op_type_id"], catalog)
    return {"old": old, "members": members, "supplier_id": supplier.entity_key, "total_days": row["total_days"]}


def prepare_groups(conn, payload, operations, groups, identities):
    active = {row["ref"]: row for row in operations if row["status"] == "active"}
    positions = {row["ref"]: index for index, row in enumerate(sorted(active.values(), key=lambda op: op["seq"]))}
    stored = {row["ref"]: row for row in groups}
    touched = {row["ref"] for row in payload["groups"] if row["ref"] is not None} | set(payload["discard_group_refs"])
    if touched - set(stored):
        raise WorkbenchCommandRejected("group_invalid", "要修改或解除的外协段已删除或属于其他零件。请刷新后重新选择。", 422)
    replaced = {stored[ref]["group_id"] for ref in touched}
    prepared, catalog = [], source_catalog(conn)
    for row in payload["groups"]:
        members = _members(row, active, positions)
        prepared.append(_prepare_group(conn, row, members, stored.get(row["ref"]), replaced, identities, catalog))
    return prepared, [stored[ref] for ref in payload["discard_group_refs"]]


def group_changes(conn, prepared, discarded, operations):
    names = {row["supplier_id"]: row["name"] for row in WorkbenchProcessQueryRepository(conn).supplier_reference_rows()}
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


def apply_groups(conn, part_no, prepared, discarded, operations):
    changes = group_changes(conn, prepared, discarded, operations)
    if not changes:
        return False
    discard_groups(conn, part_no, discarded)
    op_repo, group_repo = PartOperationRepository(conn), ExternalGroupRepository(conn)
    changed_refs = {row["ref"] for row in changes if row["action"] == "update"}
    # Detach every edited range first so splitting/moving members is independent of row order.
    for item in prepared:
        if item["old"] and item["old"]["ref"] in changed_refs:
            op_repo.clear_external_group(part_no, item["old"]["group_id"])
    for item in prepared:
        old, members = item["old"], item["members"]
        if old and old["ref"] not in changed_refs:
            continue
        if old:
            group_id = old["group_id"]
            group_repo.update(group_id, {"start_seq": members[0]["seq"], "end_seq": members[-1]["seq"],
                "merge_mode": "merged", "total_days": item["total_days"], "supplier_id": item["supplier_id"]})
        else:
            group_id = create_group(conn, part_no, members, item["supplier_id"], item["total_days"])
        for member in members:
            op_repo.update(part_no, member["seq"], {"ext_group_id": group_id, "supplier_id": item["supplier_id"]})
    return True
