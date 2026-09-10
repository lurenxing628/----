"""Resource fields follow existing explicit profiles, not inferred UI status."""

from .master_overview_graph import number, text

CATALOGS = (("opType", "OpTypes", "op_type_id"), ("equipment", "Machines", "machine_id"),
            ("personnel", "Operators", "operator_id"), ("material", "Materials", "material_id"),
            ("supplier", "Suppliers", "supplier_id"))


def add_resources(graph):
    for domain, table, key in CATALOGS:
        for row in graph.facts.rows(table):
            entity = graph.add(domain, row[key], row[key], row["name"], category=row.get("category") if domain == "opType" else None)
            for name, label in ((key, "编号"), ("name", "名称")):
                graph.field(entity, label, row[name], table + "." + name)
                if not isinstance(row[name], str) or not row[name].strip():
                    graph.issue(entity, name + ".missing", label + "未填写", "原始字段：" + table + "." + name)
            graph.field(entity, "备注", row.get("remark"), table + ".remark", required=False)
            if domain == "opType":
                _op_type(graph, entity, row)
            else:
                _status(graph, entity, row, domain, table)
            if domain == "material":
                _material(graph, entity, row)
            if domain == "supplier":
                days = row["default_days"]
                graph.field(entity, "默认周期（天）", days, "Suppliers.default_days", valid=number(days, True))
                if not number(days, True):
                    graph.issue(entity, "supplier.days", "供应商默认周期待核对", "默认周期：" + text(days) + "；应为正数天数。")


def _status(graph, entity, row, domain, table):
    raw = row["status"]
    graph.field(entity, "原始状态", raw, table + ".status")
    if raw == "active":
        return
    if domain == "equipment" and raw == "maintain":
        graph.issue(entity, "machine.maintain", "设备处于检修", "Machines.status=maintain；未推断检修结束日期。")
        return
    if raw == "inactive" and domain in ("equipment", "material"):
        entity["inactive"] = True
        return
    if raw == "inactive" and domain in ("personnel", "supplier"):
        profile_table, key = (("WorkbenchOperatorProfiles", "operator_id") if domain == "personnel"
                              else ("WorkbenchSupplierProfiles", "supplier_id"))
        profile = graph.facts.index(profile_table, key).get(row[key])
        reason = profile["inactive_reason"] if profile else None
        graph.field(entity, "停用原因", reason, profile_table + ".inactive_reason")
        if reason == "disabled":
            entity["inactive"] = True
            return
        if reason in ("leave", "pending_review"):
            graph.issue(entity, "status." + reason, "人员处于请假状态" if reason == "leave" else "供应商待复核",
                        "状态来自显式资料：" + profile_table + ".inactive_reason=" + reason)
            return
    graph.unknown(entity, "状态含义", table + ".status")
    graph.issue(entity, "status.unknown", "原状态或停用原因未知", "原状态：" + text(raw) + "；没有证据认定为启用、停用、请假或待复核。")


def _op_type(graph, entity, row):
    category = row["category"]
    graph.field(entity, "工种归属", {"internal": "自制", "external": "外协"}.get(category, category), "OpTypes.category",
                valid=category in ("internal", "external"))
    if category not in ("internal", "external"):
        graph.issue(entity, "category.unknown", "工种归属未明确", "OpTypes.category：" + text(category))
        entity["target"]["unavailable_reason"] = "工种类别未知，不能猜测自制或外协维护节点。"
    if category == "external":
        if not graph.facts.available("WorkbenchOpTypePolicies"):
            graph.unknown(entity, "周期策略", "WorkbenchOpTypePolicies")
            return
        policy = graph.facts.index("WorkbenchOpTypePolicies", "op_type_id").get(row["op_type_id"])
        mode = policy["default_merge_mode"] if policy else None
        label = {"separate": "分别设置", "merged": "合并设置"}.get(mode, mode) if mode is not None else None
        graph.field(entity, "周期策略", label, "WorkbenchOpTypePolicies.default_merge_mode")
        if mode not in ("separate", "merged"):
            graph.issue(entity, "policy.missing", "外协周期策略未设置", "显式周期策略为空或无效；未补默认配置。")


def _material(graph, entity, row):
    for name, label in (("spec", "规格"), ("unit", "库存单位")):
        graph.field(entity, label, row[name], "Materials." + name)
        if not isinstance(row[name], str) or not row[name].strip():
            graph.issue(entity, "material." + name, label + "未填写", "原始字段：Materials." + name)
    value = row["stock_qty"]
    graph.field(entity, "库存数量", value, "Materials.stock_qty", valid=number(value))
    if not number(value):
        graph.issue(entity, "material.stock", "库存数量待核对", "库存：" + text(value) + "；0合法，未知不补0。")


