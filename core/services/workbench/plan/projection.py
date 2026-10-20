"""Allowlisted plan/task DTOs. Private catalog errors and locators never serialize."""

from __future__ import annotations

from core.models.schedule_plan_role import ROLE_ADOPTED
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.zero_duration import point_event_dto
from data.repositories.schedule_time_sql import parse_dt_for_sql

_REASONS = {
    "summary_invalid": "这次排产的摘要无效，确认不了计划是否完整。请刷新后重试。",
    "summary_missing": "这次排产的摘要缺失，确认不了计划是否完整。请刷新后重试。",
    "plan_unavailable": "这个计划的类型关系或明细无效，暂时看不了。请刷新计划列表后重试。",
    "history_missing": "这个试调方案依据的那次排产已经没有了，暂时看不了。",
    "scenario_not_active": "这个试调方案已发布、过期或作废，不能再拿来查看。请回「试调」重新选一个。",
    "scenario_unavailable": "这个试调方案依据的计划关系或明细无效，暂时看不了。",
    "plan_binding_invalid": "这个计划的类型或它依据的计划已经变了，暂时看不了。请刷新计划列表后重试。",
    "identity_missing": "计划编号缺失，请刷新计划列表。",
    "identity_invalid": "这个计划的编号和当前记录对不上，暂时看不了。请刷新计划列表后重试。",
    "source_missing": "计划来源记录已不存在，请刷新列表后重新选择。",
}


def wire_positive_int64(value):
    if type(value) is not int or not 0 < value <= (1 << 63) - 1:
        return None
    return value if value <= (1 << 53) - 1 else str(value)


def _public_reasons(codes):
    return [{"code": code if code in _REASONS else "plan_unavailable",
             "message": _REASONS.get(code, _REASONS["plan_unavailable"])} for code in codes]


def project_plan(entry, plan_ref):
    identity = entry.plan_identity
    version = wire_positive_int64(entry.locator.version)
    if entry.can_view and version is None:
        raise WorkbenchCommandRejected("plan_unavailable", "计划的版本号无效，不能开放查看。请刷新计划列表后重试。")
    return {"plan_ref": plan_ref, "version": version, "kind": entry.kind,
            "is_current_official": bool(entry.can_view and identity is not None
                                        and identity.is_current_executable_official_version),
            "display_name": entry.display_name, "completeness": entry.completeness,
            "capabilities": {"view": entry.can_view, "export": entry.can_view,
                             "edit_draft": False, "adopt": False, "report_actual": False},
            "blocked_reasons": _public_reasons(issue.code for issue in entry.blocked_reasons)}


def project_unavailable_plan(locator, plan_ref, display_name, reason_codes, *, completeness="invalid"):
    """A disabled header; a missing permanent identity stays null, never allocated."""
    kind = "scenario" if locator.scenario_id is not None else "official" if locator.plan_role == ROLE_ADOPTED else "candidate"
    version = wire_positive_int64(locator.version)
    return {"plan_ref": plan_ref, "version": version, "kind": kind,
            "is_current_official": False, "display_name": display_name, "completeness": completeness,
            "capabilities": {"view": False, "export": False, "edit_draft": False, "adopt": False, "report_actual": False},
            "blocked_reasons": _public_reasons(reason_codes)}


def public_time(value):
    parsed = parse_dt_for_sql(value)
    if parsed is None:
        raise WorkbenchCommandRejected("plan_unavailable", "工序安排的起止时间无效，请核对计划资料。")
    return parsed.replace(" ", "T")


def _required_text(value):
    if type(value) is not str or not value.strip():
        raise WorkbenchCommandRejected("plan_unavailable", "有安排缺批次号或工序名称，读不全。请到批次管理核对。")
    return value


def _sequence(value):
    wire = wire_positive_int64(value)
    if wire is None:
        raise WorkbenchCommandRejected("plan_unavailable", "工序号无效，请到批次管理核对。")
    return wire


def _resource_ref(row, kind, identities):
    key = row[kind + "_id"]
    if key is None or key == "":
        return None
    identity = identities[kind].get(str(key))
    if identity is None:
        raise WorkbenchCommandRejected("identity_missing", "安排关联的设备或人员编号缺失，请到资料总览核对。")
    return identity.ref


def _captured_quantities(operation, batch, execution, basis):
    from core.services.workbench.facts.candidate_values import number

    gaps = []
    piece = operation.get("piece_id")
    valid_piece = "piece_id" in operation and (piece is None or type(piece) is str and piece.strip() and "\x00" not in piece)
    captured = type(execution) is dict
    quantity = number(execution.get("target_quantity"), "quantity", gaps, integer=True) if captured else None
    batch_quantity = number(batch.get("quantity"), "batch_quantity", gaps, integer=True)
    valid = (valid_piece and captured
             and execution.get("target_basis") == ("piece" if piece is not None else "batch"))
    return {"piece_id": piece if valid_piece else None, "quantity": quantity if valid else None,
            "batch_quantity": batch_quantity, "quantity_basis": basis,
            "quantity_reason": None if valid and quantity is not None and not gaps else "plan_target_invalid"}


def _adopted_task_facts(conn, plan_ref, *, context=None):
    if context is not None:
        if plan_ref not in context._task_work:
            context._task_work[plan_ref] = _read_adopted_task_facts(conn, plan_ref, context=context)
        return context._task_work[plan_ref]
    return _read_adopted_task_facts(conn, plan_ref)


