"""Resource fields follow existing explicit profiles, not inferred UI status."""

from .master_overview_graph import number, text

CATALOGS = (("opType", "OpTypes", "op_type_id"), ("equipment", "Machines", "machine_id"),
            ("personnel", "Operators", "operator_id"), ("material", "Materials", "material_id"),
            ("supplier", "Suppliers", "supplier_id"))
STATUS_TEXT = {"active": "启用", "maintain": "停机", "inactive": "停用"}
REASON_TEXT = {"disabled": "已停用", "leave": "请假", "pending_review": "待复核"}


def _shown(value, labels):
    """英文枚举换成中文显示值；系统不认识的原值照抄，好让用户回去改。"""
    return labels.get(value, value)


def add_resources(graph):
    for domain, table, key in CATALOGS:
        for row in graph.facts.rows(table):
            entity = graph.add(domain, row[key], row[key], row["name"], category=row.get("category") if domain == "opType" else None)
            for name, label in ((key, "编号"), ("name", "名称")):
                graph.field(entity, label, row[name], table + "." + name)
                if not isinstance(row[name], str) or not row[name].strip():
                    graph.issue(entity, name + ".missing", label + "未填写", "这条资料的" + label + "是空的，系统不会自动补。")
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
                    graph.issue(entity, "supplier.days", "供应商默认周期待核对", "默认周期现在是" + text(days) + "，应该填大于 0 的天数。")


def _status(graph, entity, row, domain, table):
    raw = row["status"]
    graph.field(entity, "状态", _shown(raw, STATUS_TEXT), table + ".status")
    if raw == "active":
        return
    if domain == "equipment" and raw == "maintain":
        graph.issue(entity, "machine.maintain", "设备处于停机", "设备状态为停机，但没有登记停机结束日期。")
        return
    if raw == "inactive" and domain in ("equipment", "material"):
        entity["inactive"] = True
        return
    if raw == "inactive" and domain in ("personnel", "supplier"):
        profile_table, key = (("WorkbenchOperatorProfiles", "operator_id") if domain == "personnel"
                              else ("WorkbenchSupplierProfiles", "supplier_id"))
        profile = graph.facts.index(profile_table, key).get(row[key])
        reason = profile["inactive_reason"] if profile else None
        graph.field(entity, "停用原因", _shown(reason, REASON_TEXT), profile_table + ".inactive_reason")
        if reason == "disabled":
            entity["inactive"] = True
            return
        if reason in ("leave", "pending_review"):
            graph.issue(entity, "status." + reason, "人员处于请假状态" if reason == "leave" else "供应商待复核",
                        "资料里单独登记的停用原因是" + REASON_TEXT[reason] + "。")
            return
    graph.unknown(entity, "状态含义", table + ".status")
    graph.issue(entity, "status.unknown", "状态或停用原因不明确",
                "资料里记的状态是「" + text(raw) + "」，系统不认识，判断不出是启用、停用、请假还是待复核。")


def _op_type(graph, entity, row):
    category = row["category"]
    graph.field(entity, "工种归属", {"internal": "自制", "external": "外协"}.get(category, category), "OpTypes.category",
                valid=category in ("internal", "external"))
    if category not in ("internal", "external"):
        graph.issue(entity, "category.unknown", "工种归属未明确", "资料里记的工种归属是「" + text(category) + "」，只能填自制或外协。")
        entity["target"]["unavailable_reason"] = "工种归属还没填自制或外协，系统不知道该跳到哪个维护页。"
    if category == "external":
        if not graph.facts.available("WorkbenchOpTypePolicies"):
            graph.unknown(entity, "周期算法", "WorkbenchOpTypePolicies")
            return
        policy = graph.facts.index("WorkbenchOpTypePolicies", "op_type_id").get(row["op_type_id"])
        mode = policy["default_merge_mode"] if policy else None
        label = {"separate": "分别设置", "merged": "合并设置"}.get(mode, mode) if mode is not None else None
        graph.field(entity, "周期算法", label, "WorkbenchOpTypePolicies.default_merge_mode")
        if mode not in ("separate", "merged"):
            graph.issue(entity, "policy.missing", "外协周期算法未设置", "这个工种没有单独设置外协周期算法，系统不会替你套默认值。")


