"""Source diagnostics shared by confirmations, reads and batch replacement."""

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.resource_capabilities import supports_source

SOURCE_MESSAGES = {
    "source_missing": "尚未明确自制或外协归属。",
    "type_missing": "缺少明确工种。",
    "type_source_mismatch": "的工种不支持本序归属，请先核对工艺。",
    "supplier_missing": "的供应商未填写。",
    "supplier_invalid": "的供应商不存在、已停用或有停用原因，或未登记本序能力。",
    "group_missing": "的外协组不存在，请先完善工艺。",
    "group_part_mismatch": "的外协组被其他零件引用，请先核对外协组。",
    "group_range_invalid": "的外协组起止序无效，请先完善工艺。",
    "group_mode_unknown": "的外协组周期算法不明确，请先完善工艺。",
    "group_members_invalid": "的外协组包含非外协工序或超出范围的工序，请先核对成员。",
    "group_supplier_mismatch": "的合并外协组成员与组头供应商不一致，请整段核对供应商。",
    "group_supplier_invalid": "的合并外协组供应商不存在、已停用或未登记本序能力。",
    "internal_external_binding": "是自制工序，不能保留外协供应商或外协组关系。",
}


def valid_supplier(fact):
    return bool(fact is not None and fact["status"] == "active"
                and fact["capable"] and fact["inactive_reason"] is None)


def group_suppliers_consistent(group, supplier_ids):
    """Only a merged shipment requires all members to use the same supplier."""
    return group["merge_mode"] != "merged" or len(set(supplier_ids)) <= 1


def external_group_issues(group, members):
    """Diagnose the stored group once, including references from other parts."""
    issues = []
    valid_range = (type(group["start_seq"]) is int and type(group["end_seq"]) is int
                   and 0 < group["start_seq"] <= group["end_seq"])
    if not valid_range:
        issues.append("group_range_invalid")
    if group["merge_mode"] not in ("separate", "merged"):
        issues.append("group_mode_unknown")
    if any(op["part_no"] != group["part_no"] for op in members):
        issues.append("group_part_mismatch")
    if any(op["source"] != "external" or type(op["seq"]) is not int
           or valid_range and not group["start_seq"] <= op["seq"] <= group["end_seq"] for op in members):
        issues.append("group_members_invalid")
    if group["merge_mode"] == "merged":
        supplier_ids = {op["supplier_id"] for op in members}
        if len(supplier_ids) > 1 or group["supplier_id"] is not None and any(
                supplier_id != group["supplier_id"] for supplier_id in supplier_ids):
            issues.append("group_supplier_mismatch")
    return issues


class TemplateSourceFacts:
    """A captured catalog owns the supplier and external-group source rules."""

    def __init__(self, operations, groups, suppliers, capabilities, profiles):
        self.groups = {row["group_id"]: row for row in groups}
        self.suppliers = {row["supplier_id"]: row for row in suppliers}
        self.profiles = {row["supplier_id"]: row for row in profiles}
        self.capabilities = {row["supplier_id"]: {row["op_type_id"]} for row in suppliers}
        for row in capabilities:
            if row["supplier_id"] in self.capabilities:
                self.capabilities[row["supplier_id"]].add(row["op_type_id"])
        members = {}
        for op in operations:
            if op["status"] == "active" and op["ext_group_id"] is not None:
                members.setdefault(op["ext_group_id"], []).append(op)
        self.group_issues = {key: external_group_issues(group, members.get(key, []))
                             for key, group in self.groups.items()}

    def supplier_fact(self, supplier_id, op_type_id):
        supplier = self.suppliers.get(supplier_id)
        if supplier is None:
            return None
        profile = self.profiles.get(supplier_id)
        return {"status": supplier["status"],
                "inactive_reason": profile["inactive_reason"] if profile else None,
                "capable": op_type_id is not None and op_type_id in self.capabilities[supplier_id]}

    def issues(self, op, *, type_name, category):
        source, issues = op["source"], []
        if source not in OPERATION_SOURCES:
            issues.append("source_missing")
        if type_name is None:
            issues.append("type_missing")
        elif source in OPERATION_SOURCES and not supports_source(category, source):
            issues.append("type_source_mismatch")
        if source == "internal" and (op["supplier_id"] is not None or op["ext_group_id"] is not None):
            issues.append("internal_external_binding")
        elif source == "external":
            if op["supplier_id"] is None:
                issues.append("supplier_missing")
            elif not valid_supplier(self.supplier_fact(op["supplier_id"], op["op_type_id"])):
                issues.append("supplier_invalid")
            group = self.groups.get(op["ext_group_id"])
            if op["ext_group_id"] is not None and group is None:
                issues.append("group_missing")
            if group is not None:
                issues.extend(self.group_issues[group["group_id"]])
                if group["part_no"] != op["part_no"] and "group_part_mismatch" not in issues:
                    issues.append("group_part_mismatch")
                if (group["merge_mode"] == "merged" and group["supplier_id"] is not None
                        and not valid_supplier(self.supplier_fact(group["supplier_id"], op["op_type_id"]))):
                    issues.append("group_supplier_invalid")
        return issues
