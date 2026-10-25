"""Route checks retain the current workflow's zero/unknown and merged-group rules."""

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.services.process.template_source import SOURCE_MESSAGES, TemplateSourceFacts

from .overview_graph import number, text

PARSED_TEXT = {"yes": "已解析", "no": "未解析"}
MERGE_TEXT = {"merged": "合并设置", "separate": "分别设置"}
SOURCE_TITLES = {
    "source_missing": ("operation.source", "归属未明确"),
    "type_source_mismatch": ("operation.category", "归属与工种类别不一致"),
    "supplier_invalid": ("operation.supplier", "工序供应商状态或能力待核对"),
    "group_missing": ("operation.group", "外协组缺失"),
    "group_part_mismatch": ("group.invalid", "外协组所属零件不符"),
    "group_range_invalid": ("group.invalid", "外协组范围无效"),
    "group_mode_unknown": ("group.invalid", "外协组周期算法无效"),
    "group_members_invalid": ("group.members", "外协组成员无效"),
    "group_supplier_mismatch": ("group.supplier", "合并外协组供应商不一致"),
    "group_supplier_invalid": ("group.supplier_invalid", "合并外协组供应商状态或能力待核对"),
    "internal_external_binding": ("operation.internal_external", "自制工序保留外协绑定"),
}


def add_process(graph):
    facts = graph.facts
    grouped = facts.grouped("PartOperations", "part_no")
    sources = (TemplateSourceFacts(facts.rows("PartOperations"), facts.rows("ExternalGroups"), facts.rows("Suppliers"),
                                   facts.rows("WorkbenchSupplierOpTypes"), facts.rows("WorkbenchSupplierProfiles"))
               if facts.available("PartOperations", "ExternalGroups", "OpTypes", "Suppliers",
                                  "WorkbenchSupplierOpTypes", "WorkbenchSupplierProfiles") else None)
    for row in facts.rows("Parts"):
        key = row["part_no"]
        part = graph.add("part", key, key, row["part_name"])
        for column, label in (("part_no", "图号"), ("part_name", "名称")):
            graph.field(part, label, row[column], "Parts." + column)
            if not isinstance(row[column], str) or not row[column].strip():
                graph.issue(part, column + ".missing", "零件基本信息不完整", "这个零件的" + label + "未填写，请补充。")
        graph.field(part, "备注", row.get("remark"), "Parts.remark", required=False)
        if not facts.available("PartOperations", "ExternalGroups"):
            graph.unknown(part, "工艺路线", "PartOperations / ExternalGroups", relation=True)
            continue
        operations = grouped.get(key, [])
        active = [op for op in operations if op["status"] == "active"]
        graph.field(part, "有效模板工序数", len(active), "PartOperations.status=active")
        if not active:
            graph.issue(part, "part.route_missing", "零件无有效模板工序", "请为该零件建立并确认工序。",
                        stage="route", action="录入或核对路线")
        if operations or isinstance(row["route_raw"], str) and row["route_raw"].strip():
            name = row["part_name"] if isinstance(row["part_name"], str) and row["part_name"].strip() else key
            route = graph.add("route", key, key, name + " · 工艺路线")
            graph.link(part, route, "工艺路线", "Parts -> PartOperations", "所属零件")
            _route(graph, route, row, operations, active, sources)
    _orphan_operations(graph, grouped)


def _route(graph, route, row, operations, active, sources):
    graph.field(route, "原始路线", row["route_raw"], "Parts.route_raw", required=False)
    graph.field(route, "路线解析标记", PARSED_TEXT.get(row["route_parsed"], row["route_parsed"]), "Parts.route_parsed")
    graph.field(route, "有效工序数", len(active), "PartOperations.status=active")
    graph.field(route, "保留历史工序数", len(operations) - len(active), "PartOperations.status", required=False)
    if (row["route_parsed"] == "yes") != bool(active):
        graph.issue(route, "route.state_mismatch", "路线标记与有效工序不一致",
                    "路线标记是" + text(PARSED_TEXT.get(row["route_parsed"], row["route_parsed"])) + "，实际有效工序 " + str(len(active)) + " 道。", stage="route")
    state = graph.facts.workflow.get(row["part_no"]) if graph.facts.workflow is not None else None
    _workflow_confirmation(graph, route, state)
    groups = graph.facts.index("ExternalGroups", "group_id")
    seen = set()
    for op in operations:
        op_ref = graph.facts.ref("template_operation", op["id"])
        if op["status"] not in ("active", "deleted"):
            graph.issue(route, "operation.status", "工序状态不明确", "资料里记的工序状态是「" + text(op["status"]) + "」，系统只认有效和已删除。",
                        stage="route", operation_ref=op_ref)
        if op["status"] != "active":
            continue
        if op["seq"] in seen or type(op["seq"]) is not int or op["seq"] <= 0:
            graph.issue(route, "operation.sequence", "工序号重复或无效", "工序号是" + text(op["seq"]) + "，重复了或者不是大于 0 的整数。",
                        stage="route", operation_ref=op_ref)
        seen.add(op["seq"])
        _operation(graph, route, op, op_ref, groups, state, sources)


