"""Field/resource checks preserve NULL; exclusion never masks required fields."""

import math
from collections import defaultdict
from datetime import date, datetime

from core.models.resource_capabilities import machine_type_index, supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_preflight import issue
from core.services.material.stage_availability import MaterialAvailability, covers_quantity, quantity
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    member_index,
    merged_supplier_problem,
)


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
        self.machine_types = machine_type_index(tables["Machines"], tables.get("MachineOpTypes", []))
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
        self.external_contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
        self.external_members = member_index(self.external_contexts, tables.get("BatchOperations", []))
        self.availability = MaterialAvailability(tables)
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
        work_type = self.catalogs["op_type"].get(op["op_type_id"])
        if work_type is not None and not supports_source(work_type["category"], op["source"]):
            gaps.append(issue("source_category_mismatch", "该工种不支持本序所选的自制或外协归属，请先核对工艺。"))
        if op["source"] == "internal":
            for key, label in (("setup_hours", "换型工时"), ("unit_hours", "单件工时")):
                if not number(op[key]):
                    gaps.append(issue("hours_missing", label + "未填写或无效；填 0 和不填不是一回事。请到基础资料补填。"))
        elif op["source"] == "external":
            gaps.extend(self._external_fields(batch, op))
        else:
            gaps.append(issue("source_missing", "这道工序是自制还是外协还没确认。请到基础资料确认归属。"))
        return gaps

    def _external_fields(self, batch, op):
        gaps = []
        supplier = self.catalogs["supplier"].get(op["supplier_id"])
        if not supplier or supplier["status"] != "active":
            gaps.append(issue("supplier_missing", "外协供应商没填或已停用。请到资料总览核对供应商。"))
        elif op["op_type_id"] not in self.supplier_skills.get(op["supplier_id"], {supplier.get("op_type_id")}):
            gaps.append(issue("supplier_skill_missing", "这家供应商没有登记该外协工种。请到资料总览补登。"))
        context = self.external_contexts.get(op["id"])
        problem = (context_problem(context, operation_id=op["id"], part_no=batch["part_no"], sequence=op["seq"])
                   if batch["quantity"] != 0 else None)
        if problem:
            gaps.append(issue("external_context_invalid", problem))
        elif batch["quantity"] != 0:
            problem = merged_supplier_problem(context, op["supplier_id"],
                self.external_members.get((op["batch_id"], context_group_key(context), op.get("piece_id"))))
            if problem:
                gaps.append(issue("external_context_invalid", problem))
        days = context["total_days"] if context and context["merge_mode"] == "merged" else op["ext_days"]
        if not number(days, positive=True):
            gaps.append(issue("external_days_missing", "外协周期没填或无效，缺设备人员时的规则也补不上。请到基础资料补填周期。"))
        return gaps

    def resources(self, op):
        if op["source"] != "internal":
            return []
        missing = []
        machine = self.catalogs["machine"].get(op["machine_id"])
        operator = self.catalogs["operator"].get(op["operator_id"])
        if not machine or machine["status"] != "active" or op["op_type_id"] not in self.machine_types.get(op["machine_id"], set()):
            missing.append(issue("machine_missing", "设备没填、已停用，或者工种对不上。请改派设备，或到资料总览核对。"))
        if not operator or operator["status"] != "active":
            missing.append(issue("operator_missing", "人员没填或不在岗。请改派人员，或到资料总览核对。"))
        if operator and op["operator_id"] in self.skills and op["op_type_id"] not in self.skills[op["operator_id"]]:
            missing.append(issue("operator_skill_missing", "这个人员没有该工种的资格。请改派人员，或到资料总览补资格。"))
        if machine and operator and (op["operator_id"], op["machine_id"]) not in self.links:
            missing.append(issue("machine_authorization_missing", "这个人员没有该设备的操作授权。请改派人员，或到资料总览补授权。"))
        return missing

    def protected_resources(self, op):
        """Actual history needs surviving identities, not today's qualifications.

        Call only after the execution guard has proven this exact arrangement
        or its shared actual external cycle. Ordinary locked plans use resources.
        """
        gaps = []
        if op["op_type_id"] not in self.catalogs["op_type"]:
            gaps.append(issue("op_type_missing", "实际工序的原工种身份缺失，请核对历史记录。"))
        if op["source"] == "external":
            kinds = ("supplier",)
            if op["machine_id"] is not None or op["operator_id"] is not None:
                gaps.append(issue("external_actual_resource_conflict", "外协实际记录不能占用本厂设备人员。"))
        elif op["source"] == "internal":
            kinds = ("machine", "operator")
        else:
            return gaps + [issue("source_missing", "实际工序的自制或外协归属缺失，请核对历史记录。")]
        for kind in kinds:
            if op[kind + "_id"] not in self.catalogs[kind]:
                gaps.append(issue(kind + "_identity_missing", "实际记录的原设备、人员或供应商身份缺失，请核对历史记录。"))
        return gaps

    def readiness(self, batch, enabled):
        if not enabled:
            return []
        if hasattr(self, "availability") and any(row["id"] in self.availability.reviews for row in self.materials[batch["batch_id"]]):
            status, problems = self.availability.readiness_state(batch, date.today().isoformat())
            return problems or ([] if status == "yes" else [issue("material_not_ready", "按当前日期的到料，物料尚未全部齐套。")])
        reasons = []
        if batch["ready_status"] != "yes":
            reasons.append(issue("batch_not_ready", "这批还没确认齐套。请到批次管理确认齐套状态。"))
        for row in self.materials[batch["batch_id"]]:
            required, available = row["required_qty"], row["available_qty"]
            if not number(required, positive=True) or not number(available):
                reasons.append(issue("material_unknown", "物料需求量或到料数量没填，算不出齐不齐套。请到批次管理核对物料需求。"))
            elif not covers_quantity(quantity(available), quantity(required)) or row["ready_status"] != "yes":
                reasons.append(issue("material_not_ready", "这批的物料还没到齐。请到批次管理核对物料需求。"))
        return reasons

    def operation_readiness(self, batch, op, settings):
        if not settings["ready_check"]:
            return [], None
        if not self.materials[batch["batch_id"]]:
            return self.readiness(batch, True), None
        if not any(row["id"] in self.availability.reviews for row in self.materials[batch["batch_id"]]):
            return self.readiness(batch, True), None
        try:
            day = self.availability.operation_release(batch, op, settings.get("material_strategy", "strict"))
        except WorkbenchCommandRejected as exc:
            return [issue(exc.code, str(exc))], None
        if day is None:
            return [issue("material_not_ready", "本序或前序所需物料未到齐，也没有足够的分次到料记录；本序及后序暂不排产。")], None
        if day > settings["end_date"]:
            return [issue("material_after_window", "本序物料到齐日期为 " + day + "，晚于本次排产止日。")], day
        return [], day
