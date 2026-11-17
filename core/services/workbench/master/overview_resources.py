"""Resource fields follow existing explicit profiles; status words come from the shared resource status rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.enums import MERGE_MODE_LABELS, OP_TYPE_CATEGORY_LABELS, RESOURCE_STATUS_LABELS
from core.models.resource_capabilities import machine_type_index, supports_source
from core.models.workbench_resource_status import SPECIAL_INACTIVE_REASONS, reasoned_resource_state, table_status_label
from core.shared.strict_parse import is_stored_number

from .overview_graph import KINDS, text

if TYPE_CHECKING:
    from .overview_graph import MasterOverviewGraph

CATALOGS = (("opType", "OpTypes", "op_type_id"), ("equipment", "Machines", "machine_id"),
            ("personnel", "Operators", "operator_id"), ("material", "Materials", "material_id"),
            ("supplier", "Suppliers", "supplier_id"))
#: 有停用原因的两类资料各自的档案表。
_PROFILES = {"operator": ("WorkbenchOperatorProfiles", "operator_id"), "supplier": ("WorkbenchSupplierProfiles", "supplier_id")}
#: 暂时用不了、需要有人跟进的对外状态；停用的资料不算待办。
_PAUSED = {
    "maintain": ("machine.maintain", "设备处于停机", "设备状态为停机，但没有登记停机结束日期。"),
    "leave": ("status.leave", "人员处于请假状态", "资料里单独登记的停用原因是" + RESOURCE_STATUS_LABELS["leave"] + "。"),
    "pending_review": ("status.pending_review", "供应商待复核",
                       "资料里单独登记的停用原因是" + RESOURCE_STATUS_LABELS["pending_review"] + "。"),
}


def add_resources(graph: MasterOverviewGraph):
    for domain, table, key in CATALOGS:
        for row in graph.facts.rows(table):
            entity = graph.add(domain, row[key], row[key], row["name"], category=row["category"] if domain == "opType" else None)
            for name, label in ((key, "编号"), ("name", "名称")):
                graph.field(entity, label, row[name], table + "." + name)
                if not isinstance(row[name], str) or not row[name].strip():
                    graph.issue(entity, name + ".missing", label + "未填写", "这条资料的" + label + "未填写，请补充。")
            graph.field(entity, "备注", row["remark"], table + ".remark", required=False)
            if domain == "opType":
                _op_type(graph, entity, row)
            else:
                _status(graph, entity, row, domain, table)
            if domain == "material":
                _material(graph, entity, row)
            if domain == "supplier":
                # 默认周期由表约束定为必填且在 (0, 36500] 天。
                graph.field(entity, "默认周期（天）", row["default_days"], "Suppliers.default_days")


def _status(graph: MasterOverviewGraph, entity, row, domain, table):
    kind = KINDS[domain]
    status = row["status"]
    graph.field(entity, "状态", table_status_label(kind, status), table + ".status")
    if kind in SPECIAL_INACTIVE_REASONS:
        profile_table, key = _PROFILES[kind]
        state = reasoned_resource_state(kind, status, graph.facts.index(profile_table, key).get(row[key]))
        status = state["status"]
        if state["inactive_reason"] is not None:
            graph.field(entity, "停用原因", RESOURCE_STATUS_LABELS[status], profile_table + ".inactive_reason")
    if status == "inactive":
        entity["inactive"] = True
    elif status != "active":
        graph.issue(entity, *_PAUSED[status])


def _op_type(graph: MasterOverviewGraph, entity, row):
    category = row["category"]
    graph.field(entity, "工种归属", OP_TYPE_CATEGORY_LABELS[category], "OpTypes.category")
    if supports_source(category, "external"):
        policy = graph.facts.index("WorkbenchOpTypePolicies", "op_type_id").get(row["op_type_id"])
        graph.field(entity, "周期算法", MERGE_MODE_LABELS[policy["default_merge_mode"]] if policy else None,
                    "WorkbenchOpTypePolicies.default_merge_mode")
        if policy is None:
            graph.issue(entity, "policy.missing", "外协周期算法未设置", "请设置该工种的外协周期算法。")


def _material(graph: MasterOverviewGraph, entity, row):
    for name, label in (("spec", "规格"), ("unit", "库存单位")):
        graph.field(entity, label, row[name], "Materials." + name)
        if not isinstance(row[name], str) or not row[name].strip():
            graph.issue(entity, "material." + name, label + "未填写", "这条物料的" + label + "未填写，请补充。")
    value = row["stock_qty"]
    valid = is_stored_number(value)
    graph.field(entity, "库存数量", value, "Materials.stock_qty", valid=valid)
    if not valid:
        graph.issue(entity, "material.stock", "库存数量待核对", "库存数量现在是" + text(value) + "，请填写有效数量，可填 0。")


def resource_links(graph: MasterOverviewGraph):
    facts = graph.facts
    machine_types = machine_type_index(facts.rows("Machines"), facts.rows("MachineOpTypes"))
    for row in facts.rows("Machines"):
        entity = graph.by_key[("equipment", row["machine_id"])]
        codes = sorted(machine_types[row["machine_id"]])
        for code in codes or [None]:
            target = graph.related(entity, "opType", code, "可做工种", "MachineOpTypes", "关联设备", required=True)
            if target and not supports_source(facts.index("OpTypes", "op_type_id")[code]["category"], "internal"):
                graph.issue(entity, "machine.category", "设备能力不支持自制", "请核对设备所选工种的适用归属。")
    _explicit_links(graph, "OperatorSkill", "personnel", "operator_id", "opType", "op_type_id", "登记技能", "技能人员")
    _explicit_links(graph, "OperatorMachine", "personnel", "operator_id", "equipment", "machine_id", "设备操作授权", "获授权人员")
    _explicit_links(graph, "WorkbenchSupplierOpTypes", "supplier", "supplier_id", "opType", "op_type_id", "具备外协能力", "关联供应商")
    _qualification_fields(graph)
    _op_resources(graph)


def _explicit_links(graph: MasterOverviewGraph, table, domain, owner, other_domain, other_key, label, reverse):
    for row in graph.facts.rows(table):
        entity = graph.by_key.get((domain, row[owner]))
        if entity:
            graph.related(entity, other_domain, row[other_key], label, table, reverse, required=True)
        else:
            other = graph.by_key.get((other_domain, row[other_key]))
            if other:
                graph.issue(other, table + ".owner_missing", "有一条关联的另一头记录已不存在", "关联里另一头的记录找不到了，这条反向关系确认不了。")
                other["relations_complete"] = False


def _qualification_fields(graph: MasterOverviewGraph):
    facts = graph.facts
    profiles = facts.index("WorkbenchOperatorProfiles", "operator_id")
    shifts = facts.index("WorkbenchShiftProfiles", "profile_id")
    types = facts.index("OpTypes", "op_type_id")
    for domain, table, key in (("personnel", "Operators", "operator_id"), ("supplier", "Suppliers", "supplier_id")):
        for row in facts.rows(table):
            entity = graph.by_key[(domain, row[key])]
            relation_label = "登记技能" if domain == "personnel" else "具备外协能力"
            bound = [item for item in entity["relations"] if item["relation"] == relation_label]
            if entity["relations_complete"]:
                graph.field(entity, "登记工种数", len(bound), "OperatorSkill" if domain == "personnel" else "Suppliers + WorkbenchSupplierOpTypes")
                if not bound:
                    graph.issue(entity, "qualification.empty", "人员未登记技能" if domain == "personnel" else "供应商未选外协工种",
                                "请登记该人员具备的技能工种。" if domain == "personnel"
                                else "这家供应商没有登记任何可做的外协工种。")
            expected = "internal" if domain == "personnel" else "external"
            if any(not supports_source(types[item["business_code"]]["category"], expected) for item in bound):
                graph.issue(entity, "qualification.category", "绑定工种类别不符",
                            "人员请选择自制工种，供应商请选择外协工种。")
            if domain == "personnel":
                _person_fields(graph, entity, row, profiles, shifts)


def _person_fields(graph: MasterOverviewGraph, entity, row, profiles, shifts):
    profile = profiles.get(row["operator_id"])
    shift = shifts.get(profile["shift_profile_id"]) if profile else None
    graph.field(entity, "班次", shift["name"] if shift else None, "WorkbenchOperatorProfiles.shift_profile_id -> WorkbenchShiftProfiles.name")
    if shift is None:
        graph.issue(entity, "shift.missing", "人员班次待设置", "请为该人员选择有效班次。")
    else:
        graph.field(entity, "班次状态", table_status_label("shift_profile", shift["status"]), "WorkbenchShiftProfiles.status")
        if shift["status"] != "active":
            graph.issue(entity, "shift.inactive", "人员班次未启用", "所在班次是" + text(shift["name"]) + "，这个班次当前不是启用状态。")
    declared = bool(profile and profile["skills_declared"] or any(item["relation"] == "登记技能" for item in entity["relations"]))
    graph.field(entity, "技能登记情况", "已明确登记" if declared else "老数据，未单独登记", "WorkbenchOperatorProfiles.skills_declared + OperatorSkill")
    if not declared:
        graph.unknown(entity, "技能登记", "WorkbenchOperatorProfiles.skills_declared")
    count = sum(item["relation"] == "设备操作授权" for item in entity["relations"])
    graph.field(entity, "设备授权数", count, "OperatorMachine")
    if not count:
        graph.issue(entity, "authorization.empty", "人员未获设备操作授权",
                    "请为该人员设置可操作设备。")


def _op_resources(graph: MasterOverviewGraph):
    for row in graph.facts.rows("OpTypes"):
        entity = graph.by_key[("opType", row["op_type_id"])]
        checks = []
        if supports_source(row["category"], "internal"):
            checks.extend((
                ("关联设备", "Machines", "设备"),
                ("技能人员", "OperatorSkill", "技能人员"),
            ))
        if supports_source(row["category"], "external"):
            checks.append(("关联供应商", "Suppliers", "供应商"))
        for relation, source, label in checks:
            count = sum(item["relation"] == relation for item in entity["relations"])
            graph.field(entity, label + "关联数", count, source)
            if count == 0:
                graph.issue(entity, "op.resources." + source, "未找到关联" + label,
                            "这个工种下没有登记任何" + label + "，请补充关联。")
