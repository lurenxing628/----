"""Export tables from the same projection of one run's saved shared process."""

from core.services.scheduler.run.optimizer.shared_process import UNIFIED_PROCESS_VERSION
from core.services.workbench.facts.unified_process import project_unified_process
from core.shared.strict_json import canonical_json

from .decision_recommendation_export import COMMON_HEADERS, common_export_columns

_SCORE_FIELDS = tuple("评分分量" + str(index) for index in range(6))
_SCORE_UNITS = tuple("评分分量" + str(index) + "单位" for index in range(6))


def _values(raw, fields, *, prefix=""):
    return {prefix + label: raw.get(key) for key, label in fields}


def process_export_tables(data, snapshot):
    common = common_export_columns(data, snapshot)
    records = _unified_records(data["export_process"])
    return {title: (COMMON_HEADERS + fields, [common + [row.get(field) for field in fields] for row in records[title]])
            for title, fields in _UNIFIED_TABLE_FIELDS}


def process_csv(data, snapshot):
    common = dict(zip(COMMON_HEADERS, common_export_columns(data, snapshot)))
    records = _unified_records(data["export_process"])
    return UNIFIED_PROCESS_CSV_HEADERS, [[{**common, **row}.get(field) for field in UNIFIED_PROCESS_CSV_HEADERS]
        for rows in records.values() for row in rows]


_UNIFIED_DIRECTION_FIELDS = ("优化方向", "优化方向名称", "主指标key", "主指标", "主指标单位")
_UNIFIED_COUNT_FIELDS = (("actual_decoder_calls", "共同实际排程调用数"), ("new_decisions", "共同新增决策数"),
    ("decision_reuses", "共同决策复用数"), ("skipped_requests", "共同跳过执行次数"),
    ("failed_decoder_calls", "共同排程失败数"), ("request_count", "共同不同决策请求数"))
_UNIFIED_GOAL_FIELDS = (("objective_status", "方向状态"), ("weight", "方向预算权重"),
    ("elapsed_seconds", "方向实际耗时（秒）"), ("charged_seconds", "方向计入预算耗时（秒）"),
    ("preparation_seconds", "方向准备耗时（秒）"), ("action_count", "方向动作数"),
    ("new_decisions", "方向新增决策数"), ("reused_decisions", "方向复用决策数"),
    ("probe_decisions", "方向探测决策数"), ("minimum_opportunity", "方向已取得最小机会"),
    ("improvement_action_count", "方向改善动作数"), ("has_gain", "方向已有改善"),
    ("feedback_rate", "方向改善反馈率"), ("feedback_bonus", "方向预算反馈增量"),
    ("unavailable_reason", "方向无机会原因"), ("budget_reason", "方向预算原因"))
_UNIFIED_ACTION_FIELDS = (("action_id", "动作编号"), ("phase", "阶段"), ("initial_construction", "共同首次构造"),
    ("started_elapsed_ms", "动作起点（毫秒）"), ("finished_elapsed_ms", "动作终点（毫秒）"),
    ("elapsed_ms", "动作实际耗时（毫秒）"), ("evaluation_count", "动作评估数"),
    ("verified_evaluation_count", "动作已验证评估数"), ("new_decisions", "动作新增决策数"),
    ("reused_decisions", "动作复用决策数"), ("skip_reason", "动作跳过原因"))
_UNIFIED_STAGE_FIELDS = (("phase", "阶段"), ("start_elapsed_ms", "阶段动作起点（毫秒）"),
    ("end_elapsed_ms", "阶段动作终点（毫秒）"), ("elapsed_ms", "阶段预算累计耗时（毫秒）"),
    ("action_count", "阶段动作数"), ("evaluation_count", "阶段评估数"),
    ("verified_evaluation_count", "阶段已验证评估数"), ("new_decisions", "阶段新增决策数"),
    ("reused_decisions", "阶段复用决策数"))
_UNIFIED_BRIDGE_FIELDS = (("search_objective", "实际搜索方向"), ("phase", "阶段"),
    ("before_entry_id", "桥接前条目编号"), ("after_entry_id", "桥接后条目编号"),
    ("source_event_id", "来源事件编号"), ("started_elapsed_ms", "桥接起点（毫秒）"),
    ("finished_elapsed_ms", "桥接终点（毫秒）"), ("elapsed_ms", "桥接实际耗时（毫秒）"),
    ("same_arrangement", "桥接安排相同"), ("decoder_executed", "桥接实际调用排程"), ("reference_kind", "桥接来源类型"))
_UNIFIED_SCORE_KEYS = tuple("评分分量" + str(index) + "指标key" for index in range(6))
_UNIFIED_TABLE_FIELDS = (
    ("共同计算", ("record_kind", "过程版本", "共同计时来源", "共同总耗时（毫秒）", "首次完整解（毫秒）", "停止原因", "主目标",
        "目标方向目录", "查看过程候选编号", "查看过程候选名称", "查看过程来源事件编号", "共同候选来源目录", "共同执行类型计数", "共同预算")
        + tuple(label for _, label in _UNIFIED_COUNT_FIELDS)),
    ("目标预算", ("record_kind",) + _UNIFIED_DIRECTION_FIELDS + tuple(label for _, label in _UNIFIED_GOAL_FIELDS)
        + ("首次真实评分改善（毫秒）", "最后真实评分改善（毫秒）", "进步采样记录")),
    ("进步事件", ("record_kind",) + _UNIFIED_DIRECTION_FIELDS + ("累计共同耗时（毫秒）", "档案条目编号", "来源事件编号", "实际搜索方向", "实际来源",
        "阶段", "已验证", "评价范围编号", "连续段", "进步标记", "业务主值") + _SCORE_FIELDS + _SCORE_UNITS + _UNIFIED_SCORE_KEYS),
    ("搜索动作", ("record_kind",) + _UNIFIED_DIRECTION_FIELDS + tuple(label for _, label in _UNIFIED_ACTION_FIELDS) + ("动作改善方向",)),
    ("搜索阶段", ("record_kind",) + _UNIFIED_DIRECTION_FIELDS + tuple(label for _, label in _UNIFIED_STAGE_FIELDS)),
    ("评价范围", ("record_kind", "评价范围编号", "目标评价范围", "评分分量已知", "本次工序已排齐", "已排工序成员数", "排齐批次成员数")),
    ("范围成员", ("record_kind", "评价范围编号", "成员类型", "成员顺序", "成员永久编号")),
    ("真实桥接", ("record_kind",) + tuple(label for _, label in _UNIFIED_BRIDGE_FIELDS)),
)
UNIFIED_PROCESS_CSV_HEADERS = COMMON_HEADERS + tuple(dict.fromkeys(field for _, fields in _UNIFIED_TABLE_FIELDS for field in fields))


