"""Shared origin validation against birth evidence and full mutation history."""

from typing import NoReturn

from core.models.workbench_calibration import MAX_OPERATIONS, CalibrationLineage, issue
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import (
    EVIDENCE_VERSION,
    OWNER_COLUMNS,
    SEMANTIC_COLUMNS,
    STATE_COLUMNS,
    fingerprint,
    restore_snapshot,
    snapshot,
    state_snapshot,
)
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository

MAX_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 50000


def _invalid() -> NoReturn:
    raise WorkbenchCommandRejected("template_lineage_corrupt", "模板来源记录和这道工序的历史记录对不上，系统没有猜着匹配，也没有忽略。请联系维护人员。", 500)


def check_evidence_size(size):
    if size > MAX_EVIDENCE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "要读的模板来源记录超过 16 MB，系统没有截断处理，这次没有读取。请缩小范围后重试。", 413)


def lineage_available(repo):
    """False when lineage storage was never installed; partial or altered DDL is rejected, never repaired."""
    state = repo.schema_state()
    if state == "invalid":
        raise WorkbenchCommandRejected("template_lineage_unavailable", "模板来源记录的数据表不完整，系统没有自动补表，这次没有读取。请恢复完整资料后重试。")
    return state == "loaded"


def read_origins(repo, refs):
    check_evidence_size(repo.origins_bytes(refs))
    return repo.origins(refs)


def read_events(repo, refs):
    check_evidence_size(repo.events_bytes(refs))
    result = {}
    for rows in repo.event_chunks(refs, MAX_EVENTS):
        if len(rows) > MAX_EVENTS:
            raise WorkbenchCommandRejected("query_too_large", "模板来源的变更记录超过 50000 条，系统没有截断处理，这次没有读取。请缩小范围后重试。", 413)
        for row in rows:
            result.setdefault(row["operation_ref"], []).append(row)
    if sum(map(len, result.values())) > MAX_EVENTS:
        raise WorkbenchCommandRejected("query_too_large", "模板来源的变更记录超过 50000 条，系统没有截断处理，这次没有读取。请缩小范围后重试。", 413)
    return result


def validate_origin(origin, events):
    try:
        template = restore_snapshot(origin["template_snapshot"])
        instance = restore_snapshot(origin["instance_snapshot"])
    except (KeyError, TypeError, ValueError, OverflowError):
        _invalid()
    if (origin["evidence_version"] != EVIDENCE_VERSION or
            fingerprint(origin["template_snapshot"]) != origin["template_fingerprint"] or
            fingerprint(origin["instance_snapshot"]) != origin["instance_fingerprint"] or
            set(instance) != set(STATE_COLUMNS)):
        _invalid()
    if (template.get("template_operation_ref") != origin["template_operation_ref"] or
            template.get("template_revision") != origin["template_revision"]):
        _invalid()
    if (not events or events[0]["event_id"] != origin["birth_event_id"] or events[0]["event_type"] != "created" or
            state_snapshot(events[0]) != origin["instance_snapshot"] or
            any(event["operation_ref"] != origin["operation_ref"] for event in events)):
        _invalid()
    _validate_events(events)
    return template, instance


def _validate_events(events):
    previous = events[0]
    if previous["affects_calibration"] != 0:
        _invalid()
    for row in events[1:]:
        if row["event_type"] == "updated":
            keys = SEMANTIC_COLUMNS + ("batch_id",)
            changed = snapshot({key: previous[key] for key in keys}) != snapshot({key: row[key] for key in keys})
        elif row["event_type"] in ("retired", "withdrawn", "batch_changed"):
            changed = True
        else:
            _invalid()
        if bool(row["affects_calibration"]) != changed:
            _invalid()
        previous = row


