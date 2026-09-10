"""Route checks retain the current workflow's zero/unknown and merged-group rules."""

from collections import defaultdict

from .master_overview_graph import number, text


def add_process(graph):
    facts = graph.facts
    grouped = defaultdict(list)
    for row in facts.rows("PartOperations"):
        grouped[row["part_no"]].append(row)
    for row in facts.rows("Parts"):
        key = row["part_no"]
        part = graph.add("part", key, key, row["part_name"])
        for column, label in (("part_no", "图号"), ("part_name", "名称")):
            graph.field(part, label, row[column], "Parts." + column)
            if not isinstance(row[column], str) or not row[column].strip():
                graph.issue(part, column + ".missing", "零件基本信息不完整", label + "未填写。")
        graph.field(part, "备注", row.get("remark"), "Parts.remark", required=False)
        if not facts.available("PartOperations", "ExternalGroups"):
            graph.unknown(part, "工艺路线", "PartOperations / ExternalGroups", relation=True)
            continue
        operations = grouped[key]
        active = [op for op in operations if op["status"] == "active"]
        graph.field(part, "有效模板工序数", len(active), "PartOperations.status=active")
        if not active:
            graph.issue(part, "part.route_missing", "零件无有效模板工序", "有效工序为0；未把原始路线文字当成已确认模板。", stage="route", action="录入或核对路线")
        if operations or isinstance(row["route_raw"], str) and row["route_raw"].strip():
            route = graph.add("route", key, key, (row["part_name"] or key) + " · 工艺路线")
            graph.link(part, route, "工艺路线", "Parts -> PartOperations", "所属零件")
            _route(graph, route, row, operations)
    _orphan_operations(graph, grouped)


def _route(graph, route, row, operations):
    graph.field(route, "原始路线", row["route_raw"], "Parts.route_raw", required=False)
    graph.field(route, "路线解析标记", row["route_parsed"], "Parts.route_parsed")
    active = [op for op in operations if op["status"] == "active"]
    graph.field(route, "有效工序数", len(active), "PartOperations.status=active")
    graph.field(route, "保留历史工序数", len(operations) - len(active), "PartOperations.status", required=False)
    if (row["route_parsed"] == "yes") != bool(active):
        graph.issue(route, "route.state_mismatch", "路线标记与有效工序不一致", "解析标记：" + text(row["route_parsed"]) + "；有效工序：" + str(len(active)), stage="route")
    state = graph.facts.workflow.get(row["part_no"]) if graph.facts.workflow is not None else None
    _workflow_confirmation(graph, route, state)
    groups = graph.facts.index("ExternalGroups", "group_id")
    seen = set()
    for op in operations:
        op_ref = graph.facts.ref("template_operation", op["id"])
        if op["status"] not in ("active", "deleted"):
            graph.issue(route, "operation.status", "工序状态不明确", "原状态：" + text(op["status"]), stage="route", operation_ref=op_ref)
        if op["status"] != "active":
            continue
        if op["seq"] in seen or type(op["seq"]) is not int or op["seq"] <= 0:
            graph.issue(route, "operation.sequence", "工序号重复或无效", "工序号：" + text(op["seq"]), stage="route", operation_ref=op_ref)
        seen.add(op["seq"])
        _operation(graph, route, op, op_ref, groups, state)


def _workflow_confirmation(graph, route, state):
    if state is None:
        graph.unknown(route, "路线、归属与工时确认", "process.workflow_snapshot")
        return
    workflow = state["workflow"]
    labels = {"route": "路线", "source": "归属", "hours": "工时"}
    for stage, label in labels.items():
        confirmed = workflow[stage]["state"] == "confirmed"
        graph.field(route, label + "确认", "已确认" if confirmed else "存量未确认" if workflow["origin"] == "legacy" else "未确认",
                    "process.workflow_snapshot." + stage, valid=confirmed)
    if not workflow["ready"]:
        graph.issue(route, "workflow.pending", "工艺确认尚未完成", "当前待处理阶段：" + labels[workflow["stage"]] + "；现存归属与0工时不构成人工确认。",
                    stage="route" if workflow["origin"] == "legacy" else workflow["stage"], action="核对并确认工艺阶段")


