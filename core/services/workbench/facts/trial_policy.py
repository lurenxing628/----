"""Draft and scenario rulings over WorkbenchTrialRepository facts; the repository itself never rejects."""

from core.infrastructure.read_evidence import verified_read
from core.models.content import same
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import _encoded, load_object, load_object_with_size
from core.models.workbench_trial_scenario_archive import (
    logical_snapshot_bytes,
    scenario_read_size_basis,
    scenario_snapshot,
)

_CURRENT_FIELDS = {"machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end"}


def _current_fields(value):
    return _CURRENT_FIELDS <= set(value) <= _CURRENT_FIELDS | {"operation_effort"} and (
        "operation_effort" not in value or type(value["operation_effort"]) is dict)


def require_trial_schema(repo):
    if verified_read(getattr(repo, "conn", None), ("trial_schema_issues",), repo.schema_issues):
        reject("trial_schema_unavailable", "试调记录结构不完整，请联系维护人员。", 503)


def load_draft(repo, draft_ref, *, header=None):
    """(head, rows) of one draft with decoded snapshots; rejects missing, truncated or malformed storage."""
    require_trial_schema(repo)
    head = repo.draft_header(draft_ref) if header is None else header
    if head is None:
        reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
    head = dict(head)
    head["admission"] = load_object(head.pop("admission_json"))
    head["validation"] = load_object(head.pop("validation_json"))
    rows = []
    for item in repo.draft_rows(draft_ref):
        if item["ordinal"] != len(rows):
            reject("trial_snapshot_invalid", "草稿原始行顺序缺失。")
        item["original"] = load_object(item.pop("original_json"))
        item.pop("original_hash")
        item["current"] = load_object(item.pop("current_json"))
        if not _current_fields(item["current"]):
            reject("trial_snapshot_invalid", "草稿安排字段不完整。")
        rows.append(item)
    if len(rows) != head["row_count"] or not 0 < len(rows) <= MAX_TRIAL_TASKS:
        reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
    return head, rows


def load_scenario(repo, scenario_ref):
    """The decoded scenario snapshot; rejects a missing scenario or one whose permanent rows disagree."""
    return load_scenario_record(repo, scenario_ref)[1]


def load_scenario_record(repo, scenario_ref, *, row_limit=None, byte_limit=None, size_check=None):
    """One immutable saved record; each consumer keeps its own actual body limits."""
    require_trial_schema(repo)
    header, result, sizes = verified_read(getattr(repo, "conn", None), ("trial_scenario_record", scenario_ref),
        lambda: _load_scenario_record(repo, scenario_ref, row_limit, byte_limit, size_check))
    _scenario_limits(sizes, row_limit, byte_limit, size_check)
    return header, result


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
    archive, header_bytes = load_object_with_size(raw)
    sizes = {"header": header_bytes, "rows": 0, "bodies": 0}
    _scenario_limits(sizes, row_limit, byte_limit, size_check)
    legacy, stored = "tasks" in archive, {}
    metadata_bytes, normalize_task_bytes = (None, False) if legacy else scenario_read_size_basis(raw, archive, header_bytes)
    logical_bodies = 0
    for row in repo.iter_scenario_rows(scenario_ref):
        raw = row["payload_json"]
        task, task_bytes = load_object_with_size(raw)
        sizes["rows"] += 1
        sizes["bodies"] += task_bytes
        _scenario_limits(sizes, row_limit, byte_limit, size_check)
        if metadata_bytes is not None:
            logical_bodies += len(_encoded(task)[1]) if normalize_task_bytes else task_bytes
            logical_snapshot_bytes(metadata_bytes, logical_bodies, sizes["rows"], has_metadata=bool(archive["snapshot"]))
        stored[row["row_ref"]] = task
    if metadata_bytes is not None and not sizes["rows"]:
        logical_snapshot_bytes(metadata_bytes, logical_bodies, sizes["rows"], has_metadata=bool(archive["snapshot"]))
    result = scenario_snapshot(archive, stored)
    tasks = result.get("tasks")
    if type(tasks) is not list or any(type(task) is not dict or type(task.get("row_ref")) is not str for task in tasks):
        reject("trial_snapshot_invalid", "场景任务明细必须为带永久行引用的对象列表。")
    if legacy and (len(stored) != len(tasks) or not same(stored, {row["row_ref"]: row for row in tasks})):
        reject("trial_snapshot_invalid", "场景快照与永久明细不一致。")
    return header, result, sizes


def require_advanced(advanced):
    """A draft transition that moved no head row lost the race to another save, change or discard."""
    if not advanced:
        reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")
