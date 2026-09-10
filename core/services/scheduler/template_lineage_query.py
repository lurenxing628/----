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


def _invalid() -> NoReturn:
    raise WorkbenchCommandRejected("template_lineage_corrupt", "模板来源证据与实例历史不一致，未猜配或静默忽略。", 500)


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
        reasons.append(issue("template_copy_source_unqualified", "所复制实例的来源已污染或撤回，复制不能把它变成合格模板样本。"))
    if any(row["event_type"] == "withdrawn" for row in events):
        reasons.append(issue("template_lineage_withdrawn", "来源已明确撤回，原证据保留但不再用于校准。"))
    if current is None or any(row["event_type"] == "retired" for row in events):
        reasons.append(issue("template_instance_retired", "原工序实例已删除或替换，不会转指同号新实例。"))
    if any(row["affects_calibration"] and row["event_type"] in ("updated", "batch_changed") for row in events):
        reasons.append(issue("template_instance_modified", "实例工艺或所属批次资料曾被修改；即使改回原值也不能充作未污染样本。"))
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
        if not self.repo.available():
            return {"available": False, "origins": {}, "events": {}, "current": {}, "templates": {}, "lineages": {}, "problems": {}}
        origins = self.repo.origins(refs)
        self._ancestors(origins)
        events = self.repo.events(list(origins))
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
            rows = self.repo.origins(sorted(missing))
            if set(rows) != missing:
                _invalid()
            origins.update(rows)
            self.repo._check_size(sum(len(row["template_snapshot"].encode("ascii")) + len(row["instance_snapshot"].encode("ascii"))
                                      for row in origins.values()))
            if len(origins) > MAX_OPERATIONS:
                break
        raise WorkbenchCommandRejected("query_too_large", "模板复制来源超过100层或10000实例，请缩小范围。", 413)
