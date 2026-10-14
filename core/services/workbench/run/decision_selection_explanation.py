"""Describe the recorded selector and health calculation without rerunning either."""

from core.models.objective import metric_label_for, objective_choice_labels
from core.services.workbench.facts.table_cells import number_text

from .decision_metrics import metric_definitions

_CHECKS = {"failed_ops": ("未安排工序上限", "道"), "objective_primary_score": ("主要指标上限", None),
           "overdue_count": ("超期批次上限", "批"), "total_tardiness_hours": ("总拖期上限", "小时")}
_HEALTH = {"critical_chain_finish_hours_delta": "关键工序总时长", "critical_chain_wait_hours_delta": "关键工序间等待",
           "top_impact_ops_avg_start_hours_delta": "重点工序平均开始时间", "critical_chain_slack_hours_delta": "关键工序可调整余量"}
_STEPS = {"failed_ops": "优先选择未安排工序较少的方案", "primary_score": "比较主要指标",
          "secondary_score": "继续比较下一项指标", "baseline_preference": "各项比较指标相同，优先原算法方案",
          "candidate_sequence": "各项比较指标及计算方式相同，优先先生成的方案",
          "input_order": "各项比较指标和生成序号相同，按原有顺序选择",
          "only_completed_candidate": "本次只有一份方案计算完成", "score_length": "按保存的指标数量决定比较顺序"}
_POLICIES = {"score_only": "按目标依次比较各项指标", "balanced": "按目标比较，并检查关键工序时间和交期上限"}
_NOT_CHECKED = {"score_only": "本次按目标依次比较各项指标。",
                "baseline_unavailable": "原算法方案没有计算结果，无法比较关键工序时间。",
                "critical_candidate_unavailable": "关键工序优化方案没有计算结果。",
                "critical_health_not_better": "关键工序时间未达到改善条件，保留按目标比较选出的方案。"}
_HEALTH_UNAVAILABLE = {"baseline": "本方案是关键工序时间的比较基准。",
                       "baseline_result_unavailable": "原算法方案没有计算结果，无法比较关键工序时间。",
                       "critical_path_unavailable": "这条记录未保存关键工序列表，无法比较其时间。",
                       "critical_path_result_missing": "部分关键工序没有安排，无法比较其时间。",
                       "critical_path_empty": "这条记录保存的关键工序列表为空。"}


def _metric_name(metric):
    return {"failed_ops": "未安排工序", "overdue_count": "超期批次", "total_tardiness_hours": "总拖期",
            "weighted_tardiness_hours": "加权拖期", "makespan_hours": "安排总时长", "changeover_count": "换型次数"}.get(metric, metric_label_for(metric))


def _quantity(value, unit):
    return "未记录" if value is None else number_text(value) + (" " + unit if unit else "")


