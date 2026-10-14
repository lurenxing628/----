"""Three inspectable flat tables from the same recommendation and source facts."""

from .decision_preparation_export import EFFORT_FIELDS, effort_values

COMMON_HEADERS = ("排产编号", "归档编号", "读取编号", "读取时间", "保存推荐候选编号", "当前查看候选编号", "比较模式",
                  "查看基准编号", "查看基准类型", "范围起点（含）", "范围终点（不含）", "资源视角", "推荐版本", "推荐记录格式版本")
EXPLANATION_FIELDS = ("record_kind", "指标标识", "名称", "范围", "来源", "状态", "变化方向", "单位", "基准值", "比较对象值", "差值",
                      "实际限制", "容差", "容差单位", "主项类别", "主项顺序", "相关明细类型", "相关明细永久编号", "相关明细候选编号", "相关明细页签",
                      "相关明细比较起点", "相关明细比较终点", "相关明细筛选字段", "相关明细筛选值", "说明", "指标版本")
COMPLETION_FIELDS = ("record_kind", "安排组号", "安排来源类型", "候选永久编号", "候选名称", "来源可用", "批次永久编号", "批次编号",
                     "安排分类", "双方工序都已排齐", "批次工序安排状态", "交付状态", "交期状态", "交期", "预计完工", "已排部分预计结束", "拖期小时",
                     "工序总数", "已排工序数", "其他未安排工序数", "缺料未安排工序数", "安排缺少资料")
REMAINING_FIELDS = ("record_kind", "安排组号", "安排来源类型", "候选永久编号", "候选名称", "来源可用", "批次永久编号", "批次编号",
                    "工序永久编号", "零件名称", "工序号", "工序名称", "单件编号", "排产时安排状态", "排产时说明") + tuple(label for label, _ in EFFORT_FIELDS)
RECOMMENDATION_HEADERS = COMMON_HEADERS + EXPLANATION_FIELDS
COMPLETION_HEADERS = COMMON_HEADERS + COMPLETION_FIELDS
REMAINING_HEADERS = COMMON_HEADERS + REMAINING_FIELDS
RECOMMENDATION_CSV_HEADERS = tuple(dict.fromkeys(RECOMMENDATION_HEADERS + COMPLETION_HEADERS + REMAINING_HEADERS))


def _message(value):
    return "；".join(str(row.get("message") or row.get("code")) if isinstance(row, dict) else str(row) for row in value or ()) or None


