"""Project reliable static facts without inventing the prototype's readiness ratio."""

import logging
import sqlite3
from typing import Dict, Optional

from core.errors import AppError, ErrorCode
from core.services.process.workflow_state import workflow_snapshot

_STAGES = ("route", "source", "hours")
_PROCESS_COUNTS = _STAGES + ("ready", "legacy", "managed", "legacy_route_present",
                            "route_confirmed", "source_confirmed", "hours_confirmed")
_PROCESS_BASIS = "零件工艺确认进度。"


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
            workflow = record["workflow"]
            verified[workflow["stage"]] += 1
            verified[workflow["origin"]] += 1
            verified["legacy_route_present"] += workflow["origin"] == "legacy" and workflow["route"]["state"] == "present"
            for stage in _STAGES:
                verified[stage + "_confirmed"] += workflow[stage]["state"] == "confirmed"
    except (RuntimeError, sqlite3.DatabaseError, AppError) as exc:
        # Only the repository's translated read failure degrades; any other AppError is a caller bug and must surface.
        if isinstance(exc, AppError) and exc.code is not ErrorCode.DB_QUERY_ERROR:
            raise
        (logger or logging.getLogger(__name__)).exception("Process readiness could not verify the workflow snapshot; no records were repaired.")
        return {"status": "unavailable", "counts": counts, "basis": _PROCESS_BASIS,
                "issues": [{"code": "process_workflow_unavailable", "message": "工艺确认记录读取失败，请联系维护人员核对。"}]}
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
                         "issues": [], "basis": "这里只数物料资料有多少条，没有按批次需求核对齐套。"}
    items["calendar"] = {"status": "unavailable" if calendar["status"] != "known" else
                          "not_configured" if not calendar["stats"]["configured_days"] else "recorded",
                         "counts": dict(calendar["stats"]), "basis": calendar["basis"],
                         "issues": calendar["stats"]["issues"] + [issue for day in calendar["days"] for issue in day["issues"]]}
    return {"status": "unknown", "ratio": None, "basis": "static_resource_facts_not_schedule_precheck",
            "message": "整体就绪度暂无数据；这里只汇总静态资料，不代表排产检查结果。", "items": items}
