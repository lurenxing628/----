"""Shared origin validation against birth evidence and full mutation history."""

from typing import NoReturn

from core.models.workbench_calibration import MAX_OPERATIONS, CalibrationLineage, issue
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import (
    EVIDENCE_VERSION,
    OWNER_COLUMNS,
    SEMANTIC_COLUMNS,
    STATE_COLUMNS,
    columns_signature,
    restore_snapshot,
)
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository

_INITIAL_SEMANTIC_COLUMNS = SEMANTIC_COLUMNS + OWNER_COLUMNS

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


def _read_origins(repo, refs, evidence_bytes=0):
    result = {}
    for row in repo.origin_rows(refs):
        evidence_bytes += row.pop("_lineage_bytes")
        check_evidence_size(evidence_bytes)
        result[row["operation_ref"]] = row
    return result, evidence_bytes


def read_events(repo, refs):
    result = {}
    event_count = evidence_bytes = 0
    for rows in repo.event_chunks(refs, MAX_EVENTS):
        for row in rows:
            event_count += 1
            evidence_bytes += row.pop("_lineage_bytes")
            check_evidence_size(evidence_bytes)
            if event_count > MAX_EVENTS:
                raise WorkbenchCommandRejected("query_too_large", "模板来源的变更记录超过 50000 条，系统没有截断处理，这次没有读取。请缩小范围后重试。", 413)
            result.setdefault(row["operation_ref"], []).append(row)
    return result


def _prepare_origin(origin, events, *, restored_templates):
    try:
        raw_template = origin["template_snapshot"]
        template = restored_templates.get(raw_template)
        if template is None:
            template = restore_snapshot(raw_template)
            restored_templates[raw_template] = template
        if not isinstance(origin["instance_snapshot"], str):
            _invalid()
    except (KeyError, TypeError, ValueError, OverflowError):
        _invalid()
    if origin["evidence_version"] != EVIDENCE_VERSION:
        _invalid()
    if (template.get("template_operation_ref") != origin["template_operation_ref"] or
            template.get("template_revision") != origin["template_revision"]):
        _invalid()
    if (not events or events[0]["event_id"] != origin["birth_event_id"] or events[0]["event_type"] != "created" or
            any(event["operation_ref"] != origin["operation_ref"] for event in events)):
        _invalid()
    instance = {key: events[0][key] for key in STATE_COLUMNS}
    positions, prefixes = _validate_events(events)
    return _PreparedOrigin(origin, template, instance, events, positions, prefixes)


def _validate_events(events):
    previous = events[0]
    if previous["affects_calibration"] != 0:
        _invalid()
    positions = {previous["event_id"]: 0}
    prefixes = [(False, False, False)]
    withdrawn = retired = modified = False
    for position, row in enumerate(events[1:], 1):
        event_type = row["event_type"]
        if row["event_id"] <= previous["event_id"] or event_type not in ("updated", "retired", "withdrawn", "batch_changed"):
            _invalid()
        if event_type != "updated" and not row["affects_calibration"]:
            _invalid()
        withdrawn = withdrawn or event_type == "withdrawn"
        retired = retired or event_type == "retired"
        modified = modified or bool(row["affects_calibration"] and event_type in ("updated", "batch_changed"))
        positions[row["event_id"]] = position
        prefixes.append((withdrawn, retired, modified))
        previous = row
    return positions, prefixes


class _PreparedOrigin:
    def __init__(self, origin, template, initial, events, positions, prefixes):
        self.template = template
        self.initial = initial
        self.events = events
        self.positions = positions
        self.prefixes = prefixes
        self.source_eligible = bool(origin["source_eligible"])
        self.initial_semantic = columns_signature(initial, _INITIAL_SEMANTIC_COLUMNS)
        self._eligibility = {}

    @property
    def last_event_id(self):
        return self.events[-1]["event_id"]

    def eligible_at(self, position):
        if position not in self._eligibility:
            clean = self.source_eligible and not any(self.prefixes[position])
            if clean:
                _validate_semantic(self, self.events[position])
            self._eligibility[position] = clean
        return self._eligibility[position]


def _problems(prepared, current):
    reasons = []
    withdrawn, retired, modified = prepared.prefixes[-1]
    if not prepared.source_eligible:
        reasons.append(issue("template_copy_source_unqualified", "复制来源那道工序的模板来源已失效或已撤回，复制过来的这道工序也不能当作可用的完工记录。"))
    if withdrawn:
        reasons.append(issue("template_lineage_withdrawn", "模板来源已撤回，原来的记录保留，但不再用于校准。"))
    if current is None or retired:
        reasons.append(issue("template_instance_retired", "原来那道工序已删除或被替换，不会改指同号的新工序，不再用于校准。"))
    if modified:
        reasons.append(issue("template_instance_modified", "这道工序的工艺资料或所属批次改过，即使改回原值也不能当作可用的完工记录。"))
    _validate_current(prepared, current, reasons)
    return reasons


