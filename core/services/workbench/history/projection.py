"""Event identities, factual range markers and service-owned trend connections."""

from datetime import datetime

from core.models.workbench_command import WorkbenchCommandRejected

from .conditions import compare_prepared_history_conditions
from .metrics import gate_history_metric, project_history_metrics

_WINDOW_FIELDS = ("mode", "start", "end", "days", "anchor", "time_basis", "boundary", "state", "cohort")
_QUANTITY_FIELDS = ("value", "state", "known_subtotal", "known_count", "unknown_count", "total_count", "covered_batch_refs")


def reason(code, message):
    return {"code": code, "message": message}


def chronological_key(entry):
    value = entry["occurred_at"]
    return (value is None, datetime.fromisoformat(value.replace(" ", "T")) if value is not None else datetime.min,
            entry["entry_ref"])


def _navigation(reader, descriptor):
    refs, kind = descriptor["source"], descriptor["source_kind"]
    packet = reader.read(descriptor)
    result = []

    def add(label, view, context, present):
        enabled = bool(present)
        result.append({"label": label, "view": view, "context": context, "enabled": enabled,
                       "reason": None if enabled else "原记录缺少可打开的来源资料。"})

    if kind in ("run", "candidate_adoption"):
        try:
            run_available = reader.store.run(refs["run_ref"]) is not None
        except WorkbenchCommandRejected as exc:
            if exc.status != 404:
                raise
            run_available = False
        add("打开原运行", "run", {"run_ref": refs["run_ref"]}, run_available)
        add("打开原候选分析", "analysis", {"run_ref": refs["run_ref"], "candidate_ref": refs["candidate_ref"]},
            refs["run_ref"] and refs["candidate_ref"] and packet.get("candidate") is not None)
    elif kind == "trial_adoption":
        add("打开原试调", "trial", {"scenario_ref": refs["scenario_ref"]},
            refs["scenario_ref"] and packet.get("saved") is not None)
    if kind != "run":
        # Formal version identity comes from the saved binding, never the current plan.
        bound = refs["plan_ref"] is not None and not any(row["field"] == "official_plan" for row in descriptor["evidence_gaps"])
        add("打开正式甘特", "gantt", {"plan_ref": refs["plan_ref"]}, bound)
    return result


def project_entry(reader, descriptor, query):
    # Capacity changes remain visible even when the chosen chart is a delivery
    # metric. These two existing values stay private to the range marker.
    capacity_keys = ("machine_available_hours", "operator_available_hours")
    read_query = {**query, "metric_keys": list(dict.fromkeys(query["metric_keys"] + list(capacity_keys)))}
    raw = project_history_metrics(reader, descriptor, read_query)
    projected = {**raw, "metrics": {key: raw["metrics"][key] for key in query["metric_keys"]}}
    if not hasattr(reader, "history_range_facts"):
        reader.history_range_facts = {}
    reader.history_range_facts[descriptor["entry_ref"]] = {key: {field: raw["metrics"][key][field]
        for field in ("value", "known_subtotal", "state", "known_count", "unknown_count", "total_count", "covered_resource_refs")}
        for key in capacity_keys}
    refs = descriptor["source"]
    identity = {key: refs[key] for key in ("run_ref", "candidate_ref", "scenario_ref", "draft_ref", "plan_ref",
                "history_id", "receipt_ref", "request_key")}
    identity["plan_version"] = refs["version"]
    baseline = dict(descriptor["baseline"])
    if descriptor["source_kind"] == "run":
        capture = reader.read(descriptor).get("capture")
        if capture is not None:
            baseline = {key: capture["baseline"].get(key) for key in ("plan_ref", "version")}
    issues = [{key: row[key] for key in ("code", "message")} for row in descriptor["evidence_gaps"]]
    if projected["source"]["reason"] is not None and projected["source"]["reason"] not in issues:
        issues.append(projected["source"]["reason"])
    return {"entry_ref": descriptor["entry_ref"], "timeline": descriptor["timeline"],
            "source_kind": descriptor["source_kind"], "label": descriptor["label"],
            "occurred_at": descriptor["occurred_at"], "time_basis": descriptor["time_basis"],
            "state": descriptor["state"], "identity": identity, "times": dict(descriptor["times"]),
            "baseline": baseline, **projected, "navigation": _navigation(reader, descriptor), "issues": issues}


def window_comparable(before, after, definition):
    if definition["scope"] not in ("fixed_resource_window", "fixed_changeover_window"):
        return True
    previous, selected = (entry["reading_context"]["resource_window"] for entry in (before, after))
    return (previous["start"] is not None and previous["end"] is not None
            and all(previous[key] == selected[key] for key in ("start", "end", "time_basis", "boundary", "cohort")))


def range_changed(before, after, capacity_before, capacity_after):
    previous, selected = before["scope"], after["scope"]
    if any(previous[key] != selected[key] for key in ("state", "batch_refs", "operation_refs", "demand_hours")):
        return True
    if any(previous["batch_quantity"][key] != selected["batch_quantity"][key] for key in _QUANTITY_FIELDS):
        return True
    left, right = (entry["reading_context"]["resource_window"] for entry in (before, after))
    if any(left[key] != right[key] for key in _WINDOW_FIELDS):
        return True
    return capacity_before != capacity_after


def missing_packet(code="reference_required", message="请选择明确基准运行。"):
    return {"kind": "legacy", "ref": None, "entry_ref": None, "parsed_summary": None,
            "source_issue": reason(code, message)}