def _direction(objective):
    return {"优化方向": objective["name"], "优化方向名称": objective["label"], "主指标key": objective["primary_metric_key"],
            "主指标": objective["primary_metric_label"], "主指标单位": objective["unit"]}


def _unified_point(point, objective):
    fields = {field["key"]: field for field in objective["score_fields"]}
    return {"record_kind": "progress_point", **_direction(objective), "累计共同耗时（毫秒）": point["elapsed_ms"],
        "档案条目编号": point["entry_id"], "来源事件编号": point["source_event_id"], "实际搜索方向": point["search_objective"],
        "实际来源": point["origin"], "阶段": point["phase"], "已验证": point["verified"], "评价范围编号": point["scope_ref"],
        "连续段": point["segment"], "进步标记": canonical_json(point["flags"]), "业务主值": point["primary_value"],
        **{label: point["score"][index] if index < len(point["score"]) else None for index, label in enumerate(_SCORE_FIELDS)},
        **{label: point["field_order"][index] if index < len(point["field_order"]) else None for index, label in enumerate(_UNIFIED_SCORE_KEYS)},
        **{label: fields[point["field_order"][index]]["unit"] if index < len(point["field_order"]) else None
           for index, label in enumerate(_SCORE_UNITS)}}


def _unified_records(exports):
    """A run exports exactly its one saved shared process."""
    (saved,) = exports
    records = {title: [] for title, _ in _UNIFIED_TABLE_FIELDS}
    current = saved["projected"]
    process = saved["process"]
    source_event, candidate = current["source_event"], current["candidate"]
    records["共同计算"].append({"record_kind": "run_process_summary", "过程版本": UNIFIED_PROCESS_VERSION,
        "共同计时来源": process["clock"], "共同总耗时（毫秒）": current["summary"]["elapsed_ms"],
        "首次完整解（毫秒）": current["summary"]["first_complete_elapsed_ms"], "停止原因": current["stop_reason"],
        "主目标": process["primary_objective"], "目标方向目录": canonical_json(process["target_objectives"]),
        "查看过程候选编号": candidate["candidate_ref"],
        "查看过程候选名称": candidate["label"],
        "查看过程来源事件编号": source_event["event_id"] if source_event is not None else None,
        "共同候选来源目录": canonical_json(current["candidates"]), "共同执行类型计数": canonical_json(current["counts"]["execution_counts"]),
        "共同预算": canonical_json({key: value for key, value in current["budget"].items() if key not in ("objectives", "objective_status")}),
        **_values(current["counts"], _UNIFIED_COUNT_FIELDS)})
    for name in saved["export_objectives"]:
        projected = current if name == current["selected_objective"]["name"] else project_unified_process(
            process, objective=name, candidate=candidate, candidates=current["candidates"])
        objective = projected["selected_objective"]
        direction = _direction(objective)
        records["目标预算"].append({"record_kind": "objective_budget", **direction,
            **_values(projected["budget"]["objectives"][name], _UNIFIED_GOAL_FIELDS),
            "首次真实评分改善（毫秒）": projected["summary"]["first_improvement_elapsed_ms"],
            "最后真实评分改善（毫秒）": projected["summary"]["last_improvement_elapsed_ms"],
            "进步采样记录": canonical_json(projected["progress"]["sampling"])})
        records["进步事件"].extend(_unified_point(point, objective) for point in projected["progress"]["points"])
        records["搜索动作"].extend({"record_kind": "search_action", **direction, **_values(action, _UNIFIED_ACTION_FIELDS),
            "动作改善方向": canonical_json(action["improved_objectives"])} for action in projected["actions"])
        records["搜索阶段"].extend({"record_kind": "stage", **direction, **_values(stage, _UNIFIED_STAGE_FIELDS)} for stage in projected["stages"])
    for scope_ref, scope in current["scopes"].items():
        records["评价范围"].append({"record_kind": "score_scope", "评价范围编号": scope_ref,
            "目标评价范围": scope["objective_scope"], "评分分量已知": scope["components_known"], "本次工序已排齐": scope["is_complete"],
            "已排工序成员数": len(scope["scheduled_operation_refs"]), "排齐批次成员数": len(scope["complete_batch_refs"])})
        for kind, members in (("scheduled_operation", scope["scheduled_operation_refs"]), ("complete_batch", scope["complete_batch_refs"])):
            records["范围成员"].extend({"record_kind": "scope_member", "评价范围编号": scope_ref, "成员类型": kind,
                "成员顺序": index, "成员永久编号": member} for index, member in enumerate(members, 1))
    records["真实桥接"].extend({"record_kind": "bridge", **_values(bridge, _UNIFIED_BRIDGE_FIELDS)} for bridge in current["bridges"])
    return records