def _operation(graph, route, op, ref, groups, state):
    prefix = "工序 " + text(op["seq"]) + " " + text(op["op_type_name"])
    source = op["source"]
    def issue(rule, title, evidence, stage="source"):
        graph.issue(route, rule, title, prefix + "；" + evidence, stage=stage, operation_ref=ref)
    graph.field(route, prefix + "归属", {"internal": "自制", "external": "外协"}.get(source, source),
                "PartOperations.source", valid=source in ("internal", "external"))
    if source not in ("internal", "external"):
        issue("operation.source", "工序归属未明确", "原归属：" + text(source))
    target = graph.related(route, "opType", op["op_type_id"], "工序使用工种", "PartOperations.op_type_id", "引用路线", required=True, operation_ref=ref, stage="source")
    if target and graph.facts.index("OpTypes", "op_type_id")[op["op_type_id"]]["category"] != source:
        issue("operation.category", "工序归属与工种类别不一致", "绑定工种：" + target["business_code"])
    if source == "internal":
        for key, label in (("setup_hours", "换型工时"), ("unit_hours", "单件工时")):
            value = op[key]
            graph.field(route, prefix + label + "（h）", value, "PartOperations." + key, valid=number(value))
            if not number(value):
                issue("operation." + key, label + ("未填写" if value is None else "数值异常"), label + "：" + text(value) + "；允许有限非负数与0。", "hours")
        confirmation = state["operations"].get(ref) if state else None
        if op["unit_hours"] == 0 and (not confirmation or confirmation["hours"]["state"] != "confirmed"):
            issue("operation.zero_review", "单件工时0待复核", "原值0保留；尚无当前内容的人工工时确认。", "hours")
        if op["supplier_id"] is not None or op["ext_group_id"] is not None:
            issue("operation.internal_external", "自制工序保留外协绑定", "自制工序仍绑定供应商或外协组；未清空原数据。")
    if source == "external":
        _external(graph, route, op, ref, groups, prefix, issue)


def _external(graph, route, op, ref, groups, prefix, issue):
    _external_supplier(graph, route, op, ref, issue)
    group = _external_group(graph, route, op, ref, groups, prefix, issue)
    merged = group and group["merge_mode"] == "merged"
    value = group["total_days"] if group is not None and merged else op["ext_days"]
    label = "整组周期" if merged else "逐序周期"
    graph.field(route, prefix + label + "（天）", value, "ExternalGroups.total_days" if merged else "PartOperations.ext_days", valid=number(value, True))
    if not number(value, True):
        issue("operation.days", "外协周期待维护", label + "：" + text(value) + "；未默认补1天。", "hours")
    if merged and op["ext_days"] is not None and not number(op["ext_days"], True):
        issue("operation.retained_days", "合并组保留的逐序周期无效", "逐序周期：" + text(op["ext_days"]), "hours")


def _external_supplier(graph, route, op, ref, issue):
    supplier = graph.related(route, "supplier", op["supplier_id"], "工序供应商", "PartOperations.supplier_id", "引用路线", required=True, operation_ref=ref, stage="source")
    suppliers = graph.facts.index("Suppliers", "supplier_id")
    if supplier:
        raw = suppliers[op["supplier_id"]]
        capabilities = {row["op_type_id"] for row in graph.facts.grouped("WorkbenchSupplierOpTypes", "supplier_id").get(op["supplier_id"], [])} | {raw["op_type_id"]}
        if raw["status"] != "active" or op["op_type_id"] not in capabilities:
            issue("operation.supplier", "工序供应商状态或能力待核对", "供应商：" + supplier["business_code"])


def _external_group(graph, route, op, ref, groups, prefix, issue):
    group = groups.get(op["ext_group_id"])
    if op["ext_group_id"] is not None and (group is None or group["part_no"] != op["part_no"]):
        issue("operation.group", "外协组缺失或不属于本零件", "未使用同号工序或其他零件的外协组。")
        group = None
    if group:
        group_ref = graph.facts.ref("template_external_group", group["group_id"])
        graph.field(route, prefix + "外协组策略", group["merge_mode"], "ExternalGroups.merge_mode")
        graph.related(route, "supplier", group["supplier_id"], "外协组供应商", "ExternalGroups.supplier_id", "引用路线")
        valid_range = (type(group["start_seq"]) is int and type(group["end_seq"]) is int and
                       0 < group["start_seq"] <= group["end_seq"] and type(op["seq"]) is int and group["start_seq"] <= op["seq"] <= group["end_seq"])
        if not valid_range or group["merge_mode"] not in ("merged", "separate"):
            graph.issue(route, "group.invalid", "外协组范围或策略无效", prefix + "；原组规则待核对。", stage="source", operation_ref=ref, group_ref=group_ref)
    return group


def _orphan_operations(graph, grouped):
    parts = graph.facts.index("Parts", "part_no")
    count = sum(len(rows) for key, rows in grouped.items() if key not in parts)
    if count:
        graph.facts.gaps.append({"code": "orphan_operations", "source": "PartOperations.part_no", "message": f"有{count}条模板工序的所属零件缺失，未伪造所属实体。"})
