"""Read the existing plan-chain engine without invoking scheduling or changing its rules."""

from datetime import datetime

from core.models.workbench_command import input_fingerprint
from core.models.workbench_plan_scope import PlanReadScope
from core.services.scheduler.gantt_critical_chain import compute_critical_chain_from_rows
from core.services.scheduler.resource_dispatch_task_ids import public_task_id

from .plan_fact_serialization import plain_plan_facts
from .plan_projection import public_time

ENGINE = "core.services.scheduler.gantt_critical_chain.compute_critical_chain_from_rows"
SEMANTICS = "selected_plan_control_predecessor_chain"


def unavailable(plan_ref, code, reason, *, target_task_ref=None, **evidence):
    return {"state": "unavailable", "reason_code": code, "reason": reason, "plan_ref": plan_ref,
            "source": ENGINE, "semantics": SEMANTICS, "scope": "full_plan", "time_basis": "factory_local",
            "mode": "related" if target_task_ref is not None else "global", "target_task_ref": target_task_ref,
            "gap_unit": "minute", "nodes": [], "task_refs": [], "edges": [], **evidence}


def _mixed_piece_groups(tasks):
    groups = {}
    for task in tasks:
        groups.setdefault(task["batch_id"], set()).add(task["piece_id"] is None)
    return any(len(values) > 1 for values in groups.values())


def _bound_rows(plans, planned):
    plan_ref = planned["plan"]["plan_ref"]
    repo, entry, _ = plans._selected(plan_ref)
    rows = plans._task_rows(repo, entry, PlanReadScope(plan_ref))
    task_refs = plans.references.get_task_refs(plan_ref, rows)
    tasks = {task["task_ref"]: task for task in planned["tasks"]}
    if set(task_refs.values()) != set(tasks) or len(rows) != len(tasks):
        return None, None
    resources = {item["ref"]: item["business_code"] for item in planned["resources"]}
    mapping = {}
    for row in rows:
        task = tasks[task_refs[row["schedule_id"]]]
        if (public_time(row["start_time"]), public_time(row["end_time"]), row["batch_id"], row["seq"], row.get("piece_id")) != (
                task["start"], task["end"], task["batch_id"], task["sequence"], task["piece_id"]):
            return None, None
        if any((row[kind + "_id"] or None) != resources.get(task[kind + "_ref"])
               for kind in ("machine", "operator")):
            return None, None
        key = (row.get("op_code") or "").strip() or public_task_id(row)
        if key in mapping:
            return None, None
        mapping[key] = task
    return rows, mapping


def _result_structure_valid(raw, mapping, point_count):
    ids, edges = raw.get("ids"), raw.get("edges")
    if (type(ids) is not list or any(type(key) is not str or key not in mapping for key in ids)
            or len(set(ids)) != len(ids) or type(edges) is not list or len(edges) != max(0, len(ids) - 1)
            or raw.get("edge_count") != len(edges) or raw.get("dropped_count") != point_count
            or raw.get("critical_chain_partial") is not (point_count > 0)):
        return False
    return True


