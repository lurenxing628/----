"""Four numerical process grains from the same saved-process projection."""

from core.models.workbench_command import canonical_json
from core.services.scheduler.summary.optimizer_public_attempts import COMPARISON_METRIC_KEYS
from core.services.workbench.facts.candidate_process import PROCESS_VERSION

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
    common = _common(data, snapshot)
    records = [_records(saved) for saved in data["export_process"]]
    definitions = (("候选计算", CANDIDATE_FIELDS), ("进步事件", PROGRESS_FIELDS), ("搜索阶段", STAGE_FIELDS), ("代表尝试", ATTEMPT_FIELDS))
    return {title: (PROCESS_HEADERS + fields, [common + [row.get(field) for field in PROCESS_COMMON_FIELDS + fields]
            for tables in records for row in tables[title]]) for title, fields in definitions}


def process_csv(data, snapshot):
    common = dict(zip(COMMON_HEADERS, _common(data, snapshot)))
    return PROCESS_CSV_HEADERS, [[{**common, **row}.get(field) for field in PROCESS_CSV_HEADERS]
        for saved in data["export_process"] for rows in _records(saved).values() for row in rows]
