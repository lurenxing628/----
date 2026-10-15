"""Four numerical process grains from the same saved-process projection."""

from core.models.workbench_command import canonical_json
from core.services.scheduler.run.optimizer.shared_process import UNIFIED_PROCESS_VERSION
from core.services.scheduler.summary.optimizer_public_attempts import COMPARISON_METRIC_KEYS
from core.services.workbench.facts.candidate_process import PROCESS_VERSION
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.unified_process import project_unified_process

from .decision_recommendation_export import COMMON_HEADERS, _common

PROCESS_COMMON_FIELDS = ("过程版本", "查看过程候选编号", "查看过程候选名称", "求解来源候选编号", "过程来源类型", "过程来源可用", "过程证据版本", "过程证据状态",
                         "主目标", "主指标key", "主指标", "主指标单位")
_COUNT_FIELDS = (("evaluated", "评估数"), ("accepted", "接受数"), ("current_accepted", "当前解接受数"),
                 ("strict_improvements", "严格改善数"), ("rejected", "已记录拒绝数"), ("unverified_trials", "未验证数"), ("decoder_invocations", "实际排程调用数"))
_COMPLETION_FIELDS = (("expected_operation_count", "本次参与计算工序数"), ("missing_operation_count", "本次计算范围缺少工序数"),
                      ("unexpected_result_count", "本次计算范围外结果数"), ("complete_batch_count", "本次计算范围内工序排齐批次数"),
                      ("incomplete_batch_count", "本次计算范围内工序未排齐批次数"))
_METRIC_FIELDS = (("overdue_count", "保存超期批次数"), ("total_tardiness_hours", "保存总拖期（小时）"),
                  ("weighted_tardiness_hours", "保存加权拖期（小时）"), ("makespan_hours", "保存工期（小时）"), ("changeover_count", "保存算法工种切换次数"))
_PROFILE_FIELDS = (("enabled", "优化器已启用"), ("seed", "优化器随机种子"), ("configured_time_budget_seconds", "配置求解预算（秒）"),
    ("effective_time_budget_seconds", "实际求解预算（秒）"), ("assigned_time_budget_ms", "已分配求解预算（毫秒）"),
    ("configured_max_iterations", "配置迭代上限"), ("effective_max_iterations", "实际迭代上限"),
    ("system_limit_applied", "已应用系统限制"), ("system_limit_reason", "系统限制原因"), ("message", "Profile说明"),
    ("candidate_strategy_families", "候选策略族"), ("configured_neighborhoods", "配置邻域"), ("effective_neighborhoods", "实际邻域"))
_SCORE_FIELDS = tuple("评分分量" + str(index) for index in range(6))
_SCORE_UNITS = tuple("评分分量" + str(index) + "单位" for index in range(6))
_REFERENCE_SCORE_FIELDS = tuple("当时参考评分分量" + str(index) for index in range(6))
_COMPARISON_METRICS = tuple(zip(COMPARISON_METRIC_KEYS, ("失败工序数", "超期批次数", "加权拖期（小时）", "总拖期（小时）", "工期（小时）", "算法工种切换次数")))
_COMPLETION_HEADERS = tuple(label for _, label in _COMPLETION_FIELDS)
_METRIC_HEADERS = tuple(label for _, label in _METRIC_FIELDS)

CANDIDATE_FIELDS = ("record_kind", "候选顺序类型", "保存状态", "算法模式", "策略", "优化器配置类别", "优化器Profile", "接受准则", "实际派工模式", "配置派工规则", "实际采用派工规则",
                    "候选自身耗时（毫秒）", "来源求解耗时（毫秒）", "停止原因", "停止说明") + tuple(label for _, label in _PROFILE_FIELDS) + tuple("候选自身" + label for _, label in _COUNT_FIELDS) \
    + tuple("来源求解" + label for _, label in _COUNT_FIELDS) + _METRIC_HEADERS + _COMPLETION_HEADERS \
    + ("保存代表尝试数", "旧版最佳更新数（含同分）", "原进步事件数", "保留进步点数", "采样策略", "分桶数", "桶宽（毫秒）", "保留首次有效", "保留首次排齐本次参与计算工序", "保留最终", "覆盖说明", "拒绝原因key", "拒绝原因数")
