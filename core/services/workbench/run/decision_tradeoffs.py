"""Deterministic business wording for the existing coverage-aware differences."""

_GROUP_PRIORITY = {"completeness": 0, "delivery": 1, "resources": 2, "preparation": 3, "stability": 4, "time": 5}


def _number(value, precision):
    minimum = 10 ** -precision
    if 0 < abs(value) < minimum:
        return "不到 " + format(minimum, "." + str(precision) + "f")
    return (format(abs(value), "." + str(precision) + "f").rstrip("0").rstrip(".") or "0") if precision else str(abs(int(value)))


def tradeoff_entry(definition, delta, *, scope, source, metric_version, supporting_refs=(), compared_batch_refs=()):
    """Keep different coverage and missing values visible; never rank units together."""
    state, value = delta["state"], delta.get("value")
    reason = delta.get("reason")
    label, unit, precision = definition["label"], definition["unit"], definition["precision"]
    display_value = value * 100 if value is not None and unit == "%" else value
    display_unit = "个百分点" if unit == "%" else unit
    if state == "different_coverage":
        text = ("少安排的准备需求：" + label + "减少 " + _number(display_value, precision) + " " + display_unit + "；未安排工序及其所需工时见明细。"
                if source == "runtime_operation_effort" and value is not None and value < 0 else
                label + "的两侧评价范围不同，按各自范围列出。")
    elif state == "unavailable":
        text = label + "：" + reason["message"] if reason else label + "缺少可比较的保存数值。"
    elif state == "not_applicable":
        text = label + "在当前范围不适用。"
    elif value == 0:
        text = label + "与当前基准相同。"
    elif value is not None:
        text = label + ("减少 " if value < 0 else "增加 ") + _number(display_value, precision) + " " + display_unit + "。"
    else:
        text = label + "的差值尚未形成。"
    refs = sorted(set(compared_batch_refs))
    return {"metric_key": definition["key"], "label": label, "unit": unit, "precision": precision,
            **{key: delta.get(key) for key in ("value", "reference_value", "selected_value", "state", "direction")},
            "scope": scope, "source": source, "metric_version": metric_version, "reason": reason, "text": text,
            "compared_batch_count": len(refs), "sample_compared_batch_refs": refs[:3],
            "supporting_refs": list(supporting_refs)[:3]}


def aggregate_tradeoffs(entries, definitions):
    order = {row["key"]: (_GROUP_PRIORITY[row["group"]], index) for index, row in enumerate(definitions)}
    eligible = sorted(entries, key=lambda row: order[row["metric_key"]])
    # The actual event metric is the primary business cost. The optimizer's
    # full-span statistic stays in all differences with its own source label.
    has_actual = any(row["metric_key"] == "type_changeover_count" and row["direction"] in ("better", "worse") for row in entries)
    main = [row for row in eligible if not (has_actual and row["metric_key"] == "changeover_count")]
    return {"benefits": [row for row in main if row["direction"] == "better"][:3],
            "costs": [row for row in main if row["direction"] == "worse"][:3], "all_differences": list(entries)}