def _material(graph, entity, row):
    for name, label in (("spec", "规格"), ("unit", "库存单位")):
        graph.field(entity, label, row[name], "Materials." + name)
        if not isinstance(row[name], str) or not row[name].strip():
            graph.issue(entity, "material." + name, label + "未填写", "这条物料的" + label + "是空的，系统不会自动补。")
    value = row["stock_qty"]
    graph.field(entity, "库存数量", value, "Materials.stock_qty", valid=number(value))
    if not number(value):
        graph.issue(entity, "material.stock", "库存数量待核对", "库存数量现在是" + text(value) + "，填 0 可以，空着系统不会当成 0。")


def resource_links(graph):
    facts = graph.facts
    for row in facts.rows("Machines"):
        entity = graph.by_key[("equipment", row["machine_id"])]
        target = graph.related(entity, "opType", row["op_type_id"], "绑定工种", "Machines.op_type_id", "关联设备", required=True)
        if target and facts.index("OpTypes", "op_type_id")[row["op_type_id"]]["category"] != "internal":
            graph.issue(entity, "machine.category", "设备绑定非自制工种",
                        "这台设备绑的工种是" + target["business_code"] + "，不是自制工种，不能算成自制产能。")
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
                graph.issue(other, table + ".owner_missing", "有一条关联的另一头记录已不存在", "关联里另一头的记录找不到了，这条反向关系确认不了。")
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
                    graph.issue(entity, "qualification.empty", "人员未登记技能" if domain == "personnel" else "供应商未选外协工种",
                                "没有给这个人单独登记任何技能工种，设备操作授权不等于会做这道工序。" if domain == "personnel"
                                else "这家供应商没有登记任何可做的外协工种。")
            expected = "internal" if domain == "personnel" else "external"
            if any(types[item["business_code"]]["category"] != expected for item in bound):
                graph.issue(entity, "qualification.category", "绑定工种类别不符",
                            "人员的技能工种应该是自制，供应商的能力工种应该是外协；系统不会替你改工种归属。")
            if domain == "personnel":
                _person_fields(graph, entity, row, profiles, shifts)


def _person_fields(graph, entity, row, profiles, shifts):
    profile = profiles.get(row["operator_id"])
    if graph.facts.available("WorkbenchOperatorProfiles", "WorkbenchShiftProfiles"):
        shift = shifts.get(profile["shift_profile_id"]) if profile else None
        graph.field(entity, "班次", shift["name"] if shift else None, "WorkbenchOperatorProfiles.shift_profile_id -> WorkbenchShiftProfiles.name")
        if shift is None:
            graph.issue(entity, "shift.missing", "人员班次未登记或已缺失", "这个人没有单独配班次，系统不会拿班组或个人日历顶替。")
        else:
            graph.field(entity, "班次状态", _shown(shift["status"], STATUS_TEXT), "WorkbenchShiftProfiles.status")
            if shift["status"] != "active":
                graph.issue(entity, "shift.inactive", "人员班次未启用", "所在班次是" + shift["name"] + "，这个班次当前不是启用状态。")
        declared = bool(profile and profile["skills_declared"] or any(item["relation"] == "登记技能" for item in entity["relations"]))
        graph.field(entity, "技能登记情况", "已明确登记" if declared else "老数据，未单独登记", "WorkbenchOperatorProfiles.skills_declared + OperatorSkill")
        if not declared:
            graph.unknown(entity, "技能登记", "WorkbenchOperatorProfiles.skills_declared")
    else:
        graph.unknown(entity, "班次与技能登记", "WorkbenchOperatorProfiles / WorkbenchShiftProfiles")
    if graph.facts.available("OperatorMachine"):
        count = sum(item["relation"] == "设备操作授权" for item in entity["relations"])
        graph.field(entity, "设备授权数", count, "OperatorMachine")
        if not count:
            graph.issue(entity, "authorization.empty", "人员未获设备操作授权",
                        "没有单独授权这个人操作任何设备，会做这道工序不等于有设备操作权。")


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
                    graph.issue(entity, "op.resources." + source, "未找到关联" + label,
                                "这个工种下没有登记任何" + label + "，系统不会按名称去凑。")