PROGRESS_FIELDS = ("record_kind", "事件序号", "累计求解耗时（毫秒）", "阶段", "阶段访问序号", "连续段", "首次有效", "首次排齐本次参与计算工序", "最终结果",
                   "业务主值", "目标评价范围", "评价范围未排齐批次编号", "已验证") + _COMPLETION_HEADERS + _SCORE_FIELDS + _SCORE_UNITS
STAGE_FIELDS = ("record_kind", "阶段", "阶段状态", "阶段起点（毫秒）", "阶段终点（毫秒）", "阶段累计耗时（毫秒）", "访问数",
                "评估数", "接受数", "严格改善数", "已记录拒绝数", "停止原因")
ATTEMPT_FIELDS = ("record_kind", "保存尝试序号", "代表排名", "尝试来源", "尝试策略", "尝试派工模式", "尝试派工规则", "尝试保存状态",
                  "尝试来源key", "权重Profile", "尝试事件序号", "尝试失败工序数", "尝试累计耗时（毫秒）", "尝试已接受", "尝试已验证", "相对当时对象严格改善", "业务主值", "目标评价范围",
                  "当时比较对象", "当时比较状态", "当时比较目标", "当时本次评价范围", "当时参考评价范围") \
    + _METRIC_HEADERS + _COMPLETION_HEADERS + _SCORE_FIELDS + _SCORE_UNITS + _REFERENCE_SCORE_FIELDS \
    + tuple("当时参考" + label for _, label in _COMPARISON_METRICS) + tuple("相对当时对象变化" + label for _, label in _COMPARISON_METRICS) \
    + tuple("当时参考" + label for _, label in _COMPLETION_FIELDS)
PROCESS_HEADERS = COMMON_HEADERS + PROCESS_COMMON_FIELDS
CANDIDATE_HEADERS = PROCESS_HEADERS + CANDIDATE_FIELDS
PROGRESS_HEADERS = PROCESS_HEADERS + PROGRESS_FIELDS
STAGE_HEADERS = PROCESS_HEADERS + STAGE_FIELDS
ATTEMPT_HEADERS = PROCESS_HEADERS + ATTEMPT_FIELDS
PROCESS_CSV_HEADERS = tuple(dict.fromkeys(CANDIDATE_HEADERS + PROGRESS_HEADERS + STAGE_HEADERS + ATTEMPT_HEADERS))


def _values(raw, fields, *, prefix=""):
    return {prefix + label: raw.get(key) for key, label in fields}


def _score(row, objective):
    score = row["score"]
    units = {field["index"]: field["unit"] for field in objective["score_fields"]}
    return {**{label: score[index] if index < len(score) else None for index, label in enumerate(_SCORE_FIELDS)},
            **{label: units.get(index) for index, label in enumerate(_SCORE_UNITS)}}


def _candidate(saved):
    row, summary, progress = saved["candidate"], saved["summary"], saved["progress"]
    stop, coverage, sampling = row["stop_reason"] or {}, progress["coverage"], progress["sampling"]
    profile = saved["source"]["profile"]
    endpoints = coverage["endpoint_coverage"]
    return {"record_kind": "candidate_summary", "候选顺序类型": row["kind"], "保存状态": row["persisted_status"], "算法模式": row["algo_mode"],
        "策略": row["used_strategy"], "优化器配置类别": row["algorithm_profile"], "优化器Profile": profile.get("profile"), "接受准则": profile.get("acceptance"),
        "实际派工模式": row["dispatch_mode"], "配置派工规则": row["configured_dispatch_rule"], "实际采用派工规则": row["adopted_dispatch_rule"],
        "候选自身耗时（毫秒）": row["own_elapsed_ms"], "来源求解耗时（毫秒）": row["source_solver_elapsed_ms"], "停止原因": stop.get("code"), "停止说明": stop.get("message"),
        **{label: "；".join(profile[key]) if type(profile.get(key)) is list else profile.get(key) for key, label in _PROFILE_FIELDS},
        **_values(row["own_counts"], _COUNT_FIELDS, prefix="候选自身"), **_values(row["solver_counts"], _COUNT_FIELDS, prefix="来源求解"),
        **_values(row["final_metrics"], _METRIC_FIELDS), **_values(row["completion"], _COMPLETION_FIELDS),
        "保存代表尝试数": summary["saved_attempt_count"], "旧版最佳更新数（含同分）": summary["legacy_best_updates"], "原进步事件数": sampling["event_total_count"], "保留进步点数": sampling["retained_point_count"],
        "采样策略": sampling["policy"], "分桶数": sampling["bucket_count"], "桶宽（毫秒）": sampling["bucket_width_ms"],
        "保留首次有效": endpoints["first_valid"], "保留首次排齐本次参与计算工序": endpoints["first_expected_complete"], "保留最终": endpoints["final"],
        "覆盖说明": (coverage["reason"] or {}).get("message")}


