"""Public batch facts, never guessed scheduling or execution state."""

import math
from collections import defaultdict
from datetime import date, datetime

from core.models.workbench_batch import FIELDS, MAX_INTEGER, PRIORITIES, READY, STATUSES
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_execution import batch_progress, operation_execution_fields
from core.services.workbench.batch_facts import index_relations
from core.services.workbench.process_projection import public_sequence


def issue(message, code="data_gap"):
    return {"code": code, "message": message}


def numeric(value, issues, label, *, integer=False, positive=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    valid = valid and 0 <= value <= MAX_INTEGER and (not positive or value > 0) and math.isfinite(value)
    if not valid:
        issues.append(issue(label + ("未填写。" if value is None else "原值不合法，请核对。")))
        return None
    return value


def date_text(value, issues, label):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        try:
            if date.fromisoformat(value).isoformat() == value:
                return value
        except ValueError:
            pass
    issues.append(issue(label + "原值不合法，请核对。"))
    return str(value)


class BatchProjection:
    def __init__(self, facts):
        self.facts = facts
        self.relations = index_relations(facts)
        self.refs = {(row["kind"], row["entity_key"]): row["ref"] for row in facts["WorkbenchEntityRefs"] if row["active"]}
        self.parts = {row["part_no"]: row for row in facts["Parts"]}
        self.catalogs = {kind: {row[key]: row for row in facts[table]} for kind, table, key in (
            ("machine", "Machines", "machine_id"), ("operator", "Operators", "operator_id"),
            ("supplier", "Suppliers", "supplier_id"), ("op_type", "OpTypes", "op_type_id"), ("material", "Materials", "material_id"))}
        self.templates = {(row["part_no"], row["seq"]): row for row in facts["PartOperations"] if row["status"] == "active"}
        self.groups = {row["group_id"]: row for row in facts["ExternalGroups"]}
        self.links = {(row["operator_id"], row["machine_id"]) for row in facts["OperatorMachine"]}
        self.skills = defaultdict(set)
        for row in facts["OperatorSkill"]:
            self.skills[row["operator_id"]].add(row["op_type_id"])
        for row in facts["WorkbenchOperatorProfiles"]:
            if row["skills_declared"]:
                self.skills[row["operator_id"]]

    def ref(self, kind, key):
        if key is None:
            return None
        value = self.refs.get((kind, str(key)))
        if value is None:
            raise WorkbenchCommandRejected("storage_failure", "永久实体引用不完整，未使用编号替代或自动补建。", 500)
        return value

    def resource(self, kind, key):
        if key is None:
            return None
        row = self.catalogs[kind].get(key)
        if row is None:
            return None
        return {"ref": self.ref(kind, key), "business_code": key, "label": row["name"], "status": row.get("status")}

    def group(self, batch, op):
        template = self.templates.get((batch["part_no"], op["seq"]))
        group = self.groups.get(template["ext_group_id"]) if template else None
        if not group:
            return None
        return {"ref": self.ref("template_external_group", group["group_id"]), "business_code": group["group_id"],
                "merge_mode": group["merge_mode"], "total_days": group["total_days"],
                "start_sequence": public_sequence(group["start_seq"]), "end_sequence": public_sequence(group["end_seq"])}

    def internal_issues(self, row, resources, numbers, issues):
        for key in ("setup_hours", "unit_hours"):
            numbers[key] = numeric(row[key], issues, "换型工时" if key == "setup_hours" else "单件工时")
        for kind in ("machine", "operator"):
            if resources[kind] is None or resources[kind]["status"] != "active":
                issues.append(issue("设备未补齐或不可用。" if kind == "machine" else "人员未补齐或不在岗。"))
        machine = self.catalogs["machine"].get(row["machine_id"])
        if machine and machine["op_type_id"] != row["op_type_id"]:
            issues.append(issue("设备与工序工种不匹配。"))
        if row["operator_id"] and row["machine_id"] and (row["operator_id"], row["machine_id"]) not in self.links:
            issues.append(issue("所选人员未获设备操作授权。"))
        if row["operator_id"] in self.skills and row["op_type_id"] not in self.skills[row["operator_id"]]:
            issues.append(issue("所选人员未登记本工种资格。"))

    def operation_issues(self, row, resources, group, numbers):
        issues = []
        if row["source"] == "internal":
            self.internal_issues(row, resources, numbers, issues)
        elif row["source"] == "external":
            if resources["supplier"] is None or resources["supplier"]["status"] != "active":
                issues.append(issue("供应商未补齐或已停用。"))
            if group and group["merge_mode"] == "merged":
                group["total_days"] = numeric(group["total_days"], issues, "整组周期", positive=True)
            else:
                numbers["ext_days"] = numeric(row["ext_days"], issues, "外协周期", positive=True)
        else:
            issues.append(issue("工序归属未明确。"))
        if not resources["op_type"]:
            issues.append(issue("工序工种未登记。"))
        # Hidden hours of external operations remain raw in storage, not defaulted.
        for key, value in numbers.items():
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or abs(value) > MAX_INTEGER):
                issues.append(issue("工时或周期原值无效。"))
                numbers[key] = None
        return issues

    def operation(self, batch, row, protected=False):
        resources = {kind: self.resource(kind, row[kind + "_id"]) for kind in ("machine", "operator", "supplier", "op_type")}
        group = self.group(batch, row) if row["source"] == "external" else None
        numbers = {key: row[key] for key in ("setup_hours", "unit_hours", "ext_days")}
        issues = self.operation_issues(row, resources, group, numbers)
        ref = self.facts["operation_refs"][row["id"]]
        execution = operation_execution_fields(row, ref, self.facts["execution"])
        issues.extend(execution["data_gaps"])
        return {"ref": ref, "operation_ref": ref, "business_code": row["op_code"], "sequence": public_sequence(row["seq"]),
                "piece_id": row["piece_id"], "label": row["op_type_name"], "source": row["source"], **execution,
                "setup_hours": numbers["setup_hours"], "unit_hours": numbers["unit_hours"],
                "external_days": numbers["ext_days"], **{kind + "_ref": item["ref"] if item else None for kind, item in resources.items()},
                "resources": resources, "external_group": group, "issues": issues,
                "editable": not protected and row["status"] == "pending" and row["source"] in ("internal", "external")}

    def entity(self, row):
        facts = self.relations[row["batch_id"]]
        issues = list(self.facts["execution"]["issues"])
        part = self.parts.get(row["part_no"])
        if part is None:
            raise WorkbenchCommandRejected("storage_failure", "批次所引用的零件不存在。", 500)
        ops = [self.operation(row, op, facts["protected"]) for op in sorted(facts["operations"], key=lambda op: (op["seq"], op["id"]))]
        fields = {key: row[key] for key in FIELDS}
        fields["quantity"] = numeric(row["quantity"], issues, "数量", integer=True)
        for key in ("due_date", "ready_date"):
            fields[key] = date_text(row[key], issues, "交期" if key == "due_date" else "齐套日期")
        for key, allowed in (("priority", PRIORITIES), ("ready_status", READY), ("status", STATUSES)):
            if row[key] not in allowed:
                issues.append(issue("原优先级、齐套或状态标记不明确。"))
        done, all_complete, status = batch_progress(ops, row["status"])
        if row["status"] == "completed" and (not ops or done != len(ops)):
            issues.append(issue("批次完成标记与全部工序不一致，不能据此认定整批完成。", "completion_inconsistent"))
        return {"ref": self.ref("batch", row["batch_id"]), "business_code": row["batch_id"], "label": part["part_name"],
                "status": status, "stored_status": row["status"], "execution_available": self.facts["execution"]["available"],
                "fields": fields, "relationships": {"part_ref": self.ref("part", row["part_no"]),
                    "part_no": row["part_no"], "part_name": part["part_name"], "operation_count": len(ops), "completed_count": done,
                    "gap_count": sum(bool(op["issues"]) for op in ops), "plan_reference_count": len(facts["plans"]),
                    "execution_reference_count": len(facts["events"]) + len(facts["reports"]),
                    "report_count": len(facts["reports"]), "legacy_fact_count": len(facts["events"]),
                    "material_requirement_count": len(facts["materials"])},
                "operations": ops, "all_operations_complete": all_complete, "issues": issues,
                "write_context": None, "protected": facts["protected"]}

    def materials(self, batch):
        rows = []
        for row in self.relations[batch["batch_id"]]["materials"]:
            material = self.catalogs["material"].get(row["material_id"])
            issues = []
            rows.append({"material_ref": self.ref("material", row["material_id"]), "business_code": row["material_id"],
                         "label": material["name"] if material else None, "unit": material["unit"] if material else None,
                         "required_quantity": numeric(row["required_qty"], issues, "需求数量", positive=True),
                         "available_quantity": numeric(row["available_qty"], issues, "到料数量"),
                         "ready_status": row["ready_status"], "issues": issues})
        return {"basis": "batch_material_requirements_not_stock", "requirements": rows, "count": len(rows),
                "display_status": batch["ready_status"], "display_date": date_text(batch["ready_date"], [], "齐套日期")}
