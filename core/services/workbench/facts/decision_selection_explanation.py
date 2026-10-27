"""Describe the recorded business-objective selection without rerunning it."""

from core.models.objective import metric_label_for, objective_choice_labels

from .decision_metrics import metric_definitions


def _metric_name(metric):
    return {"failed_ops": "未安排工序", "overdue_count": "超期批次", "total_tardiness_hours": "总拖期",
            "weighted_tardiness_hours": "加权拖期", "makespan_hours": "安排总时长", "changeover_count": "换型次数"}.get(metric, metric_label_for(metric))


def _entry(key, label, text, *, state="complete", unit=None, selected=None,
           source="saved_selection", scope="fixed_algorithm_selection"):
    return {"key": key, "label": label, "text": text, "state": state, "unit": unit,
            "selected_value": selected, "source": source, "scope": scope}


def selection_explanation(basis):
    primary = basis["primary_objective"]
    scope = basis["scoring_scope"]
    known = scope["components_known"]
    headline = ("按“" + objective_choice_labels()[primary] + "”推荐本次找到的最佳完整方案。" if scope["is_complete"] else
                "在本次已安排工序和完整批次范围内，按“" + objective_choice_labels()[primary] + "”推荐最佳方案。" if known else
                "已保存算法选中的部分安排；所选范围缺少完整评分依据。")
    entries = [_entry("shared_objectives", "共同优化", "多个业务方向共用一次求解和一份安排档案。",
                      state="complete", source="saved_selection", scope="shared_search")]
    fields = basis["objective_field_order"][primary]
    units = {row["key"]: row["unit"] for row in metric_definitions()}
    units["failed_ops"] = "道"
    for field, value in zip(fields, basis["selected_score"]):
        entries.append(_entry("score_" + field, _metric_name(field), "按计算时保存的完整指标顺序选择。",
            state="complete" if value is not None else "unavailable", unit=units.get(field), selected=value,
            scope="saved_scoring_scope"))
    issues = ([] if known else [{"code": "score_components_unavailable", "message": "所选范围缺少完整评分分量。"}])
    return {"headline": headline, "entries": entries, "issues": issues}


def unselected_explanation():
    """A run that saved no selection yet names what is not recorded."""
    return {"headline": "本次排产尚未保存推荐方案。",
            "entries": [_entry("selection_policy", "选择方式", "这条记录未保存选择方式。", state="unavailable"),
                        _entry("objective", "实际目标", "本次目标为“缺项”。", state="unavailable"),
                        _entry("selected_identity", "计算时推荐", "保存推荐为 未记录；按目标比较选出的方案为 未记录；"
                               "关键工序时间比较基准为 未记录。", state="unavailable")],
            "issues": []}