def _problems(origin, events, current):
    _, initial = validate_origin(origin, events)
    reasons = []
    if not origin["source_eligible"]:
        reasons.append(issue("template_copy_source_unqualified", "复制来源那道工序的模板来源已失效或已撤回，复制过来的这道工序也不能当作可用的完工记录。"))
    if any(row["event_type"] == "withdrawn" for row in events):
        reasons.append(issue("template_lineage_withdrawn", "模板来源已撤回，原来的记录保留，但不再用于校准。"))
    if current is None or any(row["event_type"] == "retired" for row in events):
        reasons.append(issue("template_instance_retired", "原来那道工序已删除或被替换，不会改指同号的新工序，不再用于校准。"))
    if any(row["affects_calibration"] and row["event_type"] in ("updated", "batch_changed") for row in events):
        reasons.append(issue("template_instance_modified", "这道工序的工艺资料或所属批次改过，即使改回原值也不能当作可用的完工记录。"))
    _validate_current(initial, events, current, reasons)
    return reasons


def _validate_current(initial, events, current, reasons):
    if current is None:
        return
    if state_snapshot(events[-1]) != state_snapshot(current):
        _invalid()
    semantic = SEMANTIC_COLUMNS + OWNER_COLUMNS
    if snapshot({key: current[key] for key in semantic}) != snapshot({key: initial[key] for key in semantic}) and not reasons:
        _invalid()


def _validate_source(origin, origins, events):
    source_ref = origin["source_operation_ref"]
    if source_ref is None:
        return
    source = origins.get(source_ref)
    if source is None or (source["lineage_ref"] != origin["source_lineage_ref"] or
                          source["template_snapshot"] != origin["template_snapshot"]):
        _invalid()
    history = [row for row in events.get(source_ref, []) if row["event_id"] <= origin["source_event_id"]]
    if not history or history[-1]["event_id"] != origin["source_event_id"] or origin["source_event_id"] >= origin["birth_event_id"]:
        _invalid()
    clean = not _problems(source, history, history[-1])
    if clean != bool(origin["source_eligible"]):
        _invalid()


def _validate_template_revision(origin, templates):
    current = templates.get(origin["template_operation_ref"])
    if current is None:
        return
    if current["id"] is None or current["part_ref"] is None:
        _invalid()
    if current["template_revision"] == origin["template_revision"] and snapshot(current) != origin["template_snapshot"]:
        _invalid()


class TemplateLineageQuery:
    def __init__(self, conn):
        self.repo = WorkbenchTemplateLineageRepository(conn)

    def read(self, operation_refs):
        refs = sorted(set(operation_refs))
        if not lineage_available(self.repo):
            return {"available": False, "origins": {}, "events": {}, "current": {}, "templates": {}, "lineages": {}, "problems": {}}
        origins = read_origins(self.repo, refs)
        self._ancestors(origins)
        events = read_events(self.repo, list(origins))
        current = self.repo.current_instances(list(origins))
        templates = self.repo.current_templates(sorted({row["template_operation_ref"] for row in origins.values()}))
        lineages, problems = {}, {}
        for ref, origin in origins.items():
            _validate_source(origin, origins, events)
            _validate_template_revision(origin, templates)
            problems[ref] = _problems(origin, events.get(ref, []), current.get(ref))
            lineages[ref] = CalibrationLineage(origin["template_operation_ref"], origin["template_revision"], origin["lineage_ref"])
        return {"available": True, "origins": origins, "events": events, "current": current, "templates": templates,
                "lineages": lineages, "problems": problems}

    def _ancestors(self, origins):
        for _ in range(100):
            missing = {row["source_operation_ref"] for row in origins.values() if row["source_operation_ref"] is not None} - origins.keys()
            if not missing:
                return
            rows = read_origins(self.repo, sorted(missing))
            if set(rows) != missing:
                _invalid()
            origins.update(rows)
            check_evidence_size(sum(len(row["template_snapshot"].encode("ascii")) + len(row["instance_snapshot"].encode("ascii"))
                                    for row in origins.values()))
            if len(origins) > MAX_OPERATIONS:
                break
        raise WorkbenchCommandRejected("query_too_large", "模板复制来源超过 100 层或 10000 道工序，这次没有读取。请缩小范围后重试。", 413)
