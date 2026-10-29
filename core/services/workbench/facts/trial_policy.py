"""Draft and scenario rulings over WorkbenchTrialRepository facts; the repository itself never rejects."""

import threading
from typing import Any

from core.infrastructure.read_evidence import verified_read
from core.models import workbench_trial as trial_model
from core.models import workbench_trial_codec as trial_codec
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import load_object, load_object_with_size
from core.models.workbench_trial_scenario_archive import (
    logical_snapshot_bytes,
    scenario_metadata_bytes,
    scenario_snapshot,
)

_CURRENT_FIELDS = {"machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end"}
_CACHE_LOCK = threading.RLock()
_SAVED_DRAFT_CACHE = {}
_SCENARIO_RECORD_CACHE = {}


def trial_cache_get(cache, key):
    with _CACHE_LOCK:
        return cache.get(key)


def trial_cache_memo(cache, key, value, limit=32):
    with _CACHE_LOCK:
        if key in cache:
            cache.pop(key)
        elif len(cache) >= limit:
            cache.pop(next(iter(cache)))
        cache[key] = value
        return value


def _scenario_header_meta(header_key):
    with _CACHE_LOCK:
        for key, entry in _SCENARIO_RECORD_CACHE.items():
            if key[0] == header_key:
                return entry[2], entry[3]
        return None


def max_trial_tasks():
    return min(MAX_TRIAL_TASKS, trial_model.MAX_TRIAL_TASKS)


def _clone_json(value) -> Any:
    kind = type(value)
    if kind is dict:
        return {k: _clone_json(v) for k, v in value.items()}
    if kind is list:
        return [_clone_json(v) for v in value]
    return value


def _copy_admission(admission):
    return _clone_json(admission)


def copy_draft_rows(rows):
    return _clone_json(rows)


def _copy_scenario_snapshot(snapshot):
    return _clone_json(snapshot)


def _current_fields(value):
    return _CURRENT_FIELDS <= set(value) <= _CURRENT_FIELDS | {"operation_effort"} and (
        "operation_effort" not in value or type(value["operation_effort"]) is dict)


def require_trial_schema(repo):
    if verified_read(repo.conn, ("trial_schema_issues",), repo.schema_issues):
        reject("trial_schema_unavailable", "试调记录结构不完整，请联系维护人员。", 503)


def load_draft(repo, draft_ref, *, header=None):
    """(head, rows) of one draft with decoded snapshots; rejects missing, truncated or malformed storage."""
    head, rows, _ = load_draft_with_key(repo, draft_ref, header=header)
    return head, rows


def load_draft_with_key(repo, draft_ref, *, header=None):
    require_trial_schema(repo)
    head = repo.draft_header(draft_ref) if header is None else header
    if head is None:
        reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
    head = dict(head)
    raw_rows = repo.draft_rows(draft_ref)
    draft_key = (
        draft_ref,
        head.get("revision"),
        head.get("row_count"),
        head.get("admission_json"),
        head.get("validation_json"),
        tuple(
            (r.get("row_ref"), r.get("task_ref"), r.get("operation_ref"), r.get("source_task_ref"),
             r.get("source_row_ref"), r.get("ordinal"), r.get("original_json"), r.get("current_json"))
            for r in raw_rows
        ),
    ) if head.get("status") == "saved" else None
    cached = trial_cache_get(_SAVED_DRAFT_CACHE, draft_key) if draft_key is not None else None
    if cached is not None:
        admission, validation, cached_rows, max_fragment = cached
        if (
            max_fragment <= trial_codec.MAX_TRIAL_BYTES
            and len(cached_rows) == head["row_count"]
            and 0 < len(cached_rows) <= max_trial_tasks()
        ):
            head.pop("admission_json", None)
            head.pop("validation_json", None)
            head["admission"] = _copy_admission(admission)
            head["validation"] = _clone_json(validation)
            return head, copy_draft_rows(cached_rows), draft_key
    admission_raw = head.pop("admission_json")
    validation_raw = head.pop("validation_json")
    head["admission"] = load_object(admission_raw)
    head["validation"] = load_object(validation_raw)
    max_fragment = max(
        len(admission_raw.encode("utf-8")) if type(admission_raw) is str else 0,
        len(validation_raw.encode("utf-8")) if type(validation_raw) is str else 0,
    )
    rows = []
    for item in raw_rows:
        if item["ordinal"] != len(rows):
            reject("trial_snapshot_invalid", "草稿原始行顺序缺失。")
        orig_raw, curr_raw = item.pop("original_json"), item.pop("current_json")
        item["original"] = load_object(orig_raw)
        item["current"] = load_object(curr_raw)
        for text in (orig_raw, curr_raw):
            if type(text) is str:
                size = len(text.encode("utf-8"))
                if size > max_fragment:
                    max_fragment = size
        if not _current_fields(item["current"]):
            reject("trial_snapshot_invalid", "草稿安排字段不完整。")
        rows.append(item)
    if len(rows) != head["row_count"] or not 0 < len(rows) <= max_trial_tasks():
        reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
    if draft_key is not None:
        trial_cache_memo(
            _SAVED_DRAFT_CACHE,
            draft_key,
            (_copy_admission(head["admission"]), _clone_json(head["validation"]), copy_draft_rows(rows), max_fragment),
        )
    return head, rows, draft_key


def load_scenario(repo, scenario_ref):
    """The decoded scenario snapshot; rejects a missing scenario or one whose permanent rows disagree."""
    return load_scenario_record(repo, scenario_ref)[1]


