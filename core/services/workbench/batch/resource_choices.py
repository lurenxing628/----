"""Batch resource facts shared by display, choices and operation changes."""

from collections import defaultdict

from core.models.resource_capabilities import machine_type_index, supplier_capability_rows
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService


class BatchResourceFacts:
    def __init__(self, facts):
        self.catalogs = {kind: {row[key]: row for row in facts[table]} for kind, table, key in (
            ("machine", "Machines", "machine_id"), ("operator", "Operators", "operator_id"),
            ("supplier", "Suppliers", "supplier_id"), ("op_type", "OpTypes", "op_type_id"),
            ("material", "Materials", "material_id"))}
        self.machine_types = machine_type_index(facts["Machines"], facts.get("MachineOpTypes", []))
        self.links = {(row["operator_id"], row["machine_id"]) for row in facts["OperatorMachine"]}
        self.supplier_types = defaultdict(set)
        for row in supplier_capability_rows(facts["Suppliers"], facts["WorkbenchSupplierOpTypes"], status="active"):
            if not row["missing_supplier"]:
                self.supplier_types[row["supplier_id"]].add(row["op_type_id"])
        self.profiles, self.skills = defaultdict(list), defaultdict(list)
        for row in facts["WorkbenchOperatorProfiles"]:
            self.profiles[row["operator_id"]].append(dict(row, profile_operator_id=row["operator_id"]))
        for row in facts["OperatorSkill"]:
            category = self.catalogs["op_type"].get(row["op_type_id"], {}).get("category")
            self.skills[row["operator_id"]].append(dict(row, category=category))
        self.qualifications, self.qualification_errors = {}, {}

    def qualification(self, code):
        if code not in self.qualifications and code not in self.qualification_errors:
            profiles = self.profiles[code] or [{"operator_id": code, "profile_operator_id": None, "skills_declared": None}]
            try:
                self.qualifications[code] = OperatorQualificationService.project_facts([code], profiles, self.skills[code])[code]
            except OperatorQualificationError as exc:
                self.qualification_errors[code] = exc
        return self.qualifications.get(code)

    def operator_issues(self, operator_id, op_type_id, machine_id):
        issues = []
        if operator_id and machine_id and (operator_id, machine_id) not in self.links:
            issues.append({"code": "data_gap", "message": "所选人员未获设备操作授权。"})
        if operator_id in self.catalogs["operator"]:
            skills = self.qualification(operator_id)
            if operator_id in self.qualification_errors:
                issues.append({"code": "operator_qualification_invalid", "message": str(self.qualification_errors[operator_id])})
            elif skills is not None and op_type_id not in skills:
                issues.append({"code": "data_gap", "message": "所选人员未登记本工种资格。"})
        return issues

    def require_operator(self, operator_id, op_type_id, machine_id):
        if not operator_id:
            return
        if machine_id and (operator_id, machine_id) not in self.links:
            raise OperatorQualificationError(
                f"人员“{operator_id}”未被配置为可操作设备“{machine_id}”。"
                "请先在【人员管理】或【设备管理】中维护人机关联后再排产。",
                field="设备/人员", details={"reason": "operator_machine_not_authorized", "operator_id": operator_id, "machine_id": machine_id})
        skills = self.qualification(operator_id)
        if operator_id in self.qualification_errors:
            raise self.qualification_errors[operator_id]
        if skills is not None and op_type_id not in skills:
            raise OperatorQualificationError(
                f"人员“{operator_id}”未登记自制工种“{op_type_id or '未填写'}”的资格，不能分配；请核对技能登记。",
                field="operator_qualification", details={"reason": "operator_skill_not_qualified", "operator_id": operator_id, "op_type_id": op_type_id})

    def supplier_capable(self, supplier_id, op_type_id):
        return op_type_id in self.supplier_types.get(supplier_id, ())

    def choice_reason(self, kind, row, op):
        code = row["business_code"]
        if row["status"] != "active":
            return "当前不可用"
        if (kind == "supplier") != (op["source"] == "external"):
            return "不适用于此工序归属"
        if kind == "operator":
            issues = self.operator_issues(code, op["op_type_id"], op["machine_id"])
            return issues[0]["message"] if issues else ""
        if kind == "machine":
            if op["op_type_id"] not in self.machine_types.get(code, ()):
                return "未具备该工序工种能力"
            if op["operator_id"] and (op["operator_id"], code) not in self.links:
                return "所选人员未获设备操作授权。"
            return ""
        return "" if self.supplier_capable(code, op["op_type_id"]) else "未具备该工序工种能力"


def operation_choices(reader, batch_ref, operation_ref, choices, resources, facts):
    batch = reader.batch(batch_ref)
    op = next((row for row in facts["BatchOperations"] if row["batch_id"] == batch["batch_id"]
               and facts["operation_refs"][row["id"]] == operation_ref), None)
    if op is None:
        raise WorkbenchCommandRejected("entity_not_found", "这道工序已失效或不属于当前批次，请刷新后重新选择。", 404)
    for kind, name in (("machine", "machines"), ("operator", "operators"), ("supplier", "suppliers")):
        for row in choices[name]:
            reason = resources.choice_reason(kind, row, op)
            row["eligible"] = not reason
            row["unavailable_reason"] = reason
    return choices
