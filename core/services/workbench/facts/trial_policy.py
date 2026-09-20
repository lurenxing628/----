"""Draft and scenario rulings over WorkbenchTrialRepository facts; the repository itself never rejects."""

from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import load_object

_CURRENT_FIELDS = {"machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end"}


def require_trial_schema(repo):
    if repo.schema_issues():
        reject("trial_schema_unavailable", "试调记录结构不完整，请联系维护人员。", 503)


def load_draft(repo, draft_ref):
    """(head, rows) of one draft with decoded snapshots; rejects missing, truncated or malformed storage."""
    require_trial_schema(repo)
    head = repo.draft_header(draft_ref)
    if head is None:
        reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
    head["admission"] = load_object(head.pop("admission_json"), head["admission_hash"])
    head["validation"] = load_object(head.pop("validation_json"))
    count = repo.draft_row_count(draft_ref)
    if count != head["row_count"] or not 0 < count <= MAX_TRIAL_TASKS:
        reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
    rows = []
    for item in repo.draft_rows(draft_ref):
        if item["ordinal"] != len(rows):
            reject("trial_snapshot_invalid", "草稿原始行顺序缺失。")
        item["original"] = load_object(item.pop("original_json"), item.pop("original_hash"))
        item["current"] = load_object(item.pop("current_json"))
        if set(item["current"]) != _CURRENT_FIELDS:
            reject("trial_snapshot_invalid", "草稿安排字段不完整。")
        rows.append(item)
    return head, rows


def load_scenario(repo, scenario_ref):
    """The decoded scenario snapshot; rejects a missing scenario or one whose permanent rows disagree."""
    require_trial_schema(repo)
    header = repo.scenario_header(scenario_ref)
    if header is None:
        reject("entity_not_found", "未找到指定试调场景。", 404)
    result = load_object(header["snapshot_json"], header["snapshot_hash"])
    tasks = result.get("tasks")
    if type(tasks) is not list or any(type(task) is not dict or type(task.get("row_ref")) is not str for task in tasks):
        reject("trial_snapshot_invalid", "场景任务明细必须为带永久行引用的对象列表。")
    stored = {row["row_ref"]: load_object(row["payload_json"]) for row in repo.scenario_rows(scenario_ref)}
    if len(stored) != len(tasks) or stored != {row["row_ref"]: row for row in tasks}:
        reject("trial_snapshot_invalid", "场景快照与永久明细不一致。")
    return result


def require_advanced(advanced):
    """A draft transition that moved no head row lost the race to another save, change or discard."""
    if not advanced:
        reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")
