"""Finite, explicit list scopes shared by reads, selections and previews."""

from core.models.enums import BATCH_STATUS_VALUES, READY_STATUS_VALUES
from core.models.workbench_batch import SORTS, object_fields
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_BATCHES, too_many_batches
from core.shared.strict_parse import JS_SAFE_INT_MAX, is_exact_finite_number

SCOPE_FIELDS = ("query", "status", "ready_status", "page", "size", "sort", "direction", "snapshot_ref", "column_filters",
                "focus", "batch_ids")


def batch_scope(values):
    object_fields(values, SCOPE_FIELDS)
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
            or scope["status"] not in (None, "") + BATCH_STATUS_VALUES
            or scope["ready_status"] not in (None, "") + READY_STATUS_VALUES
            or scope["sort"] not in SORTS or scope["direction"] not in ("asc", "desc")
            or scope["focus"] not in (None, "", "gaps", "unready")):
        raise WorkbenchCommandRejected("invalid_input", "列表筛选或排序不正确。", 400)


def _validate_filter_values(items):
    if (not isinstance(items, list) or len(items) > 5000
            or any(value is not None and type(value) not in (str, int, float) for value in items)
            or any(type(value) in (int, float) and (not is_exact_finite_number(value) or abs(value) > JS_SAFE_INT_MAX) for value in items)):
        raise WorkbenchCommandRejected("invalid_input", "列筛选必须为明确的值集合。", 400)


def _validate_batch_ids(ids):
    if ids is None:
        return
    if isinstance(ids, list) and len(ids) > MAX_WINDOW_BATCHES:
        raise WorkbenchCommandRejected("invalid_input", too_many_batches(MAX_WINDOW_BATCHES), 400)
    if not isinstance(ids, list) or any(not isinstance(key, str) or not key for key in ids):
        raise WorkbenchCommandRejected("invalid_input", "批次定位范围不正确。", 400)


def snapshot_scope(scope):
    return {"kind": "batch", **{key: value for key, value in scope.items() if key not in ("page", "snapshot_ref")}}