def _selection_headline(basis, evidence, health, labels, units, candidates, artifact):
    if evidence is None:
        return "推荐方案已保存；这条旧记录未保存具体选择依据。"
    def quantity(value, unit):
        displayed = float(format(value, ".12g")) if type(value) is float else value
        return _quantity(displayed, unit)
    completion = (artifact.get("metrics") or {}).get("completion")
    # Candidate archives retain the completion dataclass fields; newer process
    # records also save its objective_scope property explicitly.
    completed_subset = isinstance(completion, dict) and (
        completion.get("objective_scope") == "completed_batches_only" or
        "objective_scope" not in completion and bool(completion.get("incomplete_batch_ids")) and completion.get("explained") is True)
    scope_label = "本次计算范围内已排齐的批次中" if completed_subset else "本次计算范围内"
    objective = basis["objective_name"]
    order = basis["objective_field_order"]
    metric = order[1] if len(order) > 1 else None
    selected = evidence.get("selected") or {}
    score = selected.get("score") or []
    value = score[1] if len(score) > 1 else None
    result = "本次按“" + objective_choice_labels().get(objective, "保存的排产目标") + "”比较"
    if metric and value is not None:
        result += "；" + scope_label + "，推荐方案" + ("预计" if metric == "overdue_count" else "的") + _metric_name(metric) + " " + quantity(value, units.get(metric))
    balanced = evidence.get("balanced_checks")
    if balanced and balanced["checked"] and balanced["override_applied"]:
        improvements = [item for item in (health or {}).get("components", [])
                        if item["contribution"] > 0 and item["delta_hours"] is not None]
        if improvements:
            result += "；相对" + labels.get(basis.get("health_reference_candidate_ref"), "原算法方案") + "，" + "、".join(
                _HEALTH[item["key"]] + ("减少 " if item["delta_hours"] < 0 else "增加 ") + quantity(abs(item["delta_hours"]), "小时")
                for item in improvements[:2])
        costs = [item for item in balanced["checks"] if item["key"] in ("overdue_count", "total_tardiness_hours") and item["candidate_value"] > item["reference_value"]]
        if costs:
            result += "；比" + labels.get(balanced.get("reference_candidate_ref"), "按目标比较选出的方案") + "，" + "、".join(
                _metric_name(item["key"]) + "增加 " + quantity(item["candidate_value"] - item["reference_value"], units.get(item["key"])) + "（允许上限 " + quantity(item["limit"], units.get(item["key"])) + "）" for item in costs)
        else:
            result += "；超期批次和总拖期均未增加"
    else:
        tie = evidence.get("tiebreak") or {}
        full = tie.get("full_score_tied_candidate_refs") or []
        if len(full) > 1 and tie.get("decisive_step") == "baseline_preference":
            compared = "超期批次和累计超期时长" if metric in ("overdue_count", "total_tardiness_hours") and "total_tardiness_hours" in order else _metric_name(metric)
            completed = {row["candidate_ref"] for row in candidates if row.get("status") == "completed"}
            result = "本次优化未减少" + compared + "，推荐原算法方案" if set(full) == completed else "按目标比较时指标相同，优先推荐原算法方案"
            details = [(name, selected.get(name)) for name in ("overdue_count", "total_tardiness_hours") if selected.get(name) is not None]
            if not details and metric and value is not None:
                details = [(metric, value)]
            result += "；" + scope_label + "：" + "、".join(("预计" if name == "overdue_count" else "") + _metric_name(name) + " " + quantity(number, units.get(name)) for name, number in details)
        elif len(tie.get("primary_tied_candidate_refs") or []) > 1:
            index = tie.get("decisive_score_index")
            result += "；主要指标相同的方案有 " + str(len(tie["primary_tied_candidate_refs"])) + " 份"
            if type(index) is int and 1 < index < len(order):
                result += "，继续比较“" + _metric_name(order[index]) + "”后选出"
            else:
                decisive_step = tie.get("decisive_step")
                result += "，" + (_STEPS.get(decisive_step, "按保存的比较顺序选出") if decisive_step is not None else "按保存的比较顺序选出")
        if balanced and balanced["checked"]:
            failed = next((item for item in balanced["checks"] if not item["passed"]), None)
            if failed:
                name = metric if failed["key"] == "objective_primary_score" else failed["key"]
                result += "；另一方案的" + _metric_name(name) + " " + quantity(failed["candidate_value"], units.get(name)) + "，超过允许上限 " + quantity(failed["limit"], units.get(name))
        elif balanced and balanced.get("reason_code") not in (None, "score_only") and len(full) <= 1:
            result += "；" + _NOT_CHECKED.get(balanced["reason_code"], "这条记录未保存关键工序时间的比较结果").rstrip("。")
    return result + "。"


def _entry(key, label, text, *, state="complete", unit=None, reference=None, selected=None, value=None,
           limit=None, tolerance=None, tolerance_unit=None, source="saved_selection", scope="fixed_algorithm_selection"):
    return {"key": key, "label": label, "text": text, "state": state, "unit": unit,
            "reference_value": reference, "selected_value": selected, "value": value, "limit": limit,
            "tolerance": tolerance, "tolerance_unit": tolerance_unit, "source": source, "scope": scope}


