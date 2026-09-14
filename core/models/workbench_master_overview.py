"""Strict, page-independent read scope for the master-data overview."""

import json
import re
from dataclasses import dataclass, field

from core.models.workbench_command import WorkbenchCommandRejected

DOMAINS = (("part", "零件"), ("route", "工艺路线"), ("opType", "工种"),
           ("equipment", "设备"), ("personnel", "人员"), ("material", "物料"),
           ("supplier", "供应商"), ("calendar", "日历配置"))
STATUS = {"attention": "待维护", "checked": "已检查", "inactive": "停用", "unknown": "未检查"}
COLUMNS = {"entities": ("business_code", "label", "domain", "status", "filled_fields", "checked_fields",
                        "relation_count", "issue_count", "summary"),
           "issues": ("business_code", "label", "domain", "status", "title", "evidence", "action", "rule")}


def invalid(message):
    raise WorkbenchCommandRejected("invalid_input", message, 400)


def _validate_search_text(value, message):
    if type(value) is not str or len(value) > 1000 or "\x00" in value:
        invalid(message)


def public_ref(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{48}", value) is not None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            invalid("查询条件里有重复的项，请重新选择。")
        result[key] = value
    return result


def read_scope(text):
    if len(text) > 65536:
        invalid("主数据筛选范围过长。")
    try:
        value = json.loads(text, object_pairs_hook=unique_object)
    except (ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("invalid_input", "资料总览的查询条件格式不对，请刷新页面后重试。", 400) from exc
    allowed = {"view", "domain", "status", "query", "sort", "direction", "size", "column_filters"}
    if type(value) is not dict or set(value) - allowed:
        invalid("资料总览的查询条件含有不支持的项，请刷新页面后重试。")
    return MasterOverviewScope(**value)


@dataclass(frozen=True)
class MasterOverviewScope:
    view: str = "issues"
    domain: str = "all"
    status: str = "all"
    query: str = ""
    sort: str = "issue_count"
    direction: str = "desc"
    size: int = 20
    column_filters: dict = field(default_factory=dict)

    def __post_init__(self):
        options = ((self.view, ("issues", "entities")), (self.domain, ("all",) + tuple(key for key, _ in DOMAINS)),
                   (self.status, ("all",) + tuple(STATUS)),
                   (self.sort, ("issue_count", "business_code", "label", "relation_count")),
                   (self.direction, ("asc", "desc")))
        if any(type(value) is not str or value not in allowed for value, allowed in options):
            invalid("资料清单、资料类别、检查状态或排序不正确，请重新选择。")
        _validate_search_text(self.query, "搜索内容最多 1000 字。")
        if type(self.size) is not int or self.size not in (20, 50, 100):
            invalid("每页只能选 20、50 或 100 条。")
        if type(self.column_filters) is not dict or set(self.column_filters) - set(COLUMNS[self.view]):
            invalid("资料列表的筛选列不正确，请重新选择筛选条件。")
        for value in self.column_filters.values():
            _validate_search_text(value, "列筛选内容最多 1000 字。")

    def scope(self):
        return {"kind": "master_overview", **self.values()}

    def values(self):
        return {"view": self.view, "domain": self.domain, "status": self.status, "query": self.query,
                "sort": self.sort, "direction": self.direction, "size": self.size,
                "column_filters": dict(self.column_filters)}
