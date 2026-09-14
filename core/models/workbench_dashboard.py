"""Dashboard wire contract. Handling state never stands in for risk evaluation."""

import re
from dataclasses import dataclass
from typing import Any, Dict

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json

MAX_ROWS = 10000
MAX_FACT_ROWS = 50000
MAX_BYTES = 8 * 1024 * 1024
CATEGORIES = ("delivery", "actual", "external", "downtime", "material", "candidate")
STATUSES = ("new", "following", "awaiting_verification", "closed")
STATUS_LABELS = dict(zip(STATUSES, ("待分析", "跟进中", "待验证", "已关闭")))
HANDLING_FIELDS = ("owner", "deadline", "action", "remark", "completed_at",
                   "completion_evidence", "evidence_reference_text", "evidence_ref")


def reference(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise WorkbenchCommandRejected("entity_not_found", "这条记录已失效，请刷新后重新选择。", 404)
    return value


def bounded(value, limit=MAX_ROWS):
    if len(value) > limit:
        raise WorkbenchCommandRejected("query_too_large", "值班台完整来源超过读取上限，未截断或改报零风险。", 413)
    return value


def payload_size(value):
    bounded(canonical_json(value).encode("utf-8"), MAX_BYTES)
    return value


def empty_handling() -> Dict[str, Any]:
    return dict(status="new", **{key: None for key in HANDLING_FIELDS})


def allowed_transitions(status):
    return [] if status == "closed" else list(STATUSES)


@dataclass(frozen=True)
class DashboardQuery:
    category: str = "all"
    status: str = "all"
    query: str = ""
    sort: str = "subject"
    direction: str = "asc"
    number: int = 1
    size: int = 20
    source: str = "production"

    def __post_init__(self):
        if (self.source != "production" or self.category not in ("all",) + CATEGORIES
                or self.status not in ("all", "open") + STATUSES
                or self.sort not in ("subject", "category", "status", "deadline")
                or self.direction not in ("asc", "desc") or type(self.query) is not str
                or len(self.query) > 200 or "\x00" in self.query
                or type(self.number) is not int or not 1 <= self.number <= 100000
                or type(self.size) is not int or not 1 <= self.size <= 100):
            raise WorkbenchCommandRejected("invalid_input", "值班台筛选或分页参数无效。", 400)

    def scope(self):
        return {"kind": "dashboard", "source": self.source, "category": self.category,
                "status": self.status, "query": self.query.strip(), "sort": self.sort,
                "direction": self.direction, "size": self.size}


def page(items, number, size, sort):
    total = len(items)
    pages = max(1, (total + size - 1) // size)
    if number > pages:
        raise WorkbenchCommandRejected("invalid_input", "页码超出原读取范围，未跳回第一页。", 400)
    return items[(number - 1) * size:number * size], {
        "number": number, "size": size, "total": total, "pages": pages, "sort": sort}
