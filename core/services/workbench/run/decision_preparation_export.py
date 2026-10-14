"""Flat offline tables for saved requirements and exact type transition events."""

import json

EFFORT_FIELDS = (
    ("来源", "source"), ("需求数量依据", "quantity_basis"), ("需求目标量", "target_quantity"),
    ("执行数量依据", "execution_quantity_basis"), ("执行目标量", "execution_target_quantity"), ("执行剩余量", "remaining_quantity"),
    ("准备标准工时", "setup_standard_hours"), ("加工标准工时", "processing_standard_hours"), ("所需标准工时", "required_standard_hours"),
    ("准备状态", "setup_state"), ("安排类型", "requirement_role"), ("工序安排状态", "allocation_state"),
    ("外协周期天", "external_cycle_days"), ("外协组编号", "external_group_id"), ("外协合并模式", "external_merge_mode"),
    ("工时计算方式", "effort_basis"), ("工时资料状态", "state"),
    ("需求来源类型", "evidence_source.kind"), ("需求来源排产编号", "evidence_source.run_ref"),
    ("需求来源候选编号", "evidence_source.candidate_ref"), ("需求来源试调编号", "evidence_source.scenario_ref"),
    ("需求来源计划编号", "evidence_source.plan_ref"), ("需求来源正式版本", "evidence_source.version"),
    ("归档标准准备工时", "standard.setup_standard_hours"), ("归档标准单件工时", "standard.unit_standard_hours"),
    ("归档标准目标量", "standard.target_quantity"), ("归档标准总工时", "standard.standard_total_hours"),
    ("归档标准状态", "standard.state"), ("归档标准缺项", "standard.reason"), ("需求分解缺项", "data_gaps"),
)
RUNTIME_OPERATION_HEADERS = tuple(side + "所需工时：" + label for side in ("基准", "所选") for label, _field in EFFORT_FIELDS)
PREPARATION_HEADERS = (
    "排产编号", "查看基准永久编号", "所选方案编号", "批次永久编号", "批次编号", "工序永久编号", "零件名称", "工序号", "工序名称", "单件编号",
) + tuple(side + label for side in ("基准", "所选") for label, _field in EFFORT_FIELDS) + (
    "基准设备编号", "基准设备", "所选设备编号", "所选设备", "基准安排记录", "所选安排记录",
    "准备工时变化", "准备工时变化状态", "准备工时变化方向", "加工工时变化", "加工工时变化状态", "加工工时变化方向",
    "所需标准工时变化", "所需标准工时变化状态", "所需标准工时变化方向", "缺少资料",
)
CHANGEOVER_HEADERS = (
    "排产编号", "查看基准永久编号", "所选方案编号", "事件编号", "事件侧", "设备永久编号", "设备名称", "设备序列位置",
    "前序工序永久编号", "前序安排永久编号", "前序批次永久编号", "前序批次编号", "前序工序名称", "前序工种永久编号", "前序工种名称", "前序开始", "前序结束",
    "后序工序永久编号", "后序安排永久编号", "后序批次永久编号", "后序批次编号", "后序工序名称", "后序工种永久编号", "后序工种名称", "后序开始", "后序结束",
    "前序位于窗口之前", "前后安排重叠", "设备安排冲突", "事件状态", "事件缺项", "计算方式", "事件指标版本",
)


def _path(value, field):
    for part in field.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _issues(value):
    if isinstance(value, dict):
        return value.get("message") or value.get("code")
    return "；".join(str(item.get("message") or item.get("code")) if isinstance(item, dict) else str(item) for item in value or ()) or None


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) if value else None


def effort_values(value):
    return [_issues(_path(value, field)) if field in ("data_gaps", "standard.reason") else _path(value, field) for _label, field in EFFORT_FIELDS]


def runtime_operation_values(row):
    return effort_values(row["runtime_effort"]["before"]) + effort_values(row["runtime_effort"]["after"])


def _baseline_ref(baseline):
    return baseline.get("candidate_ref") if baseline["kind"] == "candidate" else baseline.get("baseline_ref")


def preparation_rows(data):
    common = [data["run_ref"], _baseline_ref(data["baseline"]), data["candidate"]["candidate_ref"]]
    for row in data["items"]:
        before, after = row["before"], row["after"]
        yield common + [row[field] for field in ("batch_ref", "batch_label", "operation_ref", "part_label", "sequence", "process_label", "piece_id")] + (
            effort_values(before) + effort_values(after)
            + ["、".join(machine[field] or "" for machine in side["machines"]) or None for side in (before, after) for field in ("ref", "label")]
            + [_json(side["arrangements"]) for side in (before, after)]
            + [row["deltas"][field][name] for field in ("setup_standard_hours", "processing_standard_hours", "required_standard_hours") for name in ("value", "state", "direction")]
            + [_issues(row["data_gaps"])])


def _boolean(value):
    return None if value is None else "是" if value else "否"


def changeover_rows(data):
    common = [data["run_ref"], _baseline_ref(data["baseline"]), data["candidate"]["candidate_ref"]]
    for row in data["items"]:
        identities = []
        for prefix in ("previous", "next"):
            item = row[prefix]
            identities += [row[prefix + "_operation_ref"], row[prefix + "_row_ref"], item["batch_ref"], item["batch_label"], item["process_label"],
                           item["type_ref"], item["type_label"], row[prefix + "_start"], row[prefix + "_end"]]
        yield common + [row[field] for field in ("event_ref", "event_side", "machine_ref", "machine_label", "sequence")] + identities + [
            _boolean(row["predecessor_outside_window"]), _boolean(row["overlap"]), _boolean(row["conflict"]), row["state"], _issues(row["data_gaps"]),
            "同一设备上相邻两道工序的工种不同，后一道工序开始时间在所选范围内（含开始、不含结束）", "type_changeover_v1"]
