"""Allowlisted plan/task DTOs. Private catalog errors and locators never serialize."""

from __future__ import annotations

from core.models.schedule_plan_role import ROLE_ADOPTED
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_plan_scope import MAX_PLAN_RESPONSE_BYTES
from data.repositories.schedule_time_sql import parse_dt_for_sql

from .zero_duration import point_event_dto

_REASONS = {
    "summary_invalid": "排产摘要无效，无法确认计划完整性。",
    "summary_missing": "排产摘要缺失，无法确认计划完整性。",
    "plan_unavailable": "计划角色关系或明细无效，暂不可查看。",
    "history_missing": "场景的基础排产历史不存在。",
    "scenario_not_active": "场景已发布、过期或作废，不能作为当前预览。",
    "scenario_unavailable": "场景的基础关系或明细无效，暂不可查看。",
    "plan_capacity_exceeded": "计划或必要基础计划的明细超过本批读取上限，尚未验证完整性。",
    "plan_binding_invalid": "计划角色或基础计划的绑定已失效，暂不可查看。",
    "identity_missing": "计划永久引用缺失，读取不会自动补建。",
    "identity_invalid": "计划永久引用与当前对象不一致，暂不可查看。",
    "source_missing": "计划源对象已不存在，未自动切换到其他计划。",
}


def _wire_positive_int64(value):
    if type(value) is not int or not 0 < value <= (1 << 63) - 1:
        return None
    return value if value <= (1 << 53) - 1 else str(value)


def _public_reasons(codes):
    return [{"code": code if code in _REASONS else "plan_unavailable",
             "message": _REASONS.get(code, _REASONS["plan_unavailable"])} for code in codes]


def project_plan(entry, plan_ref):
    identity = entry.plan_identity
    version = _wire_positive_int64(entry.locator.version)
    if entry.can_view and version is None:
        raise WorkbenchCommandRejected("plan_unavailable", "计划版本号无效，不能标记为可查看。")
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
    version = _wire_positive_int64(locator.version)
    return {"plan_ref": plan_ref, "version": version, "kind": kind,
            "is_current_official": False, "display_name": display_name, "completeness": completeness,
            "capabilities": {"view": False, "export": False, "edit_draft": False, "adopt": False, "report_actual": False},
            "blocked_reasons": _public_reasons(reason_codes)}


def project_capacity_blocked_plan(locator, plan_ref, display_name):
    return project_unavailable_plan(locator, plan_ref, display_name, ("plan_capacity_exceeded",), completeness="unknown")


def public_time(value):
    parsed = parse_dt_for_sql(value)
    if parsed is None:
        raise WorkbenchCommandRejected("plan_unavailable", "计划含无效时间明细，未返回截断或替代数据。")
    return parsed.replace(" ", "T")


def task_span(rows):
    if not rows:
        return None
    return {"start": min(public_time(row["start_time"]) for row in rows),
            "end": max(public_time(row["end_time"]) for row in rows)}


def _required_text(value):
    if type(value) is not str or not value.strip():
        raise WorkbenchCommandRejected("plan_unavailable", "任务的业务批次或工序信息缺失，无法完整投影。")
    return value


def _sequence(value):
    wire = _wire_positive_int64(value)
    if wire is None:
        raise WorkbenchCommandRejected("plan_unavailable", "任务工序号无效，未自动改号。")
    return wire


def _resource_ref(row, kind, identities):
    key = row[kind + "_id"]
    if key is None or key == "":
        return None
    identity = identities[kind].get(str(key))
    if identity is None:
        raise WorkbenchCommandRejected("identity_missing", "任务关联资源的永久引用缺失，读取不会补建身份。")
    return identity.ref


def _captured_quantities(operation, batch, execution, basis):
    from .run_candidate_values import number

    gaps = []
    piece = operation.get("piece_id")
    valid_piece = "piece_id" in operation and (piece is None or type(piece) is str and piece.strip() and "\x00" not in piece)
    quantity = number(execution.get("target_quantity"), "quantity", gaps, integer=True) if type(execution) is dict else None
    batch_quantity = number(batch.get("quantity"), "batch_quantity", gaps, integer=True)
    valid = (valid_piece and type(execution) is dict
             and execution.get("target_basis") == ("piece" if piece is not None else "batch"))
    return {"piece_id": piece if valid_piece else None, "quantity": quantity if valid else None,
            "batch_quantity": batch_quantity, "quantity_basis": basis,
            "quantity_reason": None if valid and quantity is not None and not gaps else "plan_target_invalid"}