def _validate_semantic(prepared, current):
    if columns_signature(current, _INITIAL_SEMANTIC_COLUMNS) != prepared.initial_semantic:
        _invalid()


def _validate_current(prepared, current, reasons):
    if current is not None and not reasons:
        _validate_semantic(prepared, current)


def _validate_source(origin, origins, prepared):
    source_ref = origin["source_operation_ref"]
    if source_ref is None:
        return
    source = origins.get(source_ref)
    if source is None or (source["lineage_ref"] != origin["source_lineage_ref"] or
                          source["template_snapshot"] != origin["template_snapshot"]):
        _invalid()
    source_prepared = prepared[source_ref]
    position = source_prepared.positions.get(origin["source_event_id"])
    if position is None or origin["source_event_id"] >= origin["birth_event_id"]:
        _invalid()
    clean = source_prepared.eligible_at(position)
    if clean != bool(origin["source_eligible"]):
        _invalid()


def _validate_template_revision(origin, templates):
    current = templates.get(origin["template_operation_ref"])
    if current is not None and (current["id"] is None or current["part_ref"] is None):
        _invalid()


class TemplateLineageQuery:
    def __init__(self, conn, repo=None):
        # 写入器逐道复制时把已校验过表结构的仓储传进来，避免每道工序重新解析整套 DDL。
        self.repo = repo if repo is not None else WorkbenchTemplateLineageRepository(conn)
        self._prepared = {}

    def prepared_origin(self, operation_ref):
        return self._prepared[operation_ref]

    def read(self, operation_refs, *, current=None, templates=None, current_by_ref=None, templates_by_ref=None):
        self._prepared = {}
        refs = sorted(set(operation_refs))
        if not lineage_available(self.repo):
            return {"available": False, "origins": {}, "events": {}, "current": {}, "templates": {}, "lineages": {}, "problems": {}}
        origins, evidence_bytes = _read_origins(self.repo, refs)
        self._ancestors(origins, evidence_bytes)
        events = read_events(self.repo, list(origins))
        if current is not None:
            current = {ref: current[ref] for ref in origins if ref in current}
        elif current_by_ref is not None:
            missing_current = [ref for ref in origins if ref not in current_by_ref]
            loaded_current = self.repo.current_instances(missing_current) if missing_current else {}
            current = {
                ref: (current_by_ref[ref] if ref in current_by_ref else loaded_current[ref])
                for ref in origins
                if ref in current_by_ref or ref in loaded_current
            }
        else:
            current = self.repo.current_instances(list(origins))
        template_refs = sorted({row["template_operation_ref"] for row in origins.values()})
        if templates is not None:
            templates = {ref: templates[ref] for ref in template_refs if ref in templates}
        elif templates_by_ref is not None:
            missing_templates = [ref for ref in template_refs if ref not in templates_by_ref]
            loaded_templates = self.repo.current_templates(missing_templates) if missing_templates else {}
            templates = {
                ref: (templates_by_ref[ref] if ref in templates_by_ref else loaded_templates[ref])
                for ref in template_refs
                if ref in templates_by_ref or ref in loaded_templates
            }
        else:
            templates = self.repo.current_templates(template_refs)
        restored_templates = {}
        self._prepared = {
            ref: _prepare_origin(origin, events.get(ref, []), restored_templates=restored_templates)
            for ref, origin in origins.items()
        }
        lineages, problems = {}, {}
        for ref, origin in origins.items():
            _validate_source(origin, origins, self._prepared)
            _validate_template_revision(origin, templates)
            problems[ref] = _problems(self._prepared[ref], current.get(ref))
            lineages[ref] = CalibrationLineage(origin["template_operation_ref"], origin["template_revision"], origin["lineage_ref"])
        return {"available": True, "origins": origins, "events": events, "current": current, "templates": templates,
                "lineages": lineages, "problems": problems}

    def _ancestors(self, origins, evidence_bytes):
        frontier = list(origins.values())
        if len(origins) > MAX_OPERATIONS:
            self._too_many_ancestors()
        for _ in range(100):
            missing = {row["source_operation_ref"] for row in frontier if row["source_operation_ref"] is not None
                       and row["source_operation_ref"] not in origins}
            if not missing:
                return
            rows, evidence_bytes = _read_origins(self.repo, sorted(missing), evidence_bytes)
            if set(rows) != missing:
                _invalid()
            origins.update(rows)
            if len(origins) > MAX_OPERATIONS:
                break
            frontier = list(rows.values())
        self._too_many_ancestors()

    @staticmethod
    def _too_many_ancestors():
        raise WorkbenchCommandRejected("query_too_large", "模板复制来源超过 100 层或 10000 道工序，这次没有读取。请缩小范围后重试。", 413)
