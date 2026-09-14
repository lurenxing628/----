"""Strict public scopes for the durable run directory, not formal plan history."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import NoReturn, Optional

from core.models.workbench_command import WorkbenchCommandRejected

STATES = ("queued", "running", "complete", "partial", "failed", "interrupted")
TERMINAL_STATES = frozenset(STATES[2:])
MAX_DIRECTORY_ROWS = 100000
MAX_DIRECTORY_BYTES = 128 * 1024 * 1024
MAX_DOCUMENT_BYTES = 32 * 1024 * 1024


def reject(code, message, status=400) -> NoReturn:
    raise WorkbenchCommandRejected(code, message, status)


def inconsistent() -> NoReturn:
    reject("run_result_inconsistent", "排产记录、提交结果和候选方案的条数对不上，这里不返回结果。请刷新重试；仍不行请联系维护人员。", 500)


def local_date(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("Expected factory-local date")
    return date.fromisoformat(value)


def local_datetime(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?", value) is None:
        raise ValueError("Expected factory-local datetime")
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class RunHistoryScope:
    state: str = "all"
    accepted_from: Optional[str] = None
    accepted_to: Optional[str] = None
    sort: str = "accepted_at"
    order: str = "desc"
    page: int = 1
    size: int = 20

    def __post_init__(self):
        if (self.state not in ("all",) + STATES or self.sort not in ("accepted_at", "started_at", "finished_at")
                or self.order not in ("asc", "desc") or type(self.page) is not int or not 1 <= self.page <= 1000000
                or type(self.size) is not int or not 1 <= self.size <= 50):
            reject("invalid_input", "运行历史筛选、排序或分页参数无效，未忽略条件。")
        if self.accepted_from is not None or self.accepted_to is not None:
            try:
                if local_date(self.accepted_from) > local_date(self.accepted_to):
                    raise ValueError("Reversed dates")
            except (ValueError, TypeError):
                reject("invalid_input", "提交起止日期要一起填，请按 2026-09-13 这样填写，起日不能晚于止日。")

    def scope(self):
        return {"source": "production", "kind": "scheduling-run-history", "state": self.state,
                "accepted_from": self.accepted_from, "accepted_to": self.accepted_to,
                "sort": self.sort, "order": self.order, "size": self.size}