def _point(row, objective, *, recorded):
    flags = row["flags"]
    return {"record_kind": "progress_point", "事件序号": row["event_index"], "累计求解耗时（毫秒）": row["elapsed_ms"], "阶段": row["phase"],
        "阶段访问序号": row["phase_visit"], "连续段": row["segment"], "首次有效": "first_valid" in flags if recorded else None,
        "首次排齐本次参与计算工序": "first_expected_complete" in flags if recorded else None, "最终结果": "final" in flags if recorded else None, "业务主值": row["primary_value"],
        "目标评价范围": row["objective_scope"],
        "评价范围未排齐批次编号": canonical_json(row["evaluation_scope"]["incomplete_batch_ids"]) if row["evaluation_scope"] is not None else None,
        "已验证": row["verified"], **_values(row["completion"], _COMPLETION_FIELDS), **_score(row, objective)}


def _stage(row):
    return {"record_kind": "stage", "阶段": row["phase"], "阶段状态": row["status"], "阶段起点（毫秒）": row["start_elapsed_ms"],
        "阶段终点（毫秒）": row["end_elapsed_ms"], "阶段累计耗时（毫秒）": row["elapsed_ms"], "访问数": row["visits"],
        "评估数": row["evaluated"], "接受数": row["accepted"], "严格改善数": row["strict_improvements"], "已记录拒绝数": row["rejected"], "停止原因": row["stop_reason"]}


def _attempt(row, objective):
    comparison = row["comparison"] or {}
    reference = comparison.get("reference_score") or []
    return {"record_kind": "representative_attempt", "保存尝试序号": row["saved_index"], "代表排名": row["rank"], "尝试来源": row["source_label"],
        "尝试来源key": row["candidate_origin"], "权重Profile": row["weight_profile_slug"], "尝试事件序号": row["event_index"],
        "尝试策略": row["strategy"], "尝试派工模式": row["dispatch_mode"], "尝试派工规则": row["dispatch_rule"], "尝试保存状态": row["candidate_status"],
        "尝试失败工序数": row["failed_ops"], "尝试累计耗时（毫秒）": row["elapsed_ms"], "尝试已接受": row["accepted"], "业务主值": row["primary_value"],
        "尝试已验证": row["verified"], "相对当时对象严格改善": row["strict_improved"],
        "当时比较对象": comparison.get("kind"), "当时比较状态": comparison.get("state"), "当时比较目标": comparison.get("objective_name"),
        "当时本次评价范围": comparison.get("objective_scope"), "当时参考评价范围": comparison.get("reference_scope"),
        "目标评价范围": row["objective_scope"], **_values(row["metrics"], _METRIC_FIELDS), **_values(row["completion"], _COMPLETION_FIELDS), **_score(row, objective),
        **{label: reference[index] if index < len(reference) else None for index, label in enumerate(_REFERENCE_SCORE_FIELDS)},
        **_values(comparison.get("reference_metrics") or {}, _COMPARISON_METRICS, prefix="当时参考"),
        **_values(comparison.get("metric_deltas") or {}, _COMPARISON_METRICS, prefix="相对当时对象变化"),
        **_values(comparison.get("reference_completion") or {}, _COMPLETION_FIELDS, prefix="当时参考")}