def resource_links(graph):
    facts = graph.facts
    for row in facts.rows("Machines"):
        entity = graph.by_key[("equipment", row["machine_id"])]
        target = graph.related(entity, "opType", row["op_type_id"], "绑定工种", "Machines.op_type_id", "关联设备", required=True)
        if target and facts.index("OpTypes", "op_type_id")[row["op_type_id"]]["category"] != "internal":
            graph.issue(entity, "machine.category", "设备绑定非自制工种", "实际绑定工种：" + target["business_code"] + "；不能认定自制产能。")
    _explicit_links(graph, "OperatorSkill", "personnel", "operator_id", "opType", "op_type_id", "登记技能", "技能人员")
    _explicit_links(graph, "OperatorMachine", "personnel", "operator_id", "equipment", "machine_id", "设备操作授权", "获授权人员")
    for row in facts.rows("Suppliers"):
        graph.related(graph.by_key[("supplier", row["supplier_id"])], "opType", row["op_type_id"], "具备外协能力", "Suppliers.op_type_id", "关联供应商")
    _explicit_links(graph, "WorkbenchSupplierOpTypes", "supplier", "supplier_id", "opType", "op_type_id", "具备外协能力", "关联供应商")
    _qualification_fields(graph)
    _op_resources(graph)


def _explicit_links(graph, table, domain, owner, other_domain, other_key, label, reverse):
    if not graph.facts.available(table):
        for entity in graph.entities:
            if entity["domain"] in (domain, other_domain):
                graph.unknown(entity, label, table, relation=True)
        return
    for row in graph.facts.rows(table):
        entity = graph.by_key.get((domain, row[owner]))
        if entity:
            graph.related(entity, other_domain, row[other_key], label, table, reverse, required=True)
        else:
            other = graph.by_key.get((other_domain, row[other_key]))
            if other:
                graph.issue(other, table + ".owner_missing", "关系所属记录缺失", "来源：" + table + "；不能确认反向关系。")
                other["relations_complete"] = False


def _qualification_fields(graph):
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
                    graph.issue(entity, "qualification.empty", "人员未登记技能" if domain == "personnel" else "供应商未绑定外协工种",
                                "已读取显式记录为0；设备授权不代替技能。" if domain == "personnel" else "旧单工种与显式能力并集为空。")
            expected = "internal" if domain == "personnel" else "external"
            if any(types[item["business_code"]]["category"] != expected for item in bound):
                graph.issue(entity, "qualification.category", "绑定工种类别不符", "人员技能应为自制，供应商能力应为外协；未更改工种归属。")
            if domain == "personnel":
                _person_fields(graph, entity, row, profiles, shifts)


def _person_fields(graph, entity, row, profiles, shifts):
    profile = profiles.get(row["operator_id"])
    if graph.facts.available("WorkbenchOperatorProfiles", "WorkbenchShiftProfiles"):
        shift = shifts.get(profile["shift_profile_id"]) if profile else None
        graph.field(entity, "班次", shift["name"] if shift else None, "WorkbenchOperatorProfiles.shift_profile_id -> WorkbenchShiftProfiles.name")
        if shift is None:
            graph.issue(entity, "shift.missing", "人员班次未登记或已缺失", "未用班组或个人日历代替显式班次配置。")
        else:
            graph.field(entity, "班次状态", shift["status"], "WorkbenchShiftProfiles.status")
            if shift["status"] != "active":
                graph.issue(entity, "shift.inactive", "人员班次未启用", "绑定班次：" + shift["name"])
        declared = bool(profile and profile["skills_declared"] or any(item["relation"] == "登记技能" for item in entity["relations"]))
        graph.field(entity, "技能登记情况", "已明确登记" if declared else "存量未明确登记", "WorkbenchOperatorProfiles.skills_declared + OperatorSkill")
        if not declared:
            graph.unknown(entity, "技能声明", "WorkbenchOperatorProfiles.skills_declared")
    else:
        graph.unknown(entity, "班次与技能声明", "WorkbenchOperatorProfiles / WorkbenchShiftProfiles")
    if graph.facts.available("OperatorMachine"):
        count = sum(item["relation"] == "设备操作授权" for item in entity["relations"])
        graph.field(entity, "设备授权数", count, "OperatorMachine")
        if not count:
            graph.issue(entity, "authorization.empty", "人员未获设备操作授权", "OperatorMachine显式授权为0；技能不自动授予设备操作权。")


def _op_resources(graph):
    for row in graph.facts.rows("OpTypes"):
        entity = graph.by_key[("opType", row["op_type_id"])]
        checks = (("关联供应商", "Suppliers", "供应商"),) if row["category"] == "external" else (
            ("关联设备", "Machines", "设备"), ("技能人员", "OperatorSkill", "技能人员"))
        for relation, source, label in checks:
            if not graph.facts.available(source):
                graph.unknown(entity, label + "关联数", source, relation=True)
            else:
                count = sum(item["relation"] == relation for item in entity["relations"])
                graph.field(entity, label + "关联数", count, source)
                if count == 0:
                    graph.issue(entity, "op.resources." + source, "未找到关联" + label, "已读取关系为0；不使用页面装饰数或名称匹配。")
