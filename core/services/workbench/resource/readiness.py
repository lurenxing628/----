"""Project reliable static facts without inventing the prototype's readiness ratio."""

import logging
import sqlite3
from typing import Dict, Optional

from core.errors import AppError, ErrorCode
from data.repositories.part_repo import PartRepository

_STAGES = ("route", "source", "hours")
_PROCESS_COUNTS = _STAGES + (
    "ready",
    "legacy",
    "managed",
    "legacy_route_present",
    "route_confirmed",
    "source_confirmed",
    "hours_confirmed",
)
_PROCESS_BASIS = "零件工艺确认进度。"


def process_readiness(conn, total, logger=None):
    """Aggregate inline process confirmation columns in a single SQL query."""
    counts: Dict[str, Optional[int]] = dict.fromkeys(_PROCESS_COUNTS, None)
    counts["total"] = total if type(total) is int and total >= 0 else None
    try:
        values = PartRepository(conn, logger=logger).process_readiness_counts()
    except (sqlite3.DatabaseError, AppError) as exc:
        if isinstance(exc, AppError) and exc.code is not ErrorCode.DB_QUERY_ERROR:
            raise
        (logger or logging.getLogger(__name__)).exception(
            "Process readiness could not aggregate part confirmations; no records were repaired."
        )
        return {
            "status": "unavailable",
            "counts": counts,
            "basis": _PROCESS_BASIS,
            "issues": [{"code": "process_workflow_unavailable", "message": "工艺确认记录读取失败，请联系维护人员核对。"}],
        }
    for index, key in enumerate(_PROCESS_COUNTS):
        counts[key] = values[index]
    return {
        "status": "zero" if total == 0 else "ready" if counts["ready"] == total else "pending",
        "counts": counts,
        "issues": [],
        "basis": _PROCESS_BASIS,
    }


def _metric_item(group):
    counts, issues = group["counts"], group["issues"]
    unavailable = any(
        issue["code"] in ("resource_metrics_unavailable", "resource_availability_unavailable") for issue in issues
    )
    status = "unavailable" if unavailable else "zero" if counts.get("total") == 0 else "recorded"
    return {"status": status, "counts": counts, "issues": issues, "basis": group["basis"]}


def resource_readiness(counts, metrics, calendar, process):
    items = {
        key: _metric_item(metrics["groups"][group])
        for key, group in (
            ("op_int", "internal_op_type"),
            ("machine", "machine"),
            ("operator", "operator"),
            ("op_ext", "external_op_type"),
            ("supplier", "supplier"),
        )
    }
    items["process"] = process
    items["material"] = {
        "status": "zero" if counts["material"] == 0 else "recorded",
        "counts": {"total": counts["material"]},
        "issues": [],
        "basis": "这里只数物料资料有多少条，没有按批次需求核对齐套。",
    }
    items["calendar"] = {
        "status": (
            "unavailable"
            if calendar["status"] != "known"
            else "not_configured"
            if not calendar["stats"]["configured_days"]
            else "recorded"
        ),
        "counts": calendar["stats"],
        "basis": calendar["basis"],
        "issues": calendar["stats"]["issues"] + [issue for day in calendar["days"] for issue in day["issues"]],
    }
    return {
        "status": "unknown",
        "ratio": None,
        "basis": "static_resource_facts_not_schedule_precheck",
        "message": "整体就绪度暂无数据；这里只汇总静态资料，不代表排产检查结果。",
        "items": items,
    }