def _records(saved):
    row, objective = saved["candidate"], saved["objective"]
    common = {"过程版本": PROCESS_VERSION, "查看过程候选编号": row["candidate_ref"], "查看过程候选名称": row["label"],
        "求解来源候选编号": row["source_candidate_ref"], "过程来源类型": row["source_kind"], "过程来源可用": saved["source"]["available"],
        "过程证据版本": row["evidence_version"], "过程证据状态": row["evidence_state"],
        "主目标": objective["name"], "主指标key": objective["primary_metric_key"], "主指标": objective["primary_metric_label"], "主指标单位": objective["unit"]}
    reasons = [{**common, "record_kind": "rejection_reason", "拒绝原因key": key, "拒绝原因数": count}
               for key, count in sorted((saved["source"]["rejection_summary"] or {}).items())]
    return {"候选计算": [{**common, **_candidate(saved)}] + reasons,
            "进步事件": [{**common, **_point(point, objective, recorded=row["evidence_version"] is not None)} for point in saved["progress"]["points"]],
            "搜索阶段": [{**common, **_stage(stage)} for stage in saved["stages"]],
            "代表尝试": [{**common, **_attempt(attempt, objective)} for attempt in saved["attempts"]]}


def process_export_tables(data, snapshot):
    unified = _unified_export(data)
    if unified is not None:
        common = _common(data, snapshot)
        records = _unified_records(unified)
        return {title: (COMMON_HEADERS + fields, [common + [row.get(field) for field in fields] for row in records[title]])
                for title, fields in _UNIFIED_TABLE_FIELDS}
    common = _common(data, snapshot)
    records = [_records(saved) for saved in data["export_process"]]
    definitions = (("候选计算", CANDIDATE_FIELDS), ("进步事件", PROGRESS_FIELDS), ("搜索阶段", STAGE_FIELDS), ("代表尝试", ATTEMPT_FIELDS))
    return {title: (PROCESS_HEADERS + fields, [common + [row.get(field) for field in PROCESS_COMMON_FIELDS + fields]
            for tables in records for row in tables[title]]) for title, fields in definitions}


def process_csv(data, snapshot):
    unified = _unified_export(data)
    if unified is not None:
        common = dict(zip(COMMON_HEADERS, _common(data, snapshot)))
        records = _unified_records(unified)
        return UNIFIED_PROCESS_CSV_HEADERS, [[{**common, **row}.get(field) for field in UNIFIED_PROCESS_CSV_HEADERS]
            for rows in records.values() for row in rows]
    common = dict(zip(COMMON_HEADERS, _common(data, snapshot)))
    return PROCESS_CSV_HEADERS, [[{**common, **row}.get(field) for field in PROCESS_CSV_HEADERS]
        for saved in data["export_process"] for rows in _records(saved).values() for row in rows]


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


def _unified_export(data):
    records = data["export_process"]
    if not records or records[0].get("process_version") != UNIFIED_PROCESS_VERSION:
        return None
    if len(records) != 1:
        corrupt()
    return records[0]


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


def _unified_records(saved):
    current = saved["projected"]
    process = saved["process"]
    source_event, candidate = current["source_event"], current["candidate"]
    records = {title: [] for title, _ in _UNIFIED_TABLE_FIELDS}
    records["共同计算"].append({"record_kind": "run_process_summary", "过程版本": UNIFIED_PROCESS_VERSION,
        "共同计时来源": process["clock"], "共同总耗时（毫秒）": current["summary"]["elapsed_ms"],
        "首次完整解（毫秒）": current["summary"]["first_complete_elapsed_ms"], "停止原因": current["stop_reason"],
        "主目标": process["primary_objective"], "目标方向目录": canonical_json(process["target_objectives"]),
        "查看过程候选编号": candidate["candidate_ref"] if candidate is not None else None,
        "查看过程候选名称": candidate["label"] if candidate is not None else None,
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