def _shared_window(entry, query):
    if query["range_start"] is not None:
        return {"start": query["range_start"], "end": query["range_end"]}
    window = entry["reading_context"]["resource_window"] if entry is not None else {}
    return {"start": window.get("start"), "end": window.get("end")}


def condition_pair(reader, before_descriptor, after_descriptor, after, query, cache):
    window = _shared_window(after, query)
    key = (before_descriptor["entry_ref"] if before_descriptor else None,
           after_descriptor["entry_ref"] if after_descriptor else None, window["start"], window["end"])
    if key not in cache:
        before = reader.read(before_descriptor) if before_descriptor is not None else missing_packet()
        selected = reader.read(after_descriptor) if after_descriptor is not None else missing_packet(
            "selection_required", "请选择实际历史条目。")
        cache[key] = compare_prepared_history_conditions(reader.condition_side(before, window),
                                                       reader.condition_side(selected, window))
    return cache[key]


def _observed_connection(before, after):
    return (before["value"] is not None and after["value"] is not None
            and before["state"] in ("complete", "partial", "not_applicable")
            and after["state"] in ("complete", "partial", "not_applicable")
            and all(before[key] is not None and before[key] == after[key] for key in ("unit", "metric_version", "scope")))


def trend_projection(reader, entries, descriptors, reference, reference_descriptor, query, definitions, cache):
    points, previous, previous_allowed = [], None, {}
    for entry in sorted(entries, key=chronological_key):
        state, allowed = "not_compared", {}
        if query["comparison"] == "same_conditions":
            pair = condition_pair(reader, reference_descriptor, descriptors[entry["entry_ref"]], entry, query, cache)
            state = pair["conditions"]["state"]
            for key in query["metric_keys"]:
                allowed[key] = reference is not None and gate_history_metric(definitions[key], reference["metrics"][key],
                    entry["metrics"][key], production_state=state, objective_state=pair["objective"]["state"],
                    window_comparable=window_comparable(reference, entry, definitions[key]))["state"] == "comparable"
        else:
            allowed = {key: True for key in query["metric_keys"]}
        connections = {key: bool(previous is not None and previous["occurred_at"] is not None
            and entry["occurred_at"] is not None and previous_allowed.get(key) and allowed[key]
            and _observed_connection(previous["metrics"][key], entry["metrics"][key])) for key in query["metric_keys"]}
        points.append({key: entry[key] for key in ("entry_ref", "occurred_at", "time_basis", "label", "state", "metrics", "scope")})
        points[-1].update(resource_window=entry["reading_context"]["resource_window"],
                         range_changed=previous is not None and range_changed(previous, entry,
                             reader.history_range_facts[previous["entry_ref"]], reader.history_range_facts[entry["entry_ref"]]),
                         condition_state=state, connections=connections)
        previous, previous_allowed = entry, allowed
    return {"point_scope": "current_page", "order": "asc", "points": points}


def comparison_conclusion(mode, pair, deltas, has_pair):
    improved = [key for key, item in deltas.items() if item["state"] == "comparable" and item["direction"] == "better"]
    worsened = [key for key, item in deltas.items() if item["state"] == "comparable" and item["direction"] == "worse"]
    state, message, cause = "observed", "显示原保存结果的业务走势。", None
    if mode == "same_conditions":
        if not has_pair:
            state, message, cause = "unavailable", "选择实际历史条目和明确基准后查看同条件对照。", reason(
                "history_pair_required", "同条件对照需要实际历史条目和明确基准运行。")
        elif pair["conditions"]["state"] == "different":
            state, message, cause = "different_conditions", "生产条件有变化，查看逐字段差异和实际观测值。", reason(
                "history_production_conditions_different", "两侧保存的生产条件不同。")
        elif pair["conditions"]["state"] == "unknown":
            state, message, cause = "unavailable", "生产条件缺少归档依据，保留实际观测值。", reason(
                "history_production_conditions_unknown", "两侧生产条件缺少充分归档依据。")
        elif pair["objective"]["state"] != "equal":
            different = pair["objective"]["state"] == "different"
            state = "different_objective" if different else "unavailable"
            message = "两侧优化目标不同，分别查看实际观测值。" if different else "优化目标缺少原保存依据。"
            cause = reason("history_objective_" + pair["objective"]["state"], message)
        elif not deltas or any(item["state"] != "comparable" for item in deltas.values()):
            state, message = "unavailable", "部分指标的版本、覆盖或资源窗口缺少可比较依据。"
            cause = next((item["reason"] for item in deltas.values() if item["state"] != "comparable"),
                         reason("history_metric_unavailable", message))
        elif improved and worsened:
            state, message = "comparable", "同条件下部分指标改善、部分指标变差，按实际指标作取舍。"
        elif worsened:
            state, message = "worse", "所选指标在同条件下变差。"
        elif improved:
            state, message = "improved", "所选指标在同条件下改善。"
        elif all(item["direction"] == "equal" for item in deltas.values()):
            state, message = "equal", "所选指标在同条件下相同。"
        else:
            state, message = "comparable", "所选指标具备同条件比较依据。"
    return {"state": state, "message": message, "reason": cause,
            "improved_metric_keys": improved if mode == "same_conditions" else [],
            "worsened_metric_keys": worsened if mode == "same_conditions" else []}
