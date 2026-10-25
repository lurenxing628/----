"""Explicit raw template copies and guarded resource edits, without default hours."""

from dataclasses import dataclass

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.resource_capabilities import supports_source
from core.models.workbench_batch import object_fields
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    group_from_context,
    member_index,
    merged_supplier_problem,
)
from core.services.scheduler.template_lineage import TemplateLineageWriter
from data.repositories.batch_operation_repo import BatchOperationRepository

from .facts import BatchFacts, index_relations, require_unreferenced
from .projection import BatchProjection
from .resource_choices import BatchResourceFacts
from .template_preview import template_after, template_changes
from .template_validation import template_status


@dataclass
class BatchOperationChange:
    entity_ref: str
    business_code: str
    operation_ref: str
    operation_id: int
    fields: dict


class WorkbenchBatchOperationService:
    def __init__(self, conn, logger=None, reader=None):
        self.conn = conn
        self.logger = logger
        self.reader = reader if reader is not None else BatchFacts(conn, logger)

    @staticmethod
    def normalize_sync(payload):
        object_fields(payload, ("strict_mode",))
        if "strict_mode" in payload and type(payload["strict_mode"]) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "更新选项无效，请刷新页面后重试。", 400)
        if payload.get("strict_mode") is False:
            raise WorkbenchCommandRejected("template_validation_required", "更新工序前必须检查工艺资料。请刷新页面后重新预检更新。")
        # Older strict clients remain valid; replacement always checks completeness.
        return {}

    def _prepare_sync(self, batch, facts, *, relations, resources):
        require_unreferenced(relations)
        bound = {row["operation_id"] for row in facts["BatchMaterialStages"]}
        if any(row["id"] in bound for row in relations["operations"]):
            raise WorkbenchCommandRejected("constraint_conflict", "物料需求已绑定本批使用工序，请先在物料需求中改为开工前用料，再更新工艺并重新选择使用工序。")
        rows = [row for row in facts["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
        status = template_status(facts, batch, resources, rows=rows)
        if status["diagnostics"]:
            raise WorkbenchCommandRejected("constraint_conflict", "\n".join(row["message"] for row in status["diagnostics"]))
        return rows

    def sync_preview_normalized(self, ref):
        batch, facts = self.reader.batch(ref), self.reader.load()
        projection = BatchProjection(facts)
        rows = self._prepare_sync(batch, facts, relations=projection.relations[batch["batch_id"]], resources=projection.resources)
        before = projection.entity(batch)
        after = template_after(rows, facts, projection)
        return {"entity_ref": ref, "business_code": batch["batch_id"], "operation": "batch.sync_confirm", "completeness_checked": True,
                "before": before["operations"], "after": after, **template_changes(before["operations"], after),
                "warnings": [], "commit_policy": "atomic"}

    def sync_normalized(self, ref):
        if not self.conn.in_transaction:
            raise RuntimeError("工序同步必须由工作台命令事务持有。")
        batch, facts = self.reader.batch(ref), self.reader.load()
        rows = self._prepare_sync(batch, facts, relations=index_relations(facts)[batch["batch_id"]], resources=BatchResourceFacts(facts))
        writer = TemplateLineageWriter(self.conn)
        prepared = writer.prepare_templates(rows, facts=facts)
        BatchOperationRepository(self.conn).delete_by_batch(batch["batch_id"])
        for row in prepared:
            writer.copy_prepared_template(batch["batch_id"], row)
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"], "operation_count": len(rows)})

    def prepare_update(self, ref, payload):
        """The command's normalized input and current facts produce the actual field changes."""
        if not self.conn.in_transaction:
            raise RuntimeError("工序编辑必须由工作台命令事务持有。")
        batch, facts = self.reader.batch(ref), self.reader.load()
        relations = index_relations(facts)[batch["batch_id"]]
        require_unreferenced(relations)
        row = next((row for row in relations["operations"]
                    if facts["operation_refs"][row["id"]] == payload["operation_ref"]), None)
        if row is None:
            raise WorkbenchCommandRejected("entity_not_found", "工序已失效或不属于该批次，不能按序号猜测替换。", 404)
        internal = row["source"] == "internal"
        changes = self._changes(row, payload["fields"], internal)
        actual_changes = {key: value for key, value in changes.items() if row[key] != value}
        desired = {**row, **actual_changes}
        self._validate(facts, batch, desired, internal, actual_changes, relations["operations"])
        return BatchOperationChange(ref, batch["batch_id"], payload["operation_ref"], row["id"], actual_changes)

    def apply_update(self, change):
        if not self.conn.in_transaction:
            raise RuntimeError("工序编辑必须由工作台命令事务持有。")
        if change.fields:
            BatchOperationRepository(self.conn).update(change.operation_id, change.fields)
        return WorkbenchCommandOutcome("committed" if change.fields else "unchanged", {"entity_ref": change.entity_ref,
                                       "business_code": change.business_code, "operation_ref": change.operation_ref})

    def _changes(self, row, fields, internal):
        allowed = ("machine_ref", "operator_ref", "setup_hours", "unit_hours") if internal else ("supplier_ref", "external_days")
        if row["source"] not in OPERATION_SOURCES or set(fields) - set(allowed):
            raise WorkbenchCommandRejected("invalid_input", "要改的项和这道工序的归属对不上：自制和外协能改的内容不一样。", 422)
        changes = {}
        for key, value in fields.items():
            if key.endswith("_ref"):
                kind = key[:-4]
                changes[kind + "_id"] = self.reader.resolve(value, kind).entity_key if value is not None else None
            else:
                changes["ext_days" if key == "external_days" else key] = value
        return changes

    def _validate(self, facts, batch, row, internal, changes, operations):
        resources = BatchResourceFacts(facts)
        work_type = resources.catalogs["op_type"].get(row["op_type_id"])
        if work_type is None or not supports_source(work_type["category"], row["source"]):
            raise WorkbenchCommandRejected("constraint_conflict", "该工种不支持本序归属，请先核对工艺。")
        for kind in ("machine", "operator") if internal else ("supplier",):
            key = row[kind + "_id"]
            if key is not None:
                resource = resources.catalogs[kind].get(key)
                if resource is None or resource["status"] != "active":
                    raise WorkbenchCommandRejected("constraint_conflict", "所选设备、人员或供应商当前不可用。")
        if internal:
            self._validate_internal(resources, row)
        else:
            self._validate_external(resources, facts, batch, row, changes, operations)

    def _validate_internal(self, resources, row):
        machine = resources.catalogs["machine"].get(row["machine_id"])
        if machine and row["op_type_id"] not in resources.machine_types.get(row["machine_id"], set()):
            raise WorkbenchCommandRejected("constraint_conflict", "设备与工序工种不匹配。")
        resources.require_operator(row["operator_id"], row["op_type_id"], row["machine_id"])

    def _validate_external(self, resources, facts, batch, row, changes, operations):
        contexts = {item["operation_id"]: item for item in facts["BatchExternalContexts"]}
        context = contexts.get(row["id"])
        problem = context_problem(context, operation_id=row["id"], part_no=batch["part_no"], sequence=row["seq"])
        if problem is not None:
            raise WorkbenchCommandRejected("constraint_conflict", problem)
        group = group_from_context(context)
        if group and group["merge_mode"] == "merged":
            if "ext_days" in changes:
                raise WorkbenchCommandRejected("constraint_conflict", "合并外协组不能逐道改周期；请保留整组周期规则。")
            if "supplier_id" in changes:
                raise WorkbenchCommandRejected("constraint_conflict", "合并外协段不能单独更换供应商。请在工艺资料中整段改派，再预检并更新本批次工序。")
            members = member_index(contexts, operations)
            problem = merged_supplier_problem(
                context,
                row["supplier_id"],
                members.get((row["batch_id"], context_group_key(context), row["piece_id"])),
            )
            if problem is not None:
                raise WorkbenchCommandRejected("constraint_conflict", problem)
        if row["supplier_id"]:
            if not resources.supplier_capable(row["supplier_id"], row["op_type_id"]):
                raise WorkbenchCommandRejected("constraint_conflict", "这家供应商没有登记这道外协工序的能力。")
