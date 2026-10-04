"""Explicit raw template copies and guarded resource edits, without default hours."""

from core.models.resource_capabilities import supports_source
from core.models.workbench_batch import normalize_operation_input, object_fields
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.personnel.operator_qualification import OperatorQualificationService
from core.services.process.workflow_state import require_template_ready
from core.services.workbench.calibration.template_lineage import TemplateLineageWriter
from data.repositories.batch_operation_repo import BatchOperationRepository
from data.repositories.supplier_repo import SupplierRepository

from .facts import BatchFacts, require_unreferenced
from .projection import BatchProjection
from .template_preview import template_after, template_changes
from .template_validation import template_status


def operation_code(batch_id, sequence, piece):
    return batch_id + "_" + str(sequence).zfill(2) + ("_" + piece if piece is not None else "")


def insert_operation(conn, batch_id, row, *, template=False, writer=None):
    """Avoid BatchOperation.from_row, whose legacy null-hours coercion is lossy.

    一条命令复制多道工序时传同一个 writer，表结构只校验一次（改过表结构会重验）。
    """
    writer = writer if writer is not None else TemplateLineageWriter(conn)
    return writer.copy_template(batch_id, row["id"]) if template else writer.copy_instance(batch_id, row["id"])


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

    def sync_preview(self, ref, payload):
        self.normalize_sync(payload)
        batch = self.reader.batch(ref)
        facts = self.reader.load()
        require_unreferenced(facts, batch)
        bound = {row["operation_id"] for row in facts.get("BatchMaterialStages", [])}
        if any(row["id"] in bound for row in facts["BatchOperations"] if row["batch_id"] == batch["batch_id"]):
            raise WorkbenchCommandRejected("constraint_conflict", "物料需求已绑定本批使用工序，请先在物料需求中改为开工前用料，再更新工艺并重新选择使用工序。")
        status = template_status(facts, batch)
        if status["diagnostics"]:
            raise WorkbenchCommandRejected("constraint_conflict", "\n".join(row["message"] for row in status["diagnostics"]))
        require_template_ready(self.conn, batch["part_no"])
        rows = [row for row in facts["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
        projection = BatchProjection(facts)
        before = projection.entity(batch)
        after = template_after(rows, facts, projection)
        return {"entity_ref": ref, "business_code": batch["batch_id"], "operation": "batch.sync_confirm", "completeness_checked": True,
                "before": before["operations"], "after": after, **template_changes(before["operations"], after),
                "warnings": [], "commit_policy": "atomic"}

    def sync(self, ref, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("工序同步必须由工作台命令事务持有。")
        preview = self.sync_preview(ref, payload)
        writer = TemplateLineageWriter(self.conn)
        writer.require_ready()
        batch = self.reader.batch(ref)
        rows = [row for row in self.reader.load()["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
        BatchOperationRepository(self.conn).delete_by_batch(batch["batch_id"])
        for row in rows:
            insert_operation(self.conn, batch["batch_id"], row, template=True, writer=writer)
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"], "operation_count": len(rows)}, preview["warnings"])

    def update(self, ref, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("工序编辑必须由工作台命令事务持有。")
        payload = normalize_operation_input(payload)
        batch, facts = self.reader.batch(ref), self.reader.load()
        require_unreferenced(facts, batch)
        row = next((row for row in facts["BatchOperations"] if row["batch_id"] == batch["batch_id"]
                    and facts["operation_refs"][row["id"]] == payload["operation_ref"]), None)
        if row is None:
            raise WorkbenchCommandRejected("entity_not_found", "工序已失效或不属于该批次，不能按序号猜测替换。", 404)
        internal = row["source"] == "internal"
        changes = self._changes(row, payload["fields"], internal)
        desired = {**row, **changes}
        self._validate(batch, desired, internal, changes)
        changes = {key: value for key, value in changes.items() if row[key] != value}
        if changes:
            BatchOperationRepository(self.conn).update(row["id"], changes)
        return WorkbenchCommandOutcome("committed" if changes else "unchanged", {"entity_ref": ref,
                                       "business_code": batch["batch_id"], "operation_ref": payload["operation_ref"]})

    def _changes(self, row, fields, internal):
        allowed = ("machine_ref", "operator_ref", "setup_hours", "unit_hours") if internal else ("supplier_ref", "external_days")
        if row["source"] not in ("internal", "external") or set(fields) - set(allowed):
            raise WorkbenchCommandRejected("invalid_input", "要改的项和这道工序的归属对不上：自制和外协能改的内容不一样。", 422)
        changes = {}
        for key, value in fields.items():
            if key.endswith("_ref"):
                kind = key[:-4]
                changes[kind + "_id"] = self.reader.resolve(value, kind).entity_key if value is not None else None
            else:
                changes["ext_days" if key == "external_days" else key] = value
        return changes

    def _validate(self, batch, row, internal, changes):
        projection = BatchProjection(self.reader.load())
        work_type = projection.catalogs["op_type"].get(row["op_type_id"])
        if work_type is None or not supports_source(work_type["category"], row["source"]):
            raise WorkbenchCommandRejected("constraint_conflict", "该工种不支持本序归属，请先核对工艺。")
        for kind in ("machine", "operator") if internal else ("supplier",):
            key = row[kind + "_id"]
            if key is not None:
                resource = projection.catalogs[kind].get(key)
                if resource is None or resource["status"] != "active":
                    raise WorkbenchCommandRejected("constraint_conflict", "所选设备、人员或供应商当前不可用。")
        if internal:
            self._validate_internal(projection, row)
        else:
            self._validate_external(projection, batch, row, changes)

    def _validate_internal(self, projection, row):
        machine = projection.catalogs["machine"].get(row["machine_id"])
        if machine and row["op_type_id"] not in projection.machine_types.get(row["machine_id"], set()):
            raise WorkbenchCommandRejected("constraint_conflict", "设备与工序工种不匹配。")
        if row["operator_id"]:
            OperatorQualificationService(self.conn, self.logger).require(operator_id=row["operator_id"],
                op_type_id=row["op_type_id"], machine_id=row["machine_id"])

    def _validate_external(self, projection, batch, row, changes):
        group = projection.group(batch, row)
        if group and group["merge_mode"] == "merged" and "ext_days" in changes:
            raise WorkbenchCommandRejected("constraint_conflict", "合并外协组不能逐道改周期；请保留整组周期规则。")
        if group and group["merge_mode"] == "merged" and "supplier_id" in changes:
            raise WorkbenchCommandRejected("constraint_conflict", "合并外协段不能单独更换供应商。请在工艺资料中整段改派，再预检并更新本批次工序。")
        if row["supplier_id"]:
            capable = {(r["supplier_id"], r["op_type_id"]) for r in SupplierRepository(self.conn).list_capabilities(status="active") if not r["missing_supplier"]}
            if (row["supplier_id"], row["op_type_id"]) not in capable:
                raise WorkbenchCommandRejected("constraint_conflict", "这家供应商没有登记这道外协工序的能力。")
