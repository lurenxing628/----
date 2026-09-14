"""Keep the existing official-review sheet contract, now labelled from the ledger."""

from .review_records import actual_resource
from .review_values import minutes


def deviation(planned, actual, action):
    """偏差按“晚<动作> N 分钟 / 提前<动作> N 分钟”写，和交期超期分开说。"""
    value = minutes(planned, actual)
    if value is None:
        return "尚不可比较"
    rounded = round(value)
    if rounded == 0:
        return "按计划" + action
    return ("晚" if rounded > 0 else "提前") + action + " " + str(abs(rounded)) + " 分钟"


def export_labels(label, operation, directory):
    result = dict(label)
    result.update({"feedback_status_label": operation["execution_label"],
        "actual_start_time_label": operation["actual_start"] or "暂无已确认实际开工",
        "actual_end_time_label": operation["confirmed_finish"] or (
            "未确认整道完工（记录时间异常）" if operation["execution_state"] == "invalid" else "未确认整道完工"),
        "start_deviation_label": deviation(operation["planned_start"], operation["actual_start"], "开工"),
        "end_deviation_label": deviation(operation["planned_end"], operation["confirmed_finish"], "完成"),
        "actual_resource_label": operation["actual_machine_label"] + " / " + operation["actual_operator_label"],
        "pause_duration_label": "未知" if operation["pause_duration_minutes"] is None else str(operation["pause_duration_minutes"]) + " 分钟"})
    for key in ("reason", "severity", "impact_minutes", "handling_status", "suggest_reschedule"):
        value = operation["exception_" + key]
        result["exception_" + key + "_label"] = value if value is not None else "暂无异常记录"
    for kind in ("machine", "operator"):
        result["exception_affected_" + kind + "_label"] = actual_resource(directory, kind, operation["exception_" + kind + "_ref"])["label"]
    return result
