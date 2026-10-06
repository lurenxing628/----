"""Validate raw template facts for an explicit batch operation refresh."""

from core.errors import ValidationError
from core.models.workbench_batch import number
from core.services.process.template_source import source_issues, valid_external_group, valid_supplier

from .projection import issue


def template_diagnostics(rows, facts, batch):
    diagnostics = []
    sequences = set()
    types = {row["op_type_id"]: row for row in facts["OpTypes"]}
    groups, suppliers = _source_catalogs(rows, facts, batch)
    for row in rows:
        if type(row["seq"]) is not int or row["seq"] <= 0:
            diagnostics.append(issue("工序号 " + str(row["seq"]) + " 无效，请填写正整数。"))
        if row["seq"] in sequences:
            diagnostics.append(issue("工序号 " + str(row["seq"]) + " 重复，请先整理工艺路线。"))
        sequences.add(row["seq"])
        kind = types.get(row["op_type_id"])
        group = groups.get(row.get("ext_group_id"))
        supplier = suppliers.get(row.get("supplier_id"))
        group_supplier = suppliers.get(group["supplier_id"]) if group else None
        group_valid = (group is None or group["valid"] and (group["merge_mode"] == "separate" or group["supplier_id"] is None
                       or _supplier_valid(group_supplier, row["op_type_id"])))
        errors = source_issues(row, type_name=kind["name"] if kind else None,
                              category=kind["category"] if kind else None,
                              supplier_valid=_supplier_valid(supplier, row["op_type_id"]),
                              group=group, group_valid=group_valid)
        diagnostics.extend(issue("工序 " + str(row["seq"]) + " " + _SOURCE_MESSAGES[code]) for code in errors)
        if row["source"] == "internal":
            diagnostics.extend(_internal_diagnostics(row))
        elif row["source"] == "external":
            diagnostics.extend(_external_diagnostics(row, group))
    return diagnostics


_SOURCE_MESSAGES = {
    "source_missing": "尚未明确自制或外协归属。",
    "type_missing": "缺少明确工种。",
    "type_source_mismatch": "的工种不支持本序归属，请先核对工艺。",
    "supplier_missing": "的供应商未填写。",
    "supplier_invalid": "的供应商不存在或已停用，或未登记本序能力。",
    "group_invalid": "的外协组关系不完整，请先完善工艺。",
    "group_supplier_mismatch": "的供应商与外协组不一致，请先完善工艺。",
    "internal_external_binding": "是自制工序，不能保留外协供应商或外协组关系。",
}


def _source_catalogs(rows, facts, batch):
    members = {}
    for row in rows:
        members.setdefault(row.get("ext_group_id"), []).append((row["seq"], row["source"], row["supplier_id"]))
    groups = {group["group_id"]: dict(group, valid=valid_external_group(
        group, batch["part_no"], members.get(group["group_id"], []))) for group in facts["ExternalGroups"]}
    profiles = {row["supplier_id"]: row for row in facts["WorkbenchSupplierProfiles"]}
    suppliers = {row["supplier_id"]: dict(row, capabilities={row["op_type_id"]},
        inactive_reason=profiles.get(row["supplier_id"], {}).get("inactive_reason")) for row in facts["Suppliers"]}
    for row in facts["WorkbenchSupplierOpTypes"]:
        if row["supplier_id"] in suppliers:
            suppliers[row["supplier_id"]]["capabilities"].add(row["op_type_id"])
    return groups, suppliers


def _supplier_valid(supplier, op_type_id):
    return valid_supplier(dict(supplier, capable=op_type_id in supplier["capabilities"])) if supplier else False


def template_status(facts, batch):
    """The detail and replacement preview apply the same completeness policy."""
    rows = [row for row in facts["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
    workflow = facts["workflow"][batch["part_no"]]["workflow"]
    diagnostics = template_diagnostics(rows, facts, batch)
    if not rows:
        diagnostics.insert(0, issue("尚未录入有效工序，请先完善工艺路线。"))
    elif workflow["origin"] == "managed" and not workflow["ready"]:
        stage = {"route": "工艺路线", "source": "工序归属", "hours": "工时定额"}[workflow["stage"]]
        diagnostics.append(issue("请先到工艺详情保存并确认" + stage + "。"))
    return {**workflow, "operation_count": len(rows), "complete": not diagnostics, "diagnostics": diagnostics}


def _number_diagnostic(value, sequence, label, *, positive=False):
    prefix = "工序 " + str(sequence) + " 的" + label
    if value is None:
        return [issue(prefix + "未填写，请先补齐工艺。")]
    try:
        number(value, label, positive=positive)
    except ValidationError:
        return [issue(prefix + ("必须大于 0。" if positive else "必须为非负数。"))]
    return []


def _internal_diagnostics(row):
    diagnostics = []
    for key, label in (("setup_hours", "换型工时"), ("unit_hours", "单件工时")):
        diagnostics.extend(_number_diagnostic(row[key], row["seq"], label))
    return diagnostics


def _external_diagnostics(row, group):
    diagnostics = []
    days = group["total_days"] if group and group["merge_mode"] == "merged" else row["ext_days"]
    diagnostics.extend(_number_diagnostic(days, row["seq"], "整组外协周期" if group and group["merge_mode"] == "merged" else "外协周期", positive=True))
    return diagnostics