def load_scenario_record(repo, scenario_ref, *, row_limit=None, byte_limit=None, size_check=None):
    """One immutable saved record; each consumer keeps its own actual body limits."""
    header, result, _ = load_scenario_record_with_key(
        repo, scenario_ref, row_limit=row_limit, byte_limit=byte_limit, size_check=size_check
    )
    return header, result


def load_scenario_record_with_key(repo, scenario_ref, *, row_limit=None, byte_limit=None, size_check=None):
    require_trial_schema(repo)
    header, result, sizes, scenario_key = verified_read(
        repo.conn,
        ("trial_scenario_record", scenario_ref),
        lambda: _load_scenario_record(repo, scenario_ref, row_limit, byte_limit, size_check),
    )
    _scenario_limits(sizes, row_limit, byte_limit, size_check)
    return header, result, scenario_key


def _scenario_limits(sizes, row_limit, byte_limit, size_check):
    if row_limit is not None and sizes["rows"] > row_limit:
        reject("query_too_large", "试调方案的明细超过 10000 条上限，这次没有读取。请缩小范围。", 413)
    if byte_limit is not None:
        size_check(sizes["header"], byte_limit, "试调方案内容")
        size_check(sizes["bodies"], byte_limit, "试调方案内容")


def _load_scenario_record(repo, scenario_ref, row_limit, byte_limit, size_check):
    header = repo.scenario_header(scenario_ref)
    if header is None:
        reject("entity_not_found", "未找到指定试调场景。", 404)
    raw = header["snapshot_json"]
    header_key = (header.get("scenario_ref", scenario_ref), header.get("revision"), header.get("saved_at"), raw)
    header_meta = _scenario_header_meta(header_key)
    if header_meta is not None:
        metadata_bytes, has_metadata = header_meta
        header_bytes = len(raw.encode("utf-8")) if type(raw) is str else 0
        if type(raw) is not str or header_bytes > trial_codec.MAX_TRIAL_BYTES:
            load_object_with_size(raw)
        sizes = {"header": header_bytes, "rows": 0, "bodies": 0}
        _scenario_limits(sizes, row_limit, byte_limit, size_check)
        raw_rows = []
        for row in repo.iter_scenario_rows(scenario_ref):
            payload_json = row["payload_json"]
            if type(payload_json) is not str or len(payload_json.encode("utf-8")) > trial_codec.MAX_TRIAL_BYTES:
                load_object_with_size(payload_json)
            task_bytes = len(payload_json.encode("utf-8"))
            sizes["rows"] += 1
            sizes["bodies"] += task_bytes
            _scenario_limits(sizes, row_limit, byte_limit, size_check)
            logical_snapshot_bytes(metadata_bytes, sizes["bodies"], sizes["rows"], has_metadata=has_metadata)
            raw_rows.append(row)
        if not sizes["rows"]:
            logical_snapshot_bytes(metadata_bytes, 0, 0, has_metadata=has_metadata)
        raw_rows = tuple(raw_rows)
        scenario_key = (header_key, tuple((r["row_ref"], r["payload_json"]) for r in raw_rows))
        cached = trial_cache_get(_SCENARIO_RECORD_CACHE, scenario_key)
        if cached is not None:
            cached_snapshot, cached_sizes, metadata_bytes, has_metadata, max_fragment = cached
            if max_fragment <= trial_codec.MAX_TRIAL_BYTES:
                _scenario_limits(cached_sizes, row_limit, byte_limit, size_check)
                logical_snapshot_bytes(metadata_bytes, cached_sizes["bodies"], cached_sizes["rows"], has_metadata=has_metadata)
                return header, _copy_scenario_snapshot(cached_snapshot), dict(cached_sizes), scenario_key
        rows_iter = raw_rows
    else:
        rows_iter = repo.iter_scenario_rows(scenario_ref)
    archive, header_bytes = load_object_with_size(raw)
    sizes = {"header": header_bytes, "rows": 0, "bodies": 0}
    _scenario_limits(sizes, row_limit, byte_limit, size_check)
    metadata_bytes, stored = scenario_metadata_bytes(raw, archive, header_bytes), {}
    has_metadata = bool(archive["snapshot"])
    seen_raw_rows, max_fragment = [], header_bytes
    for row in rows_iter:
        payload_json = row["payload_json"]
        task, task_bytes = load_object_with_size(payload_json)
        if task_bytes > max_fragment:
            max_fragment = task_bytes
        sizes["rows"] += 1
        sizes["bodies"] += task_bytes
        _scenario_limits(sizes, row_limit, byte_limit, size_check)
        logical_snapshot_bytes(metadata_bytes, sizes["bodies"], sizes["rows"], has_metadata=has_metadata)
        stored[row["row_ref"]] = task
        seen_raw_rows.append((row["row_ref"], payload_json))
    if not sizes["rows"]:
        logical_snapshot_bytes(metadata_bytes, 0, 0, has_metadata=has_metadata)
    snapshot = scenario_snapshot(archive, stored)
    scenario_key = (header_key, tuple(seen_raw_rows))
    trial_cache_memo(
        _SCENARIO_RECORD_CACHE,
        scenario_key,
        (_copy_scenario_snapshot(snapshot), dict(sizes), metadata_bytes, has_metadata, max_fragment),
    )
    return header, snapshot, sizes, scenario_key


def require_advanced(advanced):
    """A draft transition that moved no head row lost the race to another save, change or discard."""
    if not advanced:
        reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")