def _scalars(value, path):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _scalars(item, path + "." + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _scalars(item, path + "[" + str(index) + "]")
    else:
        yield path, value


def _definition_values(entry):
    factor = 100 if entry.get("unit") == "%" else 1
    return {"指标标识": entry.get("metric_key") or entry.get("key"), "名称": entry["label"], "范围": entry["scope"],
            "来源": entry["source"], "指标版本": entry.get("metric_version"), "状态": entry["state"], "变化方向": entry.get("direction"), "单位": entry.get("unit"),
            **{label: entry[key] * factor if type(entry.get(key)) in (int, float) else entry.get(key)
               for label, key in (("基准值", "reference_value"), ("比较对象值", "selected_value"), ("差值", "value"))},
            "实际限制": entry.get("limit"), "容差": (entry["tolerance"] * 100 if entry.get("tolerance_unit") == "%" and entry.get("tolerance") is not None else entry.get("tolerance")),
            "容差单位": entry.get("tolerance_unit"), "说明": entry["text"]}


def _explanations(data):
    recommendation, basis = data["recommendation"], data["selection_basis"]
    yield {"record_kind": "conclusion", "指标标识": "recommendation_type", "名称": "推荐结论", "范围": "full_admission",
           "状态": recommendation["state"], "比较对象值": recommendation["recommendation_type"], "说明": recommendation["headline"]}
    for field in ("selected_candidate_ref", "raw_score_best_candidate_ref", "health_reference_candidate_ref", "selection_policy",
                  "selection_policy_version", "reason_code", "objective_name", "objective_field_order", "selected_score",
                  "overdue_tolerance_count", "tardiness_tolerance_ratio"):
        for key, value in _scalars(basis[field], field):
            yield {"record_kind": "fixed_selection", "指标标识": key, "名称": field, "范围": "fixed_algorithm_selection",
                   "来源": "saved_selection", "状态": "complete" if value is not None else "unavailable", "比较对象值": value}
    for entry in basis["explanation"]["entries"]:
        yield {"record_kind": "selection_explanation", **_definition_values(entry)}
    for issue in basis["explanation"]["issues"]:
        yield {"record_kind": "missing_evidence", "指标标识": issue["code"], "名称": "推荐依据缺少资料", "状态": "unavailable", "说明": issue["message"]}
    for root, value in (("selection", basis["decision_evidence"]), ("health", basis["health_decision_evidence"])):
        if value is None:
            continue
        for key, scalar in _scalars(value, root):
            kind = "health" if root == "health" else "tiebreak" if ".tiebreak." in key else "tolerance" if ".balanced_checks." in key else "selection_evidence"
            yield {"record_kind": kind, "指标标识": key, "名称": key, "范围": "fixed_health_reference" if root == "health" else "fixed_algorithm_selection",
                   "来源": "saved_health_calculation" if root == "health" else "saved_selection",
                   "状态": "complete" if scalar is not None else "unavailable", "比较对象值": scalar}
    main = {row["metric_key"]: (kind, index + 1) for kind in ("benefits", "costs")
            for index, row in enumerate(recommendation["current_comparison"][kind])}
    for entry in recommendation["current_comparison"]["all_differences"]:
        category, order = main.get(entry["metric_key"], (None, None))
        yield {"record_kind": "difference", **_definition_values(entry), "主项类别": category, "主项顺序": order}
        for support in entry["supporting_refs"]:
            drill = support["drill"]
            record = {"record_kind": "support", "指标标识": entry["metric_key"], "名称": entry["label"],
                      "范围": entry["scope"], "来源": entry["source"], "指标版本": entry["metric_version"], "相关明细类型": support["kind"], "相关明细永久编号": support["ref"],
                      "相关明细候选编号": drill["candidate_ref"], "相关明细页签": drill.get("comparison_tab", "gantt"),
                      "相关明细比较起点": drill["range_start"], "相关明细比较终点": drill["range_end"]}
            query = {"side": support.get("side", "selected"), **(drill.get("detail_query") or {key: drill[key] for key in (
                "batch_ref", "operation_ref", "selected_row_ref", "resource_ref", "resource_kind", "reference_view", "plan_ref") if key in drill})}
            if not query:
                yield record
            for key, value in query.items():
                yield {**record, "相关明细筛选字段": key, "相关明细筛选值": value}


def recommendation_export_records(source, data):
    """Retain full exact sets here; the public overview carries only bounded samples."""
    explanation = list(_explanations(data))
    groups = source.completion.groups(data["candidates"])
    by_candidate = {ref: index + 1 for index, group in enumerate(groups) for ref in group["candidate_refs"]}
    fixed = data["recommendation"]["candidate_ref"]
    common = set(source.completion.common(fixed)["common_completed_batch_refs"]) if fixed else set()
    contexts = [(row["candidate_ref"], row["label"], "candidate") for row in data["candidates"]]
    if source.comparison_mode == "admission_official":
        contexts.append(("reference", source.baseline.get("label"), "admission_official"))
    completion, remaining = [], []
    for key, label, kind in contexts:
        scope = source.completion.scope(key)
        identity = {"安排组号": by_candidate.get(key), "安排来源类型": kind, "候选永久编号": key if key != "reference" else None,
                    "候选名称": label, "来源可用": scope["source_available"]}
        for row in source.completion.delivery(key):
            ref = row["batch_ref"]
            category = ("complete" if ref in scope["complete_batch_refs"] else "deferred" if ref in scope["deferred_batch_refs"] else
                        "incomplete" if ref in scope["ordinary_incomplete_batch_refs"] else "unknown")
            completion.append({"record_kind": "completion_set", **identity, "批次永久编号": ref, "批次编号": row["batch_id"],
                "安排分类": category, "双方工序都已排齐": ref in common and category == "complete", "批次工序安排状态": row["completion_state"],
                "交付状态": row["risk"], "交期状态": row["due_state"], "交期": row["due_date"], "预计完工": row["planned_finish"],
                "已排部分预计结束": row["partial_planned_finish"], "拖期小时": row["delay_hours"], "工序总数": row["operation_count"],
                "已排工序数": row["scheduled_operation_count"], "其他未安排工序数": row["ordinary_unscheduled_operation_count"],
                "缺料未安排工序数": row["deferred_operation_count"], "安排缺少资料": _message(row["issues"])})
        for batch in scope["remaining_batches"]:
            for row in batch["operations"]:
                record = {"record_kind": "remaining_work", **identity, "批次永久编号": row["batch_ref"], "批次编号": row["batch_label"],
                          "工序永久编号": row["operation_ref"], "零件名称": row["part_label"], "工序号": row["sequence"],
                          "工序名称": row["process_label"], "单件编号": row["piece_id"], "排产时安排状态": row["disposition_status"],
                          "排产时说明": _message(row["reasons"])}
                record.update({field: value for (field, _path), value in zip(EFFORT_FIELDS, effort_values(row))})
                remaining.append(record)
        if not scope["source_available"]:
            remaining.append({"record_kind": "remaining_unavailable", **identity, "排产时说明": "这份方案未保存完整安排，无法确认未安排工序及其所需工时。"})
    return {"推荐说明": explanation, "工序安排": completion, "剩余需求": remaining}


def _common(data, snapshot):
    scope, baseline, basis = data["scope"], data["baseline"], data["selection_basis"]
    return [data["run"]["run_ref"], data["capture_ref"], snapshot["snapshot_ref"], snapshot["as_of"],
            data["recommendation"]["candidate_ref"], scope["selected_candidate_ref"], scope["comparison_mode"],
            baseline.get("candidate_ref") if baseline["kind"] == "candidate" else baseline.get("baseline_ref"), baseline["kind"],
            scope["range_start"], scope["range_end"], scope["resource_view"], data["recommendation"]["recommendation_version"],
            basis["selection_evidence_version"]]


def recommendation_export_tables(data, snapshot):
    common = _common(data, snapshot)
    definitions = (("推荐说明", EXPLANATION_FIELDS), ("工序安排", COMPLETION_FIELDS), ("剩余需求", REMAINING_FIELDS))
    return {title: (COMMON_HEADERS + fields, [common + [row.get(field) for field in fields] for row in data["export_recommendation"][title]])
            for title, fields in definitions}


def recommendation_csv(data, snapshot):
    common = dict(zip(COMMON_HEADERS, _common(data, snapshot)))
    return RECOMMENDATION_CSV_HEADERS, [[{**common, **row}.get(field) for field in RECOMMENDATION_CSV_HEADERS]
        for rows in data["export_recommendation"].values() for row in rows]