def selection_explanation(basis, artifact, candidates):
    evidence, health = basis["decision_evidence"], basis["health_decision_evidence"]
    entries, issues = [], []
    units = {row["key"]: row["unit"] for row in metric_definitions()}
    units.update(failed_ops="道", overdue_count="批")
    labels = {row["candidate_ref"]: row["artifact"].get("label") or row["candidate_ref"] for row in candidates}
    def identity(ref):
        return (labels.get(ref, ref) + "（" + ref + "）") if ref else "缺项"
    headline = _selection_headline(basis, evidence, health, labels, units, candidates, artifact)
    entries.append(_entry("selection_policy", "选择方式", _POLICIES.get(basis["selection_policy"], "这条记录未保存选择方式。"),
                          state="complete" if basis["selection_policy"] else "unavailable"))
    objective = basis["objective_name"]
    entries.append(_entry("objective", "实际目标", "本次目标为“" + objective_choice_labels().get(objective, objective or "缺项") + "”。",
                          state="complete" if objective else "unavailable"))
    entries.append(_entry("selected_identity", "计算时推荐", "保存推荐为 " + labels.get(basis["selected_candidate_ref"], "未记录") +
        "；按目标比较选出的方案为 " + labels.get(basis["raw_score_best_candidate_ref"], "未记录") +
        "；关键工序时间比较基准为 " + labels.get(basis.get("health_reference_candidate_ref"), "未记录") + "。",
        state="complete" if basis["selected_candidate_ref"] else "unavailable"))
    if evidence is None:
        issues.append({"code": "selection_detail_missing", "message": "这条旧记录未保存交期上限检查和指标相同时的选择依据。"})
    else:
        selected, raw = evidence.get("selected") or {}, (evidence.get("anchors") or {}).get("raw_score_best") or {}
        before, after = raw.get("score") or [], selected.get("score") or []
        for index, value in enumerate(after):
            reference = before[index] if index < len(before) else None
            metric = basis["objective_field_order"][index] if index < len(basis["objective_field_order"]) else "score[" + str(index) + "]"
            name = _metric_name(metric)
            entries.append(_entry("score_" + str(index), name, "按计算时保存的指标顺序依次比较。", unit=units.get(metric),
                                  reference=reference, selected=value, value=value - reference if reference is not None else None))
        tie = evidence.get("tiebreak")
        if tie is None:
            issues.append({"code": "tiebreak_detail_missing", "message": "这条记录未保存指标相同时的选择依据。"})
        else:
            primary = tie.get("primary_tied_candidate_refs") or []
            full = tie.get("full_score_tied_candidate_refs") or []
            groups = (["主要指标相同的方案有 " + str(len(primary)) + " 份"] if len(primary) > 1 else []) + (
                      ["各项目标指标都相同的方案有 " + str(len(full)) + " 份"] if len(full) > 1 else [])
            index = tie.get("decisive_score_index")
            field = ("（" + _metric_name(basis["objective_field_order"][index]) + "）") if type(index) is int and index < len(basis["objective_field_order"]) else ""
            text = ("；".join(groups) + "；" if groups else "") + _STEPS.get(tie.get("decisive_step"), "按保存的比较顺序选择") + field + "。"
            entries.append(_entry("tiebreak", "指标相同时如何选择", text, value=tie.get("decisive_score_index")))
        balanced = evidence.get("balanced_checks")
        if balanced is None:
            issues.append({"code": "balanced_checks_missing", "message": "这条记录未保存关键工序时间和交期上限检查。"})
        elif not balanced["checked"]:
            entries.append(_entry("balanced_eligibility", "交期上限检查", _NOT_CHECKED.get(balanced.get("reason_code"), "这次计算未执行交期上限检查。"),
                                  state="not_applicable"))
        else:
            checked = identity(balanced.get("candidate_ref"))
            reference = identity(balanced.get("reference_candidate_ref"))
            for check in balanced["checks"]:
                label, unit = _CHECKS[check["key"]]
                if check["key"] == "objective_primary_score":
                    metric = basis["objective_field_order"][1] if len(basis["objective_field_order"]) > 1 else None
                    label, unit = _metric_name(metric) + "上限", units.get(metric)
                tolerance_unit = "%" if check["key"] == "total_tardiness_hours" else unit
                entries.append(_entry("tolerance_" + check["key"], label,
                    checked + "的" + label.replace("上限", "") + "为 " + _quantity(check["candidate_value"], unit) +
                    "，允许上限为 " + _quantity(check["limit"], unit) + ("，在上限内。" if check["passed"] else "，超过上限。") + "比较方案为 " + reference + "。", unit=unit,
                    reference=check["reference_value"], selected=check["candidate_value"],
                    value=check["candidate_value"] - check["reference_value"], limit=check["limit"], tolerance=check["tolerance"], tolerance_unit=tolerance_unit))
            override = balanced["override_applied"]
            entries.append(_entry("balanced_result", "实际选择结果", "关键工序时间改善且交期指标在上限内，因此选中此优化方案。" if override else
                                  "保留按目标比较选出的方案。",
                                  ))
    if health is None:
        issues.append({"code": "health_detail_missing", "message": "这条记录未保存关键工序时间的比较数值和评价分项。"})
        saved = artifact.get("health") or {}
        for key, label in _HEALTH.items():
            if saved.get(key) is not None:
                entries.append(_entry("health_" + key, label, "计算时保存的时间变化。", unit="小时", value=saved[key],
                                      source="saved_health_summary", scope="fixed_health_reference"))
    else:
        saved_health = artifact.get("health") or {}
        states = {"better": "改善", "same": "相同", "worse": "增加代价", "unavailable": "缺少适用评价"}
        state = saved_health.get("state")
        state_label = states.get(state, "未记录") if state is not None else "未记录"
        entries.append(_entry("health_result", "关键工序时间评价", "计算时的评价为“" + state_label + "”。",
            selected=saved_health.get("score"), unit="分", source="saved_health_calculation", scope="fixed_health_reference"))
        thresholds = health.get("score_thresholds")
        if thresholds:
            entries.append(_entry("health_rules", "时间变化的评价规则", "改善门槛为 " + str(thresholds["better_min"]) + " 分，增加代价门槛为 " +
                str(thresholds["worse_max"]) + " 分；相对容差为 " + str(health["relative_tolerance_ratio"] * 100) +
                "%，基础时间容差为 " + str(health["neutral_tolerance_hours"]) + " 小时。",
                source="saved_health_calculation", scope="fixed_health_reference"))
        if health.get("state") == "unavailable":
            reason = health.get("reason_code")
            entries.append(_entry("health_unavailable", "关键工序时间资料", _HEALTH_UNAVAILABLE.get(reason, "这条记录缺少关键工序时间的比较资料。"),
                                  state="unavailable", source="saved_health_calculation", scope="fixed_health_reference"))
        for item in health.get("components", []):
            label = _HEALTH[item["key"]]
            text = label + "按计算时的时间容差评价，计入 " + str(item["contribution"]) + " 分。"
            entries.append(_entry("health_" + item["key"], label, text, state=item["state"], unit="小时",
                reference=item["reference_value"], selected=item["candidate_value"], value=item["delta_hours"],
                tolerance=item["tolerance_hours"], tolerance_unit="小时", source="saved_health_calculation", scope="fixed_health_reference"))
            if item["delta_hours"] is not None and (item["reference_value"] is None or item["candidate_value"] is None):
                issues.append({"code": "health_levels_missing", "message": label + "只保存了变化值，未保存两份方案的原始数值。"})
    reused = artifact.get("reused_from_candidate_key")
    if reused:
        ref = next((row["candidate_ref"] for row in candidates if row["artifact"].get("candidate_key") == reused), None)
        entries.append(_entry("equivalent_reuse", "安排来源", "本方案沿用相同安排的候选方案，来源编号为 " + str(ref) + "。",
                              source="saved_candidate_reuse"))
    return {"headline": headline, "entries": entries, "issues": issues}
