"""Project reliable static facts without inventing the prototype's readiness ratio."""

import logging
import sqlite3
from typing import Dict, Optional

from core.services.process.workflow_state import workflow_snapshot

_STAGES = ("route", "source", "hours")
_PROCESS_COUNTS = _STAGES + ("ready", "legacy", "managed", "legacy_route_present",
                            "route_confirmed", "source_confirmed", "hours_confirmed")
_PROCESS_BASIS = "当前模板内容绑定的工艺确认；存量路线资料不等于人工确认，工艺确认完成不等于可排产。"


def _checked_workflow(record):
    workflow = record.get("workflow") if isinstance(record, dict) else None
    if not isinstance(workflow, dict):
        raise RuntimeError("Missing process workflow projection.")
    origin, stage = workflow.get("origin"), workflow.get("stage")
    if origin not in ("legacy", "managed") or stage not in _STAGES + ("ready",):
        raise RuntimeError("Invalid process workflow origin or stage.")
    if type(workflow.get("ready")) is not bool or workflow["ready"] != (stage == "ready"):
        raise RuntimeError("Inconsistent process workflow readiness.")
    expected = _workflow_stage_states(origin, stage)
    for name, states in zip(_STAGES, expected):
        _check_stage_confirmation(workflow.get(name), states)
    return workflow


def _workflow_stage_states(origin, stage):
    expected = {"route": (("missing", "unconfirmed"), ("locked",), ("locked",)),
                "source": (("confirmed",), ("unconfirmed",), ("locked",)),
                "hours": (("confirmed",), ("confirmed",), ("unconfirmed",)),
                "ready": (("confirmed",), ("confirmed",), ("confirmed",))}[stage]
    if origin == "legacy":
        if stage not in ("route", "source"):
            raise RuntimeError("Legacy process facts cannot imply confirmation.")
        expected = (("missing",), ("locked",), ("locked",)) if stage == "route" else (
            ("present",), ("unconfirmed",), ("locked",))
    return expected


def _check_stage_confirmation(row, states):
    if not isinstance(row, dict) or row.get("state") not in states:
        raise RuntimeError("Inconsistent process stage projection.")
    stamp, person = row.get("confirmed_at"), row.get("confirmed_by")
    if row["state"] == "confirmed":
        if not isinstance(stamp, str) or not stamp.strip() or (person is not None and (
                not isinstance(person, str) or not person.strip())):
            raise RuntimeError("Missing process confirmation evidence.")
    elif stamp is not None or person is not None:
        raise RuntimeError("Unconfirmed process stage contains confirmation evidence.")


def process_readiness(conn, total, logger=None):
    """Aggregate the domain's bulk snapshot; never read or confirm individual parts."""
    counts: Dict[str, Optional[int]] = dict.fromkeys(_PROCESS_COUNTS, None)
    counts["total"] = total if type(total) is int and total >= 0 else None
    try:
        snapshot = workflow_snapshot(conn)
        if not isinstance(snapshot, dict) or counts["total"] is None or len(snapshot) != total:
            raise RuntimeError("Process workflow catalog does not match resource counts.")
        verified: Dict[str, int] = dict.fromkeys(_PROCESS_COUNTS, 0)
        for record in snapshot.values():
            workflow = _checked_workflow(record)
            verified[workflow["stage"]] += 1
            verified[workflow["origin"]] += 1
            verified["legacy_route_present"] += workflow["origin"] == "legacy" and workflow["route"]["state"] == "present"
            for stage in _STAGES:
                verified[stage + "_confirmed"] += workflow[stage]["state"] == "confirmed"
    except (RuntimeError, sqlite3.DatabaseError):
        (logger or logging.getLogger(__name__)).exception("Process readiness could not verify the workflow snapshot; no records were repaired.")
        return {"status": "unavailable", "counts": counts, "basis": _PROCESS_BASIS,
                "issues": [{"code": "process_workflow_unavailable", "message": "工艺阶段无法核实：确认记录、永久引用或存储契约不完整；未自动修补资料。"}]}
    counts.update(verified)
    return {"status": "zero" if total == 0 else "ready" if counts["ready"] == total else "pending",
            "counts": counts, "issues": [], "basis": _PROCESS_BASIS}


def _metric_item(group):
    counts, issues = dict(group["counts"]), list(group["issues"])
    unavailable = any(issue["code"] in ("resource_metrics_unavailable", "resource_availability_unavailable") for issue in issues)
    status = "unavailable" if unavailable else "unknown" if counts.get("unknown") else "zero" if counts.get("total") == 0 else "recorded"
    return {"status": status, "counts": counts, "issues": issues, "basis": group["basis"]}


def resource_readiness(counts, metrics, calendar, process):
    items = {key: _metric_item(metrics["groups"][group]) for key, group in (
        ("op_int", "internal_op_type"), ("machine", "machine"), ("operator", "operator"),
        ("op_ext", "external_op_type"), ("supplier", "supplier"))}
    items["process"] = process
    items["material"] = {"status": "zero" if counts["material"] == 0 else "recorded", "counts": {"total": counts["material"]},
                         "issues": [], "basis": "物料主数据记录量；未按批次需求核实齐套。"}
    items["calendar"] = {"status": "unavailable" if calendar["status"] != "known" else
                          "not_configured" if not calendar["stats"]["configured_days"] else "recorded",
                         "counts": dict(calendar["stats"]), "basis": calendar["basis"],
                         "issues": calendar["stats"]["issues"] + [issue for day in calendar["days"] for issue in day["issues"]]}
    return {"status": "unknown", "ratio": None, "basis": "static_resource_facts_not_schedule_precheck",
            "message": "整体就绪度未知：静态资料不是排产前检查；工艺确认完成也不代表物料齐套或资源时段可用。", "items": items}
