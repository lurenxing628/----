"""Field/resource checks preserve NULL; exclusion never masks required fields."""

import math
from collections import defaultdict
from datetime import date, datetime

from core.models.workbench_preflight import issue


def number(value, *, integer=False, positive=False):
    return (type(value) is int if integer else type(value) in (int, float)) and math.isfinite(value) and (
        0 < value <= 9007199254740991 if positive else 0 <= value <= 9007199254740991)


def stored_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        try:
            if date.fromisoformat(value).isoformat() == value:
                return value
        except ValueError:
            pass
    return None


class PreflightChecks:
    def __init__(self, tables):
        self.catalogs = {kind: {row[key]: row for row in tables[table]} for kind, table, key in (
            ("machine", "Machines", "machine_id"), ("operator", "Operators", "operator_id"),
            ("supplier", "Suppliers", "supplier_id"), ("op_type", "OpTypes", "op_type_id"))}
        self.links = {(row["operator_id"], row["machine_id"]) for row in tables["OperatorMachine"]}
        self.skills = defaultdict(set)
        for row in tables["OperatorSkill"]:
            self.skills[row["operator_id"]].add(row["op_type_id"])
        for row in tables["WorkbenchOperatorProfiles"]:
            if row["skills_declared"]:
                self.skills[row["operator_id"]]
        self.supplier_skills = defaultdict(set)
        for row in tables["WorkbenchSupplierOpTypes"]:
            self.supplier_skills[row["supplier_id"]].add(row["op_type_id"])
        self.templates = {(row["part_no"], row["seq"]): row for row in tables["PartOperations"] if row["status"] == "active"}
        self.groups = {row["group_id"]: row for row in tables["ExternalGroups"]}
        self.materials = defaultdict(list)
        for row in tables["BatchMaterials"]:
            self.materials[row["batch_id"]].append(row)

    def fields(self, batch, op):
        gaps = []
        if not number(batch["quantity"], integer=True):
            gaps.append(issue("quantity_unknown", "批次数量未填写或无效，请到批次管理补填。"))
        if not number(op["seq"], integer=True, positive=True):
            gaps.append(issue("sequence_invalid", "工序顺序号不合法，排不出前后关系。请到批次管理核对工序号。"))
        if op["op_type_id"] not in self.catalogs["op_type"]:
            gaps.append(issue("op_type_missing", "这道工序的工种没有登记。请到资料总览补登工种。"))
        if op["source"] == "internal":
            for key, label in (("setup_hours", "换型工时"), ("unit_hours", "单件工时")):
                if not number(op[key]):
                    gaps.append(issue("hours_missing", label + "未填写或无效；填 0 和不填不是一回事。请到基础资料补填。"))
        elif op["source"] == "external":
            supplier = self.catalogs["supplier"].get(op["supplier_id"])
            if not supplier or supplier["status"] != "active":
                gaps.append(issue("supplier_missing", "外协供应商没填或已停用。请到资料总览核对供应商。"))
            elif op["op_type_id"] not in self.supplier_skills.get(op["supplier_id"], {supplier.get("op_type_id")}):
                gaps.append(issue("supplier_skill_missing", "这家供应商没有登记该外协工种。请到资料总览补登。"))
            template = self.templates.get((batch["part_no"], op["seq"]), {})
            group = self.groups.get(template.get("ext_group_id"))
            days = group["total_days"] if group and group["merge_mode"] == "merged" else op["ext_days"]
            if not number(days, positive=True):
                gaps.append(issue("external_days_missing", "外协周期没填或无效，缺设备人员时的规则也补不上。请到基础资料补填周期。"))
        else:
            gaps.append(issue("source_missing", "这道工序是自制还是外协还没确认。请到基础资料确认归属。"))
        return gaps

    def resources(self, op):
        if op["source"] != "internal":
            return []
        missing = []
        machine = self.catalogs["machine"].get(op["machine_id"])
        operator = self.catalogs["operator"].get(op["operator_id"])
        if not machine or machine["status"] != "active" or machine["op_type_id"] != op["op_type_id"]:
            missing.append(issue("machine_missing", "设备没填、已停用，或者工种对不上。请改派设备，或到资料总览核对。"))
        if not operator or operator["status"] != "active":
            missing.append(issue("operator_missing", "人员没填或不在岗。请改派人员，或到资料总览核对。"))
        if operator and op["operator_id"] in self.skills and op["op_type_id"] not in self.skills[op["operator_id"]]:
            missing.append(issue("operator_skill_missing", "这个人员没有该工种的资格。请改派人员，或到资料总览补资格。"))
        if machine and operator and (op["operator_id"], op["machine_id"]) not in self.links:
            missing.append(issue("machine_authorization_missing", "这个人员没有该设备的操作授权。请改派人员，或到资料总览补授权。"))
        return missing

    def readiness(self, batch, enabled):
        if not enabled:
            return []
        reasons = []
        if batch["ready_status"] != "yes":
            reasons.append(issue("batch_not_ready", "这批还没确认齐套。请到批次管理确认齐套状态。"))
        for row in self.materials[batch["batch_id"]]:
            required, available = row["required_qty"], row["available_qty"]
            if not number(required, positive=True) or not number(available):
                reasons.append(issue("material_unknown", "物料需求量或到料数量没填，算不出齐不齐套。请到批次管理核对物料需求。"))
            elif available < required or row["ready_status"] != "yes":
                reasons.append(issue("material_not_ready", "这批的物料还没到齐。请到批次管理核对物料需求。"))
        return reasons