def _workflow_confirmation(graph, route, state):
    if state is None:
        graph.unknown(route, "路线、归属与工时确认", "process.workflow_snapshot")
        return
    workflow = state["workflow"]
    labels = {"route": "路线", "source": "归属", "hours": "工时"}
    for stage, label in labels.items():
        confirmed = workflow[stage]["state"] == "confirmed"
        graph.field(route, label + "确认", "已确认" if confirmed else "待保存",
                    "process.workflow_snapshot." + stage, valid=confirmed)
    if not workflow["ready"]:
        stage = "route" if workflow["route"]["state"] != "confirmed" else workflow["stage"]
        message, action = {
            "route": ("请保存工艺路线，完成后再保存工序归属和工时定额。", "保存工艺路线"),
            "source": ("请保存工序归属，完成后再保存工时定额。", "保存工序归属"),
            "hours": ("请填写并保存工时定额。", "填写工时定额"),
        }[stage]
        graph.issue(route, "workflow.pending", "工艺确认尚未完成",
                    message, stage=stage, action=action)


def _operation(graph, route, op, ref, groups, state, sources):
    prefix = "工序 " + text(op["seq"]) + " " + text(op["op_type_name"])
    source = op["source"]
    def issue(rule, title, evidence, stage="source"):
        graph.issue(route, rule, title, prefix + "；" + evidence, stage=stage, operation_ref=ref)
    graph.field(route, prefix + "归属", {"internal": "自制", "external": "外协"}.get(source, source),
                "PartOperations.source", valid=source in OPERATION_SOURCES)
    graph.related(route, "opType", op["op_type_id"], "工序使用工种", "PartOperations.op_type_id", "使用它的路线", required=True, operation_ref=ref, stage="source")
    if sources is None:
        graph.unknown(route, prefix + "归属诊断", "PartOperations / ExternalGroups / Suppliers / WorkbenchSupplierProfiles")
    else:
        kind = graph.facts.index("OpTypes", "op_type_id").get(op["op_type_id"])
        errors = sources.issues(op, type_name=kind["name"] if kind else None, category=kind["category"] if kind else None)
        for code in errors:
            # Required relation reads above/below already display missing types and suppliers.
            if code not in ("type_missing", "supplier_missing"):
                rule, title = SOURCE_TITLES[code]
                issue(rule, title, SOURCE_MESSAGES[code])
    if source == "internal":
        for key, label in (("setup_hours", "换型工时"), ("unit_hours", "单件工时")):
            value = op[key]
            graph.field(route, prefix + label + "（小时）", value, "PartOperations." + key, valid=number(value))
            if not number(value):
                issue("operation." + key, label + ("未填写" if value is None else "数值异常"),
                      label + "填的是" + text(value) + "，要填 0 或大于 0 的数字。", "hours")
        confirmation = state["operations"].get(ref) if state else None
        if op["unit_hours"] == 0 and (not confirmation or confirmation["hours"]["state"] != "confirmed"):
            issue("operation.zero_review", "单件工时 0 待复核", "请核对单件工时；确实为 0 时，在工时定额页按 0 保存。", "hours")
    if source == "external":
        _external(graph, route, op, ref, groups, prefix, issue)


def _external(graph, route, op, ref, groups, prefix, issue):
    graph.related(route, "supplier", op["supplier_id"], "工序供应商", "PartOperations.supplier_id", "使用它的路线", required=True, operation_ref=ref, stage="source")
    group = _external_group(graph, route, op, groups, prefix)
    merged = group and group["merge_mode"] == "merged"
    value = group["total_days"] if group is not None and merged else op["ext_days"]
    label = "整组周期" if merged else "逐序周期"
    graph.field(route, prefix + label + "（天）", value, "ExternalGroups.total_days" if merged else "PartOperations.ext_days", valid=number(value, True))
    if not number(value, True):
        issue("operation.days", "外协周期待维护", label + "填的是" + text(value) + "，请填写大于 0 的周期。", "hours")
    if merged:
        graph.field(route, prefix + "保留的逐序周期（天）", op["ext_days"], "PartOperations.ext_days", required=False)


def _external_group(graph, route, op, groups, prefix):
    group = groups.get(op["ext_group_id"])
    if op["ext_group_id"] is not None and (group is None or group["part_no"] != op["part_no"]):
        group = None
    if group:
        graph.field(route, prefix + "外协组周期算法", MERGE_TEXT.get(group["merge_mode"], group["merge_mode"]), "ExternalGroups.merge_mode")
        graph.related(route, "supplier", group["supplier_id"], "外协组供应商", "ExternalGroups.supplier_id", "使用它的路线")
    return group


def _orphan_operations(graph, grouped):
    parts = graph.facts.index("Parts", "part_no")
    count = sum(len(rows) for key, rows in grouped.items() if key not in parts)
    if count:
        graph.facts.gaps.append({"code": "orphan_operations", "source": "PartOperations.part_no",
                                 "message": f"有 {count} 条模板工序缺少对应零件，请核对。"})
