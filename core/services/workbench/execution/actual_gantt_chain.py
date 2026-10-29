"""Read the existing plan-chain engine without invoking scheduling or changing its rules."""

from core.services.common.plan_task_identity import public_task_id
from core.services.scheduler.gantt.critical_chain import compute_critical_chain_from_rows

ENGINE = "core.services.scheduler.gantt.critical_chain.compute_critical_chain_from_rows"
SEMANTICS = "selected_plan_control_predecessor_chain"


def unavailable(plan_ref, code, reason, *, target_task_ref, **evidence):
    return {"state": "unavailable", "reason_code": code, "reason": reason, "plan_ref": plan_ref,
            "source": ENGINE, "semantics": SEMANTICS, "scope": "full_plan", "time_basis": "factory_local",
            "mode": "related" if target_task_ref is not None else "global", "target_task_ref": target_task_ref,
            "gap_unit": "minute", "nodes": [], "task_refs": [], "edges": [], **evidence}


def _mixed_piece_groups(tasks):
    groups = {}
    for task in tasks:
        groups.setdefault(task["batch_id"], set()).add(task["piece_id"] is None)
    return any(len(values) > 1 for values in groups.values())


def _bound_rows(plan_ref, rows, *, context, dt_intervals):
    projected, _, _, _ = context.projected_tasks(plan_ref, rows)
    mapping, bound = {}, []
    for original, task in zip(rows, projected):
        row = dict(original)
        row["task_id"] = "task_" + task["task_ref"]
        raw_op_code = row.get("op_code")
        op_code = raw_op_code if type(raw_op_code) is str and raw_op_code.strip() else ""
        key = op_code or public_task_id(row)
        if key in mapping:
            return None, None
        row["start_time"], row["end_time"] = dt_intervals[original["schedule_id"]]
        mapping[key] = task
        bound.append(row)
    return bound, mapping


def plan_chain(plan_ref, visible_refs, *, target_task_ref, context):
    target = {"target_task_ref": target_task_ref}
    with context.read_scope():
        _, entry, _ = context.selected(plan_ref)
        detail_rows = context.detail_rows(entry)
        if _mixed_piece_groups(detail_rows):
            return unavailable(plan_ref, "engine_piece_precedence_unsupported",
                "暂不支持共同工序与分件之间的跨组依赖，无法计算关键链。", **target)
        dt_intervals = context.datetime_intervals(entry)
        rows, mapping = _bound_rows(plan_ref, detail_rows, context=context, dt_intervals=dt_intervals)
    if rows is None or mapping is None:
        return unavailable(plan_ref, "chain_plan_facts_mismatch",
            "关键链与计划明细不一致，请刷新重试。", **target)
    target_id = next((key for key, task in mapping.items() if task["task_ref"] == target_task_ref), None)
    if target_task_ref is not None and target_id is None:
        return unavailable(plan_ref, "chain_target_not_found", "所选工序不在此计划中，请重新选择。", **target)
    raw = compute_critical_chain_from_rows(rows, target_id=target_id)
    if raw.get("available") is False:
        return unavailable(plan_ref, "chain_engine_unavailable", "计划链没算出完整、可核对的结果。请刷新后重试。",
                           engine_reason=raw["reason_code"], **target)
    point_count = raw["dropped_count"]
    if not raw["ids"]:
        return unavailable(plan_ref, "chain_no_supported_nodes", "此计划仅有零工时工序，无可分析的关键链。",
                           omitted_point_count=point_count, **target)
    return _public_chain(raw, mapping, visible_refs, plan_ref, point_count, len(mapping), target_task_ref)


def _public_chain(raw, mapping, visible_refs, plan_ref, point_count, plan_task_count, target_task_ref):
    nodes = [{key: mapping[ref][key] for key in ("task_ref", "operation_ref", "batch_id", "sequence", "process_label",
              "piece_id", "machine_ref", "operator_ref", "start", "end")} for ref in raw["ids"]]
    edges = [{"from_task_ref": mapping[edge["from"]]["task_ref"], "to_task_ref": mapping[edge["to"]]["task_ref"],
              **{key: edge[key] for key in ("edge_type", "reason", "gap_minutes")}} for edge in raw["edges"]]
    for node in nodes:
        node["in_scope"] = node["task_ref"] in visible_refs
    return {"state": "available", "reason_code": None, "reason": None, "source": ENGINE, "semantics": SEMANTICS,
            "scope": "full_plan", "plan_ref": plan_ref, "time_basis": "factory_local",
            "mode": "related" if target_task_ref is not None else "global", "target_task_ref": target_task_ref,
            "gap_unit": "minute", "gap_rounding": "floor", "nodes": nodes, "task_refs": [node["task_ref"] for node in nodes],
            "edges": edges, "makespan_end": raw["makespan_end"].replace(" ", "T"), "partial": point_count > 0,
            "omitted_point_count": point_count, "plan_task_count": plan_task_count,
            "visible_node_count": sum(node["in_scope"] for node in nodes)}
