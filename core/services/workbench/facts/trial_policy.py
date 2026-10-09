"""Draft and scenario rulings over WorkbenchTrialRepository facts; the repository itself never rejects."""

import hashlib

from core.models.workbench_command import input_fingerprint
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import dump_and_fingerprint, load_document, load_object, require_object
from core.models.workbench_trial_scenario_archive import scenario_snapshot

_CURRENT_FIELDS = {"machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end"}


def _stored_object(text, digest):
    """load_object(text, digest) without re-serializing an intact column only to hash it again.

    The repository stores dump(value) beside fingerprint(value), which is the digest of exactly that
    text, so a matching text needs no second canonical write; any other text still takes the codec's
    full check and is rejected as before. The stored hashes themselves are never recomputed differently.
    """
    if type(text) is str and type(digest) is str and hashlib.sha256(text.encode("utf-8")).hexdigest() == digest:
        return load_object(text)
    return load_object(text, digest)


def require_trial_schema(repo):
    if repo.schema_issues():
        reject("trial_schema_unavailable", "试调记录结构不完整，请联系维护人员。", 503)


def load_draft(repo, draft_ref):
    """(head, rows) of one draft with decoded snapshots; rejects missing, truncated or malformed storage."""
    require_trial_schema(repo)
    head = repo.draft_header(draft_ref)
    if head is None:
        reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
    head["admission"] = _stored_object(head.pop("admission_json"), head["admission_hash"])
    head["validation"] = load_object(head.pop("validation_json"))
    count = repo.draft_row_count(draft_ref)
    if count != head["row_count"] or not 0 < count <= MAX_TRIAL_TASKS:
        reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
    rows = []
    for item in repo.draft_rows(draft_ref):
        if item["ordinal"] != len(rows):
            reject("trial_snapshot_invalid", "草稿原始行顺序缺失。")
        item["original"] = _stored_object(item.pop("original_json"), item.pop("original_hash"))
        item["current"] = load_object(item.pop("current_json"))
        if set(item["current"]) != _CURRENT_FIELDS:
            reject("trial_snapshot_invalid", "草稿安排字段不完整。")
        rows.append(item)
    return head, rows


def reload_changed_draft(repo, head, rows):
    """Refresh a changed draft within the write transaction that checked its immutable archives."""
    if not repo.conn.in_transaction:
        raise RuntimeError("Trial archive reuse requires the same caller write transaction")
    draft_ref = head["draft_ref"]
    state = repo.draft_state(draft_ref)
    if state is None:
        reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
    current_head = dict(head, **state)
    current_head["validation"] = load_object(current_head.pop("validation_json"))
    count = repo.draft_row_count(draft_ref)
    if count != head["row_count"] or not 0 < count <= MAX_TRIAL_TASKS:
        reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
    current_rows = []
    for item in repo.draft_arrangements(draft_ref):
        index = len(current_rows)
        if item["ordinal"] != index or index >= len(rows) or item["row_ref"] != rows[index]["row_ref"]:
            reject("trial_snapshot_invalid", "草稿原始行顺序缺失。")
        current = load_object(item["current_json"])
        if set(current) != _CURRENT_FIELDS:
            reject("trial_snapshot_invalid", "草稿安排字段不完整。")
        current_rows.append(dict(rows[index], current=current))
    return current_head, current_rows


def load_scenario(repo, scenario_ref):
    """The decoded scenario snapshot; rejects a missing scenario or one whose permanent rows disagree."""
    return load_scenario_record(repo, scenario_ref)[1]


def load_scenario_record(repo, scenario_ref):
    """The immutable header and decoded snapshot from the same verified scenario read."""
    require_trial_schema(repo)
    header = repo.scenario_header(scenario_ref)
    if header is None:
        reject("entity_not_found", "未找到指定试调场景。", 404)
    packed_archive, decoded_archive = load_document(header["snapshot_json"])
    archive = require_object(decoded_archive)
    legacy = "tasks" in archive
    if legacy and input_fingerprint(packed_archive) != header["snapshot_hash"]:
        reject("trial_snapshot_invalid", "试调数据没有通过完整性检查，这里不改用最新计划。请刷新后重试。")
    del packed_archive
    stored = {row["row_ref"]: load_object(row["payload_json"]) for row in repo.scenario_rows(scenario_ref)}
    result = scenario_snapshot(archive, stored)
    # Old archives already carry the bounded body. New metadata archives must
    # apply the same size limit and digest to the reconstructed public snapshot.
    if not legacy and dump_and_fingerprint(result)[1] != header["snapshot_hash"]:
        reject("trial_snapshot_invalid", "试调数据没有通过完整性检查，这里不改用最新计划。请刷新后重试。")
    tasks = result.get("tasks")
    if type(tasks) is not list or any(type(task) is not dict or type(task.get("row_ref")) is not str for task in tasks):
        reject("trial_snapshot_invalid", "场景任务明细必须为带永久行引用的对象列表。")
    if len(stored) != len(tasks) or stored != {row["row_ref"]: row for row in tasks}:
        reject("trial_snapshot_invalid", "场景快照与永久明细不一致。")
    return header, result


def require_advanced(advanced):
    """A draft transition that moved no head row lost the race to another save, change or discard."""
    if not advanced:
        reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")
