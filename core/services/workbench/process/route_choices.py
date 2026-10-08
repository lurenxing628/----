"""Preview the choices that route confirmation will actually persist."""

from copy import deepcopy

from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .projection import project_external_days, project_group

_SUGGESTION_ISSUES = frozenset(("unknown_op_type", "supplier_missing", "multiple_supplier_candidates",
                               "external_days_missing_or_invalid", "invalid_op_type_category"))


def _group_members(repo, operations):
    group_keys = {row["ext_group_id"] for row in operations if row["ext_group_id"]}
    group_rows = {row["group_id"]: row for row in repo.groups() if row["group_id"] in group_keys} if group_keys else {}
    members = {}
    if group_rows:
        for row in repo.operations():
            if row["status"] == "active" and row["ext_group_id"] in group_rows:
                members.setdefault(row["ext_group_id"], []).append(row)
    return group_rows, members


def route_choice_context(conn, operations):
    identities = WorkbenchIdentityRepository(conn)
    type_refs = identities.active_map("op_type", {row["op_type_id"] for row in operations if row["op_type_id"]})
    supplier_refs = identities.active_map("supplier", {row["supplier_id"] for row in operations if row["supplier_id"]})
    repo = WorkbenchProcessQueryRepository(conn)
    group_rows, members = _group_members(repo, operations)
    return {"type_refs": type_refs, "supplier_refs": supplier_refs,
            "types": {row["op_type_id"]: row["name"] for row in repo.op_type_reference_rows()},
            "suppliers": {row["supplier_id"]: row["name"] for row in repo.supplier_reference_rows()},
            "group_rows": group_rows, "groups": {key: project_group(row, members.get(key, [])) for key, row in group_rows.items()}}


def _changed_route_sequences(existing, proposed):
    incoming = {row["sequence"]: row for row in proposed}
    changed = {seq for seq, old in existing.items() if old["status"] == "active" and
               (seq not in incoming or old["op_type_name"] != incoming[seq]["op_type_name"])}
    changed.update(seq for seq in incoming if seq not in existing or existing[seq]["status"] != "active")
    return changed


def _intersects_changed_range(group, changed):
    if type(group["start_seq"]) is not int or type(group["end_seq"]) is not int:
        return False
    return any(type(seq) is int and group["start_seq"] <= seq <= group["end_seq"] for seq in changed)


def _discarded_groups(existing, proposed, context):
    changed = _changed_route_sequences(existing, proposed)
    linked = {old["ext_group_id"] for seq, old in existing.items() if seq in changed and old["ext_group_id"]}
    return linked | {key for key, group in context["group_rows"].items() if _intersects_changed_range(group, changed)}


def _retained_cycle(row, old, context, discarded):
    group = context["groups"].get(old["ext_group_id"]) if old["ext_group_id"] not in discarded else None
    issues = []
    days, source = project_external_days(old, row["source_suggestion"], group["ref"] if group else None, group, issues)
    if source == "group":
        if group is None:
            raise RuntimeError("Merged route cycle requires an external group.")
        row["external_days"] = group["total_days"]
        row["basis"] += "按外协段 " + str(group["start_sequence"]) + " 至 " + str(group["end_sequence"]) + " 的统一周期计算一次；原逐序周期不参与排产。"
    else:
        row["external_days"] = days
        if old["ext_group_id"] in discarded:
            row["basis"] += "本次会解除原外协段，保存后按本序周期计算，请核对显示值。"
    row["issues"].extend(issues)


def _preview_replacement(row, old, result):
    cleared = [label + " " + str(old[field]) + " 小时" for field, label in
               (("setup_hours", "换型工时"), ("unit_hours", "单件工时")) if old[field] is not None]
    message = "名称已改为另一已登记工种，将采用本行的工种、归属、供应商和周期，并重新确认归属与工时。"
    if cleared:
        message += "将清除原" + "、".join(cleared) + "，避免沿用其他工种的定额。"
    if old["ext_days"] is not None:
        message += "原外协周期 " + str(old["ext_days"]) + " 天将改为本行显示的周期，未填写表示需要补齐。"
    row["basis"] = message + row["basis"]
    row["issues"].append({"code": "route_operation_rebound", "message": message})
    result["diagnostics"].append({"code": "route_operation_rebound", "severity": "warning",
                                  "sequence": row["sequence"], "message": message})


def _preview_retained(row, old, old_ref, result, context, discarded):
    # Cosmetic changes and repeated confirmation preserve intentional choices.
    supplier_refs = context["supplier_refs"]
    row["issues"] = [issue for issue in row["issues"] if issue["code"] not in _SUGGESTION_ISSUES]
    result["diagnostics"] = [issue for issue in result["diagnostics"] if not
                             (issue.get("sequence") == row["sequence"] and issue["code"] in _SUGGESTION_ISSUES)]
    row.update(op_type_ref=old_ref, source_suggestion=old["source"] if old["source"] in ("internal", "external") else None,
               supplier_ref=supplier_refs[old["supplier_id"]].ref if old["supplier_id"] in supplier_refs else None,
               supplier_label=context["suppliers"].get(old["supplier_id"]), external_days=old["ext_days"])
    row["basis"] = "保留原工序已选的实际工种“" + (context["types"].get(old["op_type_id"]) or "未选择") + "”、归属、供应商和工时；本次没有重新套用默认值。"
    _retained_cycle(row, old, context, discarded)


def _preview_existing_operation(row, old, result, context, discarded):
    type_refs = context["type_refs"]
    old_ref = type_refs[old["op_type_id"]].ref if old["op_type_id"] in type_refs else None
    replace = (old["op_type_name"] != row["op_type_name"] and row["op_type_ref"] is not None
               and row["op_type_ref"] != old_ref)
    row["replace_existing_choices"] = replace
    if replace:
        _preview_replacement(row, old, result)
    else:
        _preview_retained(row, old, old_ref, result, context, discarded)
    return replace


def preview_existing_route(conn, preview, operations, context=None):
    result = deepcopy(preview)
    result["_choices_projected"] = True
    existing = {row["seq"]: row for row in operations}
    if not existing:
        return result
    context = route_choice_context(conn, operations) if context is None else context
    discarded = _discarded_groups(existing, result["operations"], context)
    for row in result["operations"]:
        old = existing.get(row["sequence"])
        if old is not None:
            _preview_existing_operation(row, old, result, context, discarded)
    result["counts"]["recognized"] = sum(row["op_type_ref"] is not None for row in result["operations"])
    result["counts"]["unknown"] = len(result["operations"]) - result["counts"]["recognized"]
    return result
