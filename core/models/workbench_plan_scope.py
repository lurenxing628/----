"""Strict public read scopes; internal seek positions never belong in this model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn, Optional

from core.models.workbench_command import WorkbenchCommandRejected

MAX_PLAN_TASKS = 10000
MAX_PLAN_RESPONSE_BYTES = 8 * 1024 * 1024
PLAN_READ_TTL_SECONDS = 900


def invalid_scope(message) -> NoReturn:
    raise WorkbenchCommandRejected("invalid_input", message, 400)


def plan_reference(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise WorkbenchCommandRejected("entity_not_found", "所选计划已失效，请回到计划列表重新选择。", 404)
    return value


def local_time(value) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", value) is None:
        invalid_scope("时间格式不对，请按 2026-09-13 08:30:00 这样填写。")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "时间不存在，请核对日期和时分秒。", 400) from exc
    return value


@dataclass(frozen=True)
class PlanCatalogScope:
    collection: str = "history"
    size: int = 20

    def __post_init__(self):
        if self.collection not in ("history", "scenario"):
            invalid_scope("计划列表只能选历史版本或已保存的试调方案。")
        if type(self.size) is not int or not 1 <= self.size <= 50:
            invalid_scope("计划列表每页只能是 1 至 50 条。")

    def scope(self):
        return {"source": "production", "kind": "plan_catalog", "collection": self.collection, "size": self.size}


@dataclass(frozen=True)
class PlanReadScope:
    plan_ref: str
    range_start: Optional[str] = None
    range_end: Optional[str] = None

    def __post_init__(self):
        plan_reference(self.plan_ref)
        if (self.range_start is None) != (self.range_end is None):
            invalid_scope("起止时间必须同时提供；不提供时读取该计划的完整真实范围。")
        if self.range_start is not None:
            start = local_time(self.range_start)
            end = local_time(self.range_end)
            if start >= end:
                invalid_scope("时间范围必须起点早于终点。")

    def scope(self):
        return {"source": "production", "kind": "plan_workspace", "plan_ref": self.plan_ref,
                "range_start": self.range_start, "range_end": self.range_end}

    def time_scope(self, span):
        return {"range_start": self.range_start or span["start"], "range_end": self.range_end or span["end"],
                "selection": "overlap", "boundary": "half_open", "time_basis": "factory_local"}