def _read_adopted_task_facts(conn, plan_ref, *, context=None):
    from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
    from core.services.workbench.facts.adoption_baseline_sources import read_adoption_operation_facts
    from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable, require

    if conn is None:
        return {}, "plan_target_not_recorded", None
    try:
        evidence = context.adopted_source(plan_ref) if context is not None else _adopted_source_record(conn, plan_ref)
        if evidence is None:
            return {}, "plan_target_not_recorded", None
        basis, arranged = evidence["basis"], evidence["arranged"]
        source = evidence["generation_facts"] if basis == "candidate_adoption" else evidence["trial_source"]
        result = _source_quantities(basis, arranged, source)
        require(set(result) == {row["op_id"] for row in arranged}, "quantity.complete_operation_set")
        return result, None, read_adoption_operation_facts(conn, evidence)
    except (AdoptionBaselineUnavailable, WorkbenchPlanReferenceError):
        return {}, "plan_target_unavailable", {}
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        return {}, "plan_target_unavailable", {}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {}, "plan_target_unavailable", {}


def read_adopted_source(conn, plan_ref, *, context=None):
    """Read the audited immutable source; callers retain their read transaction."""
    from core.infrastructure.read_evidence import verified_read

    return verified_read(conn, ("adopted_plan_source", plan_ref), lambda: _read_adopted_source(conn, plan_ref, context=context))


def _read_adopted_source(conn, plan_ref, *, context=None):
    evidence = context.adopted_source(plan_ref) if context is not None else _adopted_source_record(conn, plan_ref)
    return None if evidence is None else tuple(evidence[key] for key in ("basis", "audit", "tables", "arranged", "selected"))


def _adopted_source_record(conn, plan_ref, *, context=None):
    from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

    from .adoption_baseline import read_adoption_source

    locator = context.resolve(plan_ref) if context is not None else WorkbenchPlanIdentityRepository(conn).resolve_plan(plan_ref)
    if locator.scenario_id is not None or locator.plan_role != ROLE_ADOPTED:
        return None
    history = context.history(locator.version) if context is not None else WorkbenchPlanBaselineRepository(conn).get_history_result_summary(locator.version)
    return read_adoption_source(conn, plan_ref=plan_ref, version=locator.version, history=history, context=context)


def _source_quantities(basis, arranged, source):
    # Only the audited source can supply target work; current batch joins cannot.
    if basis == "candidate_adoption":
        facts = source
        refs = {key: ref for ref, key in facts.operations.items()}
        result = {}
        for item in arranged:
            op = facts.tables["BatchOperations"][item["op_id"]]
            result[item["op_id"]] = _captured_quantities(op, facts.tables["Batches"][op["batch_id"]],
                                                       facts.execution.get(refs[item["op_id"]]), "run_admission")
        return result
    _, _, saved = source.source
    return {row["original"]["operation"]["id"]: _captured_quantities(
        row["original"]["operation"], row["original"]["batch"], row["original"]["execution"], "trial_creation")
        for row in saved}


def project_tasks(plan_ref, rows, task_refs, operation_refs, resources, *, conn=None, facts=None, context=None):
    tasks = []
    quantities, quantity_reason, origins = _adopted_task_facts(conn, plan_ref, context=context) if rows else ({}, None, None)
    if facts is not None:
        facts["resource_directory"] = [resource for row in rows for resource in
            (origins or {}).get(row["op_id"], {}).get("resource_directory", [])]
    for row in rows:
        start, end = (tuple(value.replace(" ", "T") for value in context.row_times(plan_ref, row)) if context is not None else
                      (public_time(row["start_time"]), public_time(row["end_time"])))
        if start > end or (start == end and not row.get("_point_work")):
            raise WorkbenchCommandRejected("plan_unavailable", "工序安排的起止时间无效，请核对计划资料。")
        if row["schedule_id"] not in task_refs or row["op_id"] not in operation_refs:
            raise WorkbenchCommandRejected("identity_missing", "安排编号缺失，请刷新后重试。")
        piece = row.get("piece_id")
        if piece is not None:
            piece = _required_text(piece)
        presentation = quantities.get(row["op_id"], {"piece_id": piece, "quantity": None, "batch_quantity": None,
                                                    "quantity_basis": "unknown", "quantity_reason": quantity_reason})
        supplier = origins.get(row["op_id"], {}).get("supplier") if origins is not None else None
        # Schedule has no supplier assignment: only the adopted source can prove it.
        supplier_ref = supplier["ref"] if supplier is not None else None
        tasks.append({"task_ref": task_refs[row["schedule_id"]], "operation_ref": operation_refs[row["op_id"]],
                      "plan_ref": plan_ref, "batch_id": _required_text(row["batch_id"]),
                      "sequence": _sequence(row["seq"]), "process_label": _required_text(row["op_type_name"]),
                      **presentation,
                      "machine_ref": _resource_ref(row, "machine", resources),
                      "operator_ref": _resource_ref(row, "operator", resources),
                      "supplier_ref": supplier_ref, "start": start, "end": end})
        if start == end:
            from datetime import datetime
            tasks[-1].update(point_event_dto(datetime.fromisoformat(start), datetime.fromisoformat(end)))
    if len({task["task_ref"] for task in tasks}) != len(tasks):
        raise WorkbenchCommandRejected("task_binding_invalid", "计划里有安排编号重复，确认不了完整范围。请刷新后重试。")
    return tasks