def _edge_valid(edge, predecessor, successor, mapping):
    if (type(edge) is not dict or edge.get("from") != predecessor or edge.get("to") != successor
            or edge.get("edge_type") not in ("process", "machine", "operator")
            or type(edge.get("reason")) is not str or not edge["reason"] or type(edge.get("gap_minutes")) is not int):
        return False
    start = datetime.fromisoformat(mapping[successor]["start"])
    end = datetime.fromisoformat(mapping[predecessor]["end"])
    return edge["gap_minutes"] == int((start - end).total_seconds() // 60)


def _result_valid(raw, mapping, point_count, target_id=None):
    if type(raw) is not dict or raw.get("available") is False or not _result_structure_valid(raw, mapping, point_count):
        return False
    ids = raw["ids"]
    for index, edge in enumerate(raw["edges"]):
        if not _edge_valid(edge, ids[index], ids[index + 1], mapping):
            return False
    return (not ids or raw.get("makespan_end") == mapping[ids[-1]]["end"].replace("T", " ")) and (
        target_id is None or bool(ids) and ids[-1] == target_id)


def plan_chain(plans, planned, plan_state, visible_refs, *, target_task_ref=None):
    plan_ref = planned["plan"]["plan_ref"]
    target = {"target_task_ref": target_task_ref}
    if _mixed_piece_groups(planned["tasks"]):
        return unavailable(plan_ref, "engine_piece_precedence_unsupported",
            "原计划链算法不支持共同工序与分件之间的跨组依赖，未以分组排序冒充完整关键链。", **target)
    rows, mapping = _bound_rows(plans, planned)
    if rows is None or mapping is None:
        return unavailable(plan_ref, "chain_plan_facts_mismatch",
            "关键链明细与本次计划任务不一致或原引擎任务键有冲突，未改指同号工序。", **target)
    target_id = next((key for key, task in mapping.items() if task["task_ref"] == target_task_ref), None)
    if target_task_ref is not None and target_id is None:
        return unavailable(plan_ref, "chain_target_not_found", "所选目标不在该完整计划内，未切换到全局终点。", **target)
    point_count = sum(task["start"] == task["end"] for task in planned["tasks"])
    raw = compute_critical_chain_from_rows(rows, target_id=target_id)
    if type(raw) is not dict:
        return unavailable(plan_ref, "chain_engine_unavailable", "原计划链引擎返回类型无效，未展示为已验证结果。",
                           engine_reason="invalid_result_type", **target)
    evidence_ref = input_fingerprint({"engine": ENGINE, "plan_ref": plan_ref, "plan_state": plan_state,
                                      "target_task_ref": target_task_ref, "rows": plain_plan_facts(rows), "result": raw})
    if not _result_valid(raw, mapping, point_count, target_id):
        return unavailable(plan_ref, "chain_engine_unavailable", "原计划链引擎未返回完整、可核对的结果。",
                           engine_evidence_ref=evidence_ref, engine_reason=raw.get("reason_code", "invalid_result"), **target)
    if not raw["ids"]:
        return unavailable(plan_ref, "chain_no_supported_nodes", "原计划链算法没有可分析的正时长节点，未把零时长点延长。",
                           engine_evidence_ref=evidence_ref, omitted_point_count=point_count, **target)
    return _public_chain(raw, mapping, visible_refs, plan_ref, evidence_ref, point_count, len(planned["tasks"]), target_task_ref)


def _public_chain(raw, mapping, visible_refs, plan_ref, evidence_ref, point_count, plan_task_count, target_task_ref):
    nodes = [{key: mapping[ref][key] for key in ("task_ref", "operation_ref", "batch_id", "sequence", "process_label",
              "piece_id", "machine_ref", "operator_ref", "start", "end")} for ref in raw["ids"]]
    edges = [{"from_task_ref": mapping[edge["from"]]["task_ref"], "to_task_ref": mapping[edge["to"]]["task_ref"],
              **{key: edge[key] for key in ("edge_type", "reason", "gap_minutes")}} for edge in raw["edges"]]
    for node in nodes:
        node["in_scope"] = node["task_ref"] in visible_refs
    return {"state": "available", "reason_code": None, "reason": None, "source": ENGINE, "semantics": SEMANTICS,
            "scope": "full_plan", "plan_ref": plan_ref, "engine_evidence_ref": evidence_ref, "time_basis": "factory_local",
            "mode": "related" if target_task_ref is not None else "global", "target_task_ref": target_task_ref,
            "gap_unit": "minute", "gap_rounding": "floor", "nodes": nodes, "task_refs": [node["task_ref"] for node in nodes],
            "edges": edges, "makespan_end": raw["makespan_end"].replace(" ", "T"), "partial": point_count > 0,
            "omitted_point_count": point_count, "plan_task_count": plan_task_count,
            "visible_node_count": sum(node["in_scope"] for node in nodes)}
