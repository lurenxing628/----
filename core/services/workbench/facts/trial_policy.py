"""Draft and scenario rulings over WorkbenchTrialRepository facts; the repository itself never rejects."""

from core.models.workbench_load_limits import MAX_WINDOW_OPERATIONS
from core.models.workbench_trial import reject
from core.models.workbench_trial_codec import load_object, load_object_with_size
from core.models.workbench_trial_scenario_archive import (
    check_scenario_bytes,
    scenario_snapshot,
    validate_scenario_resources,
)
from core.services.workbench.facts.candidate_facts import admit_generation_facts
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.production_capture import validate_production_archive
from core.services.workbench.facts.trial_origin import (
    TRIAL_FACTS_INVALID,
    CandidateTrialSource,
    OfficialTrialSource,
    TrialSource,
)

_CURRENT_FIELDS = {"machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end"}


def _current_fields(value):
    return _CURRENT_FIELDS <= set(value) <= _CURRENT_FIELDS | {"operation_effort"} and (
        "operation_effort" not in value or type(value["operation_effort"]) is dict
    )


def _trial_source(conn, base_kind, admission) -> TrialSource:
    """The draft's stored base as its typed source; a candidate base reads its run archive back from the run."""
    document = admission.get("source")
    if type(document) is not dict:
        reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)
    if base_kind != "candidate_ref":
        return OfficialTrialSource(document)
    run_ref = document.get("run_ref")
    if type(run_ref) is not str or not run_ref:
        reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)
    # 候选运行记录自身的损坏与超限由读取方如实报出，不改说成草稿损坏。
    capture = CandidateStore(conn).capture(run_ref)
    return CandidateTrialSource(document, capture, admit_generation_facts(capture))


def public_source_identity(source):
    """The trial base's public identity; a candidate base's ``run_ref`` is its source's single ``run_ref``."""
    identity = source["identity"]
    if identity["kind"] == "candidate":
        return {**identity, "run_ref": source["run_ref"]}
    return identity


def load_draft(repo, draft_ref, *, header=None):
    """(head, rows, source) of one draft: decoded snapshots and the typed base the admission stores; rejects
    missing, truncated or malformed storage."""
    head = repo.draft_header(draft_ref) if header is None else header
    if head is None:
        reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
    head = dict(head)
    raw_rows = repo.draft_rows(draft_ref)
    admission_raw = head.pop("admission_json")
    validation_raw = head.pop("validation_json")
    admission = load_object(admission_raw)
    if "facts" not in admission:
        reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)
    try:
        validate_production_archive(admission["facts"])
    except ValueError:
        reject("trial_snapshot_invalid", TRIAL_FACTS_INVALID)
    source = _trial_source(repo.conn, head["base_kind"], admission)
    head["admission"] = admission
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
    if len(rows) != head["row_count"] or not 0 < len(rows) <= MAX_WINDOW_OPERATIONS:
        reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
    return head, rows, source


def load_scenario_with_resources(repo, scenario_ref, *, row_limit=None, header=None):
    """(header, compact snapshot, admitted save-time resources) of one immutable saved scenario; every consumer
    shares the stored-bytes limit, a consumer may add its own row limit."""
    resolved_header = repo.scenario_header(scenario_ref) if header is None else header
    if resolved_header is None:
        reject("entity_not_found", "未找到指定试调场景。", 404)
    archive, header_bytes = load_object_with_size(resolved_header["snapshot_json"])
    resources_raw, resources_bytes = load_object_with_size(resolved_header["resources_json"])
    resources = validate_scenario_resources(resources_raw)
    header_size = check_scenario_bytes(header_bytes + resources_bytes)
    stored, columns, bodies = {}, {}, 0
    for row in repo.iter_scenario_rows(scenario_ref):
        if row_limit is not None and len(stored) >= row_limit:
            reject("query_too_large", f"试调方案的明细超过 {row_limit} 条上限，这次没有读取。请缩小范围。", 413)
        task, task_bytes = load_object_with_size(row["payload_json"])
        bodies += task_bytes
        check_scenario_bytes(header_size + bodies)
        stored[row["row_ref"]] = task
        columns[row["row_ref"]] = row
    snapshot = scenario_snapshot(archive, stored, columns)
    return resolved_header, snapshot, resources


def require_advanced(advanced):
    """A draft transition that moved no head row lost the race to another save, change or discard."""
    if not advanced:
        reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")
