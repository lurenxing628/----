"""Shared template/instance copies; origin evidence never uses heuristic matches.

The repository reads identity rows and appends evidence. Fixed source preparation
and newly inserted birth evidence belong to this caller's transaction.
"""

from dataclasses import dataclass
from typing import Optional, cast

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import copy_payload, snapshot, state_snapshot
from data.repositories.batch_external_context_repo import BatchExternalContextRepository
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository

from .template_lineage_query import (
    TemplateLineageQuery,
    check_evidence_size,
    lineage_available,
)


def _instance_row(row):
    if row is None or any(row[key] is None for key in ("operation_ref", "batch_ref", "part_ref")):
        raise WorkbenchCommandRejected("template_lineage_unavailable", "这道批次工序或它所属的批次、零件缺少记录，模板来源没有自动补上，这次没有保存。请刷新后重试；仍不行请联系维护人员。")
    return row


def _template_row(row):
    if row is None or row["template_operation_ref"] is None or row["part_ref"] is None:
        raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板的记录已失效或找不到了，系统不会按图号或工序号猜着匹配，这次没有复制。请刷新后重新选择。")
    return row


def _entity_facts(facts):
    return {(row["kind"], row["entity_key"]): row for row in facts["WorkbenchEntityRefs"] if row["active"]}


def _template_facts(facts, entities, *, target_ids=None):
    rows = {str(row["id"]): row for row in facts["PartOperations"]
            if target_ids is None or row["id"] in target_ids}
    result = {}
    for (kind, key), identity in entities.items():
        if kind != "template_operation" or (target_ids is not None and key not in rows):
            continue
        row = rows.get(key)
        part = entities.get(("part", row["part_no"])) if row is not None else None
        result[identity["ref"]] = dict(row or {"id": None}, template_operation_ref=identity["ref"],
            template_revision=identity["revision"], part_ref=part["ref"] if part else None)
    return result


def _instance_facts(facts, entities):
    batches = {row["batch_id"]: row for row in facts["Batches"]}
    result = {}
    for row in facts["BatchOperations"]:
        batch = batches.get(row["batch_id"])
        if batch is None:
            continue
        batch_ref = entities.get(("batch", batch["batch_id"]))
        part_ref = entities.get(("part", batch["part_no"]))
        ref = facts["operation_refs"].get(row["id"])
        if ref is not None:
            result[ref] = dict(row, operation_ref=ref, quantity=batch["quantity"],
                batch_ref=batch_ref["ref"] if batch_ref else None, part_ref=part_ref["ref"] if part_ref else None)
    return result


@dataclass(frozen=True)
class _PreparedTemplate:
    row: dict
    encoded: str


@dataclass(frozen=True)
class _PreparedInstance:
    row: dict
    context: Optional[dict]
    origin: Optional[dict]
    template: Optional[dict]
    source_event_id: Optional[int]
    source_eligible: bool


class TemplateLineageWriter:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchTemplateLineageRepository(conn)
        self.contexts = BatchExternalContextRepository(conn)

    def require_ready(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Template lineage writes require a caller transaction.")
        if not lineage_available(self.repo):
            raise WorkbenchCommandRejected("template_lineage_schema_missing", "模板来源记录的数据表还没安装，这次复制没有执行。请先完成统一版本升级后重试。")
        if self.repo.identity_schema_broken():
            raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板或批次的记录结构已损坏，这次复制没有执行，系统没有用不可靠的版本继续。请联系维护人员。")

    def prepare_templates(self, rows, *, facts):
        """Capture fixed raw templates once for this caller transaction."""
        self.require_ready()
        target_ids = {row["id"] for row in rows}
        entities = _entity_facts(facts)
        templates = _template_facts(facts, entities, target_ids=target_ids)
        by_id = {row["id"]: row for row in templates.values() if row["id"] is not None}
        rows = [_template_row(by_id.get(row["id"])) for row in rows]
        return [_PreparedTemplate(row, snapshot(row)) for row in rows]

    def copy_prepared_template(self, batch_id, prepared):
        self.require_ready()
        template = prepared.row
        instance = _instance_row(self.repo.insert_instance(copy_payload(template, batch_id, from_template=True)))
        if instance["part_ref"] != template["part_ref"]:
            raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次不是这个来源模板的零件，系统没有按图号猜着匹配，这次没有复制。请重新选择批次。")
        if instance["source"] == "external":
            if not self.contexts.mark_template_copy(instance["id"]):
                raise WorkbenchCommandRejected("external_context_missing", "没有保存这道外协工序的周期记录，这次没有复制。请先完成版本升级。")
        self._record_new_origin(instance, template, prepared.encoded)
        return instance["id"]

    def prepare_instances(self, rows, *, facts):
        """Capture source identities, contexts and lineage together, before any source write."""
        self.require_ready()
        rows = list(rows)
        entities = _entity_facts(facts)
        current = _instance_facts(facts, entities)
        templates = _template_facts(facts, entities)
        by_id = {row["id"]: row for row in current.values()}
        rows = [_instance_row(by_id.get(row["id"])) for row in rows]
        external_ids = {row["id"] for row in rows if row["source"] == "external"}
        contexts = {}
        if external_ids:
            captured = facts["BatchExternalContexts"]
            contexts = {row["operation_id"]: row for row in captured if row["operation_id"] in external_ids}
            if set(contexts) != external_ids:
                raise WorkbenchCommandRejected("external_context_missing", "原工序缺少外协周期记录，不能按当前模板猜着复制。请先核对原批次。")
        query = TemplateLineageQuery(self.conn, repo=self.repo)
        lineage = query.read([row["operation_ref"] for row in rows], current=current, templates=templates)
        prepared = []
        for row in rows:
            ref = row["operation_ref"]
            origin = lineage["origins"].get(ref)
            source = query.prepared_origin(ref) if origin is not None else None
            prepared.append(_PreparedInstance(row, contexts.get(row["id"]), origin,
                source.template if source else None, source.last_event_id if source else None,
                not lineage["problems"][ref] if source else True))
        return prepared

    def copy_prepared_instance(self, batch_id, prepared):
        self.require_ready()
        original = prepared.row
        instance = _instance_row(self.repo.insert_instance(copy_payload(original, batch_id, from_template=False)))
        if original["source"] == "external":
            if original["part_ref"] != instance["part_ref"]:
                raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次不是原外协周期记录的零件，这次没有复制。")
            self.contexts.copy_captured(cast(dict, prepared.context), instance["id"])
        origin = prepared.origin
        # Known but polluted origins remain known and polluted after copying.
        if origin is not None:
            template = cast(dict, prepared.template)
            if instance["part_ref"] != template["part_ref"]:
                raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次不是原来源模板的零件，这次没有复制。请重新选择批次。")
            self._record_new_origin(instance, template, origin["template_snapshot"], source=origin,
                source_event_id=prepared.source_event_id, source_eligible=prepared.source_eligible)
        return instance["id"]

    def _record_new_origin(self, instance, template, template_snapshot, *, source=None, source_event_id=None, source_eligible=True):
        encoded = state_snapshot(instance)
        check_evidence_size(len(template_snapshot.encode("ascii")) + len(encoded.encode("ascii")))
        return self.repo.append_origin(instance, template, template_snapshot, encoded, birth_event_id=instance["birth_event_id"],
                                       source=source, source_event_id=source_event_id, source_eligible=source_eligible)
