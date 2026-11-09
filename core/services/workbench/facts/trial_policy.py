"""Draft and scenario rulings over WorkbenchTrialRepository facts; the repository itself never rejects."""

import threading

from core.infrastructure.read_evidence import verified_read
from core.models import workbench_trial_codec as trial_codec
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import load_object, load_object_with_size
from core.models.workbench_trial_scenario_archive import (
    logical_snapshot_bytes,
    scenario_metadata_bytes,
    scenario_snapshot,
)
from core.services.workbench.facts.production_capture import validate_production_archive

TRIAL_FACTS_INVALID = "试调草稿保存的现场资料已损坏，不能继续核对或采用，正式计划没有改变。请从当前正式计划重新发起试调。"
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


def saved_scenario_cache_key(scenario_key, draft_key):
    if scenario_key is None or draft_key is None:
        return None
    return ("saved_scenario_v1", scenario_key, draft_key)


def _current_fields(value):
    return _CURRENT_FIELDS <= set(value) <= _CURRENT_FIELDS | {"operation_effort"} and (
        "operation_effort" not in value or type(value["operation_effort"]) is dict)


def load_draft(repo, draft_ref, *, header=None):
    """(head, rows) of one draft with decoded snapshots; rejects missing, truncated or malformed storage."""
    head, rows, _ = load_draft_with_key(repo, draft_ref, header=header)
    return head, rows


def load_draft_with_key(repo, draft_ref, *, header=None):
    head = repo.draft_header(draft_ref) if header is None else header
    if head is None:
        reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
    head = dict(head)
    raw_rows = repo.draft_rows(draft_ref)
    draft_key = (
        draft_ref,
        head["revision"],
        head["row_count"],
        head["admission_json"],
        head["validation_json"],
        tuple(
            (r["row_ref"], r["task_ref"], r["operation_ref"], r["source_task_ref"],
             r["source_row_ref"], r["ordinal"], r["original_json"], r["current_json"])
            for r in raw_rows
        ),
    ) if head["status"] == "saved" else None
    cached = trial_cache_get(_SAVED_DRAFT_CACHE, draft_key) if draft_key is not None else None
    if cached is not None:
        admission, validation, cached_rows = cached
        head.pop("admission_json", None)
        head.pop("validation_json", None)
        head["admission"] = admission
        head["validation"] = validation
        return head, cached_rows, draft_key
    admission_raw = head.pop("admission_json")
    validation_raw = head.pop("validation_json")
    head["admission"] = load_object(admission_raw)
    # The saved facts archive is admitted here, before any origin or capture reads it.
    if "facts" not in head["admission"]:
        reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)
    try:
        validate_production_archive(head["admission"]["facts"], named=True)
    except ValueError:
        reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)
    head["validation"] = load_object(validation_raw)
    rows = []
    for item in raw_rows:
        if item["ordinal"] != len(rows):
            reject("trial_snapshot_invalid", "草稿原始行顺序缺失。")
        orig_raw, curr_raw = item.pop("original_json"), item.pop("current_json")
        item["original"] = load_object(orig_raw)
        item["current"] = load_object(curr_raw)
        if not _current_fields(item["current"]):
            reject("trial_snapshot_invalid", "草稿安排字段不完整。")
        rows.append(item)
    if len(rows) != head["row_count"] or not 0 < len(rows) <= MAX_TRIAL_TASKS:
        reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
    if draft_key is not None:
        trial_cache_memo(
            _SAVED_DRAFT_CACHE,
            draft_key,
            (head["admission"], head["validation"], rows),
        )
    return head, rows, draft_key


def load_scenario(repo, scenario_ref, *, header=None):
    """The decoded scenario snapshot; rejects a missing scenario or one whose permanent rows disagree."""
    return load_scenario_record(repo, scenario_ref, header=header)[1]


def load_scenario_record(repo, scenario_ref, *, row_limit=None, byte_limit=None, size_check=None, header=None):
    """One immutable saved record; each consumer keeps its own actual body limits."""
    header, result, _ = load_scenario_record_with_key(
        repo, scenario_ref, row_limit=row_limit, byte_limit=byte_limit, size_check=size_check, header=header
    )
    return header, result


def load_scenario_record_with_key(repo, scenario_ref, *, row_limit=None, byte_limit=None, size_check=None, header=None):
    header, result, sizes, scenario_key = verified_read(
        repo.conn,
        ("trial_scenario_record", scenario_ref),
        lambda: _load_scenario_record(repo, scenario_ref, row_limit, byte_limit, size_check, header=header),
    )
    _scenario_limits(sizes, row_limit, byte_limit, size_check)
    return header, result, scenario_key


def _scenario_limits(sizes, row_limit, byte_limit, size_check):
    if row_limit is not None and sizes["rows"] > row_limit:
        reject("query_too_large", "试调方案的明细超过 10000 条上限，这次没有读取。请缩小范围。", 413)
    if byte_limit is not None:
        size_check(sizes["header"], byte_limit, "试调方案内容")
        size_check(sizes["bodies"], byte_limit, "试调方案内容")


def _load_scenario_record(repo, scenario_ref, row_limit, byte_limit, size_check, header=None):
    header = repo.scenario_header(scenario_ref) if header is None else header
    if header is None:
        reject("entity_not_found", "未找到指定试调场景。", 404)
    raw = header["snapshot_json"]
    header_key = (header["scenario_ref"], header["revision"], header["saved_at"], raw)
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
            cached_snapshot, cached_sizes, metadata_bytes, has_metadata = cached
            return header, cached_snapshot, dict(cached_sizes), scenario_key
        rows_iter = raw_rows
    else:
        rows_iter = repo.iter_scenario_rows(scenario_ref)
    archive, header_bytes = load_object_with_size(raw)
    sizes = {"header": header_bytes, "rows": 0, "bodies": 0}
    _scenario_limits(sizes, row_limit, byte_limit, size_check)
    metadata_bytes, stored = scenario_metadata_bytes(raw, archive, header_bytes), {}
    has_metadata = bool(archive["snapshot"])
    seen_raw_rows = []
    for row in rows_iter:
        payload_json = row["payload_json"]
        task, task_bytes = load_object_with_size(payload_json)
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
        (snapshot, dict(sizes), metadata_bytes, has_metadata),
    )
    return header, snapshot, sizes, scenario_key


def require_advanced(advanced):
    """A draft transition that moved no head row lost the race to another save, change or discard."""
    if not advanced:
        reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")
