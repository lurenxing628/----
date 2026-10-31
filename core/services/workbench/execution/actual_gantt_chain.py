"""Read the existing plan-chain engine without invoking scheduling or changing its rules."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.scheduler.gantt.critical_chain import compute_critical_chain_from_dependencies
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable
from core.services.workbench.plan.process_order import load_frozen_plan_process_order
from core.services.workbench.plan.projection import required_text, resource_ref, sequence

ENGINE = "core.services.scheduler.gantt.critical_chain.compute_critical_chain_from_rows"
SEMANTICS = "selected_plan_control_predecessor_chain"


def unavailable(plan_ref, code, reason, *, target_task_ref, **evidence):
    return {"state": "unavailable", "reason_code": code, "reason": reason, "plan_ref": plan_ref,
            "source": ENGINE, "semantics": SEMANTICS, "scope": "full_plan", "time_basis": "factory_local",
            "mode": "related" if target_task_ref is not None else "global", "target_task_ref": target_task_ref,
            "gap_unit": "minute", "nodes": [], "task_refs": [], "edges": [], **evidence}


def _bound_frozen_rows(frozen, *, context, dt_intervals, times):
    selected = frozen["selected"]
    operations = frozen["operations"]
    refs = frozen["refs"]
    relations = frozen["relations"]
    task_refs = frozen["task_refs"]
    resources = {}
    for kind in ("machine", "operator"):
        keys = sorted({str(row[kind + "_id"]) for row in selected if row[kind + "_id"] not in (None, "")})
        mapping_res = context.active_map(kind, keys)
        if set(mapping_res) != set(keys):
            raise WorkbenchCommandRejected("identity_missing", "安排关联的批次、设备或人员编号缺失，请到资料总览核对。")
        resources[kind] = mapping_res
    mapping, by_operation, bound = {}, {}, []
    for row in selected:
        schedule_id = row["id"]
        t_ref = task_refs[schedule_id]
        op_id = row["op_id"]
        op = operations[op_id]
        op_ref = refs[op_id]
        start, end = times[schedule_id]
        piece = op.get("piece_id")
        if piece is not None:
            piece = required_text(piece)
        task = {
            "task_ref": t_ref,
            "operation_ref": op_ref,
            "batch_id": required_text(op["batch_id"]),
            "sequence": sequence(op["seq"]),
            "process_label": op["op_type_name"],
            "piece_id": piece,
            "machine_ref": resource_ref(row, "machine", resources),
            "operator_ref": resource_ref(row, "operator", resources),
            "start": start,
            "end": end,
        }
        low_dt, high_dt = dt_intervals[schedule_id]
        mapping[t_ref] = task
        by_operation[op_ref] = t_ref
        bound.append({
            "op_code": t_ref,
            "operation_ref": op_ref,
            "batch_id": task["batch_id"],
            "piece_id": piece,
            "seq": task["sequence"],
            "op_type_name": task["process_label"],
            "start_time": low_dt,
            "end_time": high_dt,
            "machine_id": row["machine_id"],
            "operator_id": row["operator_id"],
        })
    previous = {
        t_ref: [
            by_operation[parent]
            for parent in relations[task["operation_ref"]]
            if parent in by_operation
        ]
        for t_ref, task in mapping.items()
    }
    return bound, previous, mapping


def plan_chain(plan_ref, visible_refs, *, target_task_ref, context):
    target = {"target_task_ref": target_task_ref}
    try:
        with context.read_scope():
            _, entry, _ = context.selected(plan_ref)
            frozen = load_frozen_plan_process_order(context.conn, plan_ref=plan_ref, context=context)
            if frozen is None:
                return unavailable(plan_ref, "process_order_not_recorded", "此计划未记录工序顺序。", **target)
            if target_task_ref is not None and target_task_ref not in set(frozen["task_refs"].values()):
                return unavailable(plan_ref, "chain_target_not_found", "所选工序不在此计划中，请重新选择。", **target)
            dt_intervals = context.datetime_intervals(entry)
            times = context.intervals(entry)
            rows, previous, mapping = _bound_frozen_rows(
                frozen, context=context, dt_intervals=dt_intervals, times=times
            )
    except (AdoptionBaselineUnavailable, WorkbenchPlanReferenceError, PieceAdoptionBlocked):
        return unavailable(plan_ref, "process_order_unavailable", "工序顺序数据不完整。", **target)
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        return unavailable(plan_ref, "process_order_unavailable", "工序顺序数据不完整。", **target)
    raw = compute_critical_chain_from_dependencies(
        rows, previous, target_id=target_task_ref, include_points=False
    )
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