def _adopted_quantities(conn, plan_ref):
    from core.models.workbench_plan_reference import WorkbenchPlanReferenceError

    from .plan_adoption_baseline_values import AdoptionBaselineUnavailable, require

    if conn is None:
        return {}, "plan_target_not_recorded"
    try:
        evidence = _quantity_evidence(conn, plan_ref)
        if evidence is None:
            return {}, "plan_target_not_recorded"
        basis, audit, arranged = evidence
        result = _source_quantities(conn, basis, audit, arranged)
        require(set(result) == {row["op_id"] for row in arranged}, "quantity.complete_operation_set")
        return result, None
    except (AdoptionBaselineUnavailable, WorkbenchPlanReferenceError):
        return {}, "plan_target_unavailable"
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        return {}, "plan_target_unavailable"
    except (KeyError, TypeError, ValueError, OverflowError):
        return {}, "plan_target_unavailable"


def _quantity_evidence(conn, plan_ref):
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

    from .plan_adoption_baseline import _audit
    from .plan_adoption_baseline_identity import verify_arranged, verify_capture
    from .plan_adoption_baseline_sources import candidate_source, decoded_baseline, trial_source
    from .plan_adoption_baseline_values import require, same

    locator = WorkbenchPlanIdentityRepository(conn).resolve_plan(plan_ref)
    if locator.scenario_id is not None or locator.plan_role != ROLE_ADOPTED:
        return None
    history = conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (locator.version,)).fetchone()
    recorded = _audit(conn, plan_ref, locator.version, None if history is None else {"result_summary": history[0]})
    if recorded is None:
        return None
    basis, audit, _ = recorded
    source = candidate_source if basis == "candidate_adoption" else trial_source
    baseline, tables, arranged = source(conn, audit)
    baseline = decoded_baseline(baseline)
    require(same((baseline["plan_ref"], baseline["version"]), (audit["baseline_ref"], audit["baseline_version"])),
            "quantity.adoption_baseline")
    verify_capture(baseline, tables)
    require(len(arranged) == audit["row_count"], "quantity.adoption_complete_rows")
    verify_arranged(conn, plan_ref, locator.version, tables, arranged)
    return basis, audit, arranged


def _source_quantities(conn, basis, audit, arranged):
    from .run_candidate_facts import GenerationFacts
    from .run_candidate_storage import CandidateStore
    from .trial_adoption_storage import load_saved_scenario

    # Only the audited source can supply target work; current batch joins cannot.
    if basis == "candidate_adoption":
        facts = GenerationFacts(CandidateStore(conn).capture(audit["run_ref"]))
        refs = {key: ref for ref, key in facts.operations.items()}
        result = {}
        for item in arranged:
            op = facts.tables["BatchOperations"][item["op_id"]]
            result[item["op_id"]] = _captured_quantities(op, facts.tables["Batches"][op["batch_id"]],
                                                       facts.execution.get(refs[item["op_id"]]), "run_admission")
        return result
    _, _, saved = load_saved_scenario(conn, audit["scenario_ref"])
    return {row["original"]["operation"]["id"]: _captured_quantities(
        row["original"]["operation"], row["original"]["batch"], row["original"]["execution"], "trial_creation")
        for row in saved}


def project_tasks(plan_ref, rows, task_refs, operation_refs, resources, *, conn=None):
    tasks = []
    quantities, quantity_reason = _adopted_quantities(conn, plan_ref) if rows else ({}, None)
    for row in rows:
        start, end = public_time(row["start_time"]), public_time(row["end_time"])
        if start > end or (start == end and not row.get("_point_work")):
            raise WorkbenchCommandRejected("plan_unavailable", "计划任务起止时间无效，未返回替代数据。")
        if row["schedule_id"] not in task_refs or row["op_id"] not in operation_refs:
            raise WorkbenchCommandRejected("identity_missing", "计划任务永久引用缺失，读取不会补建身份。")
        piece = row.get("piece_id")
        if piece is not None:
            piece = _required_text(piece)
        presentation = quantities.get(row["op_id"], {"piece_id": piece, "quantity": None, "batch_quantity": None,
                                                    "quantity_basis": "unknown", "quantity_reason": quantity_reason})
        tasks.append({"task_ref": task_refs[row["schedule_id"]], "operation_ref": operation_refs[row["op_id"]],
                      "plan_ref": plan_ref, "batch_id": _required_text(row["batch_id"]),
                      "sequence": _sequence(row["seq"]), "process_label": _required_text(row["op_type_name"]),
                      **presentation,
                      "machine_ref": _resource_ref(row, "machine", resources),
                      "operator_ref": _resource_ref(row, "operator", resources),
                      "supplier_ref": _resource_ref(row, "supplier", resources), "start": start, "end": end})
        if start == end:
            from datetime import datetime
            tasks[-1].update(point_event_dto(datetime.fromisoformat(start), datetime.fromisoformat(end)))
    if len({task["task_ref"] for task in tasks}) != len(tasks):
        raise WorkbenchCommandRejected("task_binding_invalid", "计划任务引用重复，无法确认完整任务范围。")
    return tasks


def check_payload_size(data):
    if len(canonical_json(data).encode("utf-8")) > MAX_PLAN_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "计划查询结果超出本批读取大小上限，未返回截断结果。", 413)
    return data
