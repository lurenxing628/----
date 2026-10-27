"""Draft and scenario rulings over WorkbenchTrialRepository facts; the repository itself never rejects."""

from core.infrastructure.read_evidence import verified_read
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import load_object, load_object_with_size
from core.models.workbench_trial_scenario_archive import (
    logical_snapshot_bytes,
    scenario_metadata_bytes,
    scenario_snapshot,
)

_CURRENT_FIELDS = {"machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end"}


def _current_fields(value):
    return _CURRENT_FIELDS <= set(value) <= _CURRENT_FIELDS | {"operation_effort"} and (
        "operation_effort" not in value or type(value["operation_effort"]) is dict)


def require_trial_schema(repo):
    if verified_read(repo.conn, ("trial_schema_issues",), repo.schema_issues):
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
    header, result, sizes = verified_read(repo.conn, ("trial_scenario_record", scenario_ref),
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
    metadata_bytes, stored = scenario_metadata_bytes(raw, archive, header_bytes), {}
    has_metadata = bool(archive["snapshot"])
    for row in repo.iter_scenario_rows(scenario_ref):
        task, task_bytes = load_object_with_size(row["payload_json"])
        sizes["rows"] += 1
        sizes["bodies"] += task_bytes
        _scenario_limits(sizes, row_limit, byte_limit, size_check)
        logical_snapshot_bytes(metadata_bytes, sizes["bodies"], sizes["rows"], has_metadata=has_metadata)
        stored[row["row_ref"]] = task
    if not sizes["rows"]:
        logical_snapshot_bytes(metadata_bytes, 0, 0, has_metadata=has_metadata)
    return header, scenario_snapshot(archive, stored), sizes


def require_advanced(advanced):
    """A draft transition that moved no head row lost the race to another save, change or discard."""
    if not advanced:
        reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")
