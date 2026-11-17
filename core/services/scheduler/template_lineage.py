"""Shared template/instance copies; origin evidence never uses heuristic matches.

The repository reads identity rows and appends origin records. Fixed source preparation
and newly inserted birth origins belong to this caller's transaction.
"""

from dataclasses import dataclass
from typing import Optional, cast

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import copy_payload
from data.repositories.batch_external_context_repo import BatchExternalContextRepository
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository

from .template_lineage_query import TemplateLineageQuery


def _instance_row(row):
    if row is None or any(row[key] is None for key in ("operation_ref", "batch_ref", "part_ref")):
        raise WorkbenchCommandRejected(
            "template_lineage_unavailable",
            "这道批次工序或它所属的批次、零件缺少记录，模板来源没有自动补上，这次没有保存。请刷新后重试；仍不行请联系维护人员。",
        )
    return row


def _template_row(row):
    if row is None or row["template_operation_ref"] is None or row["part_ref"] is None:
        raise WorkbenchCommandRejected(
            "template_lineage_unavailable",
            "来源模板的记录已失效或找不到了，系统不会按图号或工序号猜着匹配，这次没有复制。请刷新后重新选择。",
        )
    return row


def _entity_facts(facts):
    return {(row["kind"], row["entity_key"]): row for row in facts["WorkbenchEntityRefs"] if row["active"]}


def _template_facts(facts, entities, *, target_ids):
    rows = {str(row["id"]): row for row in facts["PartOperations"] if row["id"] in target_ids}
    result = {}
    for (kind, key), identity in entities.items():
        if kind != "template_operation" or key not in rows:
            continue
        row = rows[key]
        part = entities.get(("part", row["part_no"]))
        result[identity["ref"]] = dict(
            row,
            template_operation_ref=identity["ref"],
            template_revision=identity["revision"],
            part_ref=part["ref"] if part else None,
        )
    return result


def _instance_facts(tables, entities, operation_refs):
    batches = {row["batch_id"]: row for row in tables["Batches"]}
    result = {}
    for row in tables["BatchOperations"]:
        batch = batches.get(row["batch_id"])
        if batch is None:
            continue
        batch_ref = entities.get(("batch", batch["batch_id"]))
        part_ref = entities.get(("part", batch["part_no"]))
        ref = operation_refs.get(row["id"])
        if ref is not None:
            result[ref] = dict(
                row,
                operation_ref=ref,
                quantity=batch["quantity"],
                batch_ref=batch_ref["ref"] if batch_ref else None,
                part_ref=part_ref["ref"] if part_ref else None,
            )
    return result


def instance_lineage_facts(tables, operation_refs):
    return _instance_facts(tables, _entity_facts(tables), operation_refs)


@dataclass(frozen=True)
class _PreparedTemplate:
    row: dict


@dataclass(frozen=True)
class _PreparedInstance:
    row: dict
    context: Optional[dict]
    origin: Optional[dict]
    source_eligible: bool


class TemplateLineageWriter:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchTemplateLineageRepository(conn)
        self.contexts = BatchExternalContextRepository(conn)

    def require_ready(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Template lineage writes require a caller transaction.")

    def prepare_templates(self, rows, *, facts):
        """Capture fixed raw templates once for this caller transaction."""
        self.require_ready()
        target_ids = {row["id"] for row in rows}
        entities = _entity_facts(facts)
        templates = _template_facts(facts, entities, target_ids=target_ids)
        by_id = {row["id"]: row for row in templates.values()}
        return [_PreparedTemplate(_template_row(by_id.get(row["id"]))) for row in rows]

    def copy_prepared_template(self, batch_id, prepared):
        self.require_ready()
        template = prepared.row
        instance = _instance_row(self.repo.insert_instance(copy_payload(template, batch_id, from_template=True)))
        if instance["part_ref"] != template["part_ref"]:
            raise WorkbenchCommandRejected(
                "template_lineage_mismatch",
                "目标批次不是这个来源模板的零件，系统没有按图号猜着匹配，这次没有复制。请重新选择批次。",
            )
        if instance["source"] == "external":
            if not self.contexts.mark_template_copy(instance["id"]):
                raise WorkbenchCommandRejected(
                    "external_context_missing",
                    "没有保存这道外协工序的周期记录，这次没有复制。请先完成版本升级。",
                )
        self.repo.append_origin(
            instance["operation_ref"],
            template["template_operation_ref"],
            template["template_revision"],
            source_eligible=True,
        )
        return instance["id"]

    def prepare_instances(self, rows, *, facts, complete_facts: bool):
        """Capture source identities, contexts and lineage together, before any source write."""
        if complete_facts:
            current = _instance_facts(facts, _entity_facts(facts), facts["operation_refs"])
        else:
            current = facts["template_lineage_capture"]["source_instances"]
        by_id = {row["id"]: row for row in current.values()}
        rows = [_instance_row(by_id.get(row["id"])) for row in rows]
        external_ids = {row["id"] for row in rows if row["source"] == "external"}
        contexts = {}
        if external_ids:
            captured = facts["BatchExternalContexts"]
            contexts = {row["operation_id"]: row for row in captured if row["operation_id"] in external_ids}
            if set(contexts) != external_ids:
                raise WorkbenchCommandRejected(
                    "external_context_missing",
                    "原工序缺少外协周期记录，不能按当前模板猜着复制。请先核对原批次。",
                )
        query = TemplateLineageQuery(self.conn, repo=self.repo)
        if complete_facts:
            lineage = query.read([row["operation_ref"] for row in rows])
        else:
            lineage = query.read_captured(facts["template_lineage_capture"])
        prepared = []
        for row in rows:
            ref = row["operation_ref"]
            origin = lineage["origins"].get(ref)
            prepared.append(
                _PreparedInstance(
                    row,
                    contexts.get(row["id"]),
                    origin,
                    not lineage["problems"][ref] if origin is not None else True,
                )
            )
        return prepared

    def copy_prepared_instance(self, batch_id, prepared):
        """batch_id is a copy of the source batch in this transaction, so both share one part identity."""
        self.require_ready()
        original = prepared.row
        instance = _instance_row(self.repo.insert_instance(copy_payload(original, batch_id, from_template=False)))
        if original["source"] == "external":
            self.contexts.copy_captured(cast(dict, prepared.context), instance["id"])
        origin = prepared.origin
        # Known but polluted origins remain known and polluted after copying.
        if origin is not None:
            self.repo.append_origin(
                instance["operation_ref"],
                origin["template_operation_ref"],
                origin["template_revision"],
                source_eligible=prepared.source_eligible,
            )
        return instance["id"]
