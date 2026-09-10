"""Finite, explicit list scopes shared by reads, selections and previews."""

import math

from core.models.workbench_batch import MAX_INTEGER, READY, SORTS, STATUSES, object_fields
from core.models.workbench_command import WorkbenchCommandRejected


def batch_scope(values):
    allowed = ("query", "status", "ready_status", "page", "size", "sort", "direction", "snapshot_ref", "column_filters", "focus", "batch_ids")
    object_fields(values, allowed)
    scope = {"query": "", "status": None, "ready_status": None, "sort": "business_code", "direction": "asc",
             "page": 1, "size": 20, "column_filters": {}, "focus": None, "batch_ids": None, **values}
    _validate_pagination(scope)
    _validate_selection(scope)
    filters = object_fields(scope["column_filters"], SORTS)
    for items in filters.values():
        _validate_filter_values(items)
    _validate_batch_ids(scope["batch_ids"])
    scope["query"] = scope["query"].strip()
    return scope


def _validate_pagination(scope):
    for key in ("page", "size"):
        if type(scope[key]) is not int or not 1 <= scope[key] <= (100 if key == "size" else 1000000):
            raise WorkbenchCommandRejected("invalid_input", "页码或每页条数不正确。", 400)


def _validate_selection(scope):
    if (not isinstance(scope["query"], str) or len(scope["query"]) > 200
            or scope["status"] not in (None, "") + STATUSES or scope["ready_status"] not in (None, "") + READY
            or scope["sort"] not in SORTS or scope["direction"] not in ("asc", "desc")
            or scope["focus"] not in (None, "", "gaps", "unready")):
        raise WorkbenchCommandRejected("invalid_input", "列表筛选或排序不正确。", 400)


def _validate_filter_values(items):
    if (not isinstance(items, list) or len(items) > 5000
            or any(value is not None and type(value) not in (str, int, float) for value in items)
            or any(type(value) in (int, float) and (abs(value) > MAX_INTEGER or not math.isfinite(value)) for value in items)):
        raise WorkbenchCommandRejected("invalid_input", "列筛选必须为明确的值集合。", 400)


def _validate_batch_ids(ids):
    if ids is not None and (not isinstance(ids, list) or len(ids) > 5000 or any(not isinstance(key, str) or not key for key in ids)):
        raise WorkbenchCommandRejected("invalid_input", "批次定位范围不正确。", 400)


def snapshot_scope(scope):
    return {"kind": "batch", **{key: value for key, value in scope.items() if key not in ("page", "snapshot_ref")}}
