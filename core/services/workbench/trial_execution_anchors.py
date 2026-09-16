"""Use the scheduler's execution seeds when a trial includes actual production."""

from types import SimpleNamespace

from core.errors import AppError
from core.models.workbench_trial import issue
from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows
from core.services.scheduler.schedule_service import ScheduleService

from .run_input_projection_codec import restore_execution_projections


def execution_anchors(conn, rows, live):
    selected = {row["operation_ref"] for row in rows}
    if not any(ref in selected and (value["first_actual_start"] or value["reports"] or value["legacy_facts"])
               for ref, value in live["execution"].items()):
        return {}
    version = live["baseline"]["version"]
    if version is None:
        raise ValueError("Actual production has no official plan")
    svc = ScheduleService(conn)
    prior_ids = set(_latest_plan_rows(svc, version))
    tables = live["facts"]["tables"]
    prior_refs = {row["ref"] for row in tables["WorkbenchPlanSourceRefs"]
                  if row["kind"] == "operation" and row["active"] == 1 and int(row["source_key"]) in prior_ids}
    projections = restore_execution_projections([live["execution"][ref] for ref in sorted(prior_refs)])
    operations = [SimpleNamespace(**row["original"]["operation"]) for row in rows]
    _, _, completed, seeds, _, _ = build_execution_guardrails_from_projections(
        svc, operations, prev_version=version, execution_projections=projections)
    refs = {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
    result = {}
    for seed in seeds:
        arrangement = {"start": seed["start_time"].isoformat(timespec="seconds"),
                       "end": seed["end_time"].isoformat(timespec="seconds")}
        for kind in ("machine", "operator"):
            key = seed[kind + "_id"]
            arrangement[kind + "_id"] = key
            arrangement[kind + "_ref"] = refs[kind, key]
        complete = seed["op_id"] in completed
        result[seed["op_id"]] = {"arrangement": arrangement,
            "basis": "completed_actuals" if complete else "started_actuals",
            "message": "已完工，按实际开完工时间和资源固定。" if complete else "已开工，固定实际开工和资源；预计完工按原计划时长计算。"}
    return result


def anchor_issue(exc):
    message = str(exc) if isinstance(exc, AppError) else "已开工工序的实际时间或资源不完整，请检查现场记录后重新发起试调。"
    return issue("execution_anchor_unproven", message)


def attach_execution_anchors(conn, rows, live):
    try:
        anchors = execution_anchors(conn, rows, live)
    except (AppError, ValueError, TypeError, KeyError, OverflowError) as exc:
        return [anchor_issue(exc)]
    for row in rows:
        anchor = anchors.get(row["original"]["operation"]["id"])
        if anchor is not None:
            row["original"]["execution_anchor"] = anchor
            row["current"] = dict(anchor["arrangement"])
    return []
