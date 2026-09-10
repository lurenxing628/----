"""Explicit raw template copies and guarded resource edits, without default hours."""

from core.models.workbench_batch import normalize_operation_input, object_fields
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.personnel.operator_qualification import OperatorQualificationService
from core.services.process.workflow_state import require_template_ready
from core.services.workbench.batch_facts import BatchFacts, require_unreferenced
from core.services.workbench.batch_projection import BatchProjection
from core.services.workbench.batch_template_validation import template_diagnostics
from core.services.workbench.template_lineage import TemplateLineageWriter
from data.repositories.batch_operation_repo import BatchOperationRepository
from data.repositories.supplier_repo import SupplierRepository


def operation_code(batch_id, sequence, piece):
    return batch_id + "_" + str(sequence).zfill(2) + ("_" + piece if piece is not None else "")


def insert_operation(conn, batch_id, row, *, template=False):
    """Avoid BatchOperation.from_row, whose legacy null-hours coercion is lossy."""
    writer = TemplateLineageWriter(conn)
    return writer.copy_template(batch_id, row["id"]) if template else writer.copy_instance(batch_id, row["id"])


class WorkbenchBatchOperationService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.reader = BatchFacts(conn, logger)

    @staticmethod
    def normalize_sync(payload):
        object_fields(payload, ("strict_mode",), ("strict_mode",))
        if type(payload["strict_mode"]) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "资料不完整时停止刷新必须为明确开关。", 400)
        return dict(payload)

    def sync_preview(self, ref, payload):
        payload = self.normalize_sync(payload)
        batch = self.reader.batch(ref)
        facts = self.reader.load()
        require_unreferenced(facts, batch)
        require_template_ready(self.conn, batch["part_no"])
        rows = [row for row in facts["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
        if not rows:
            raise WorkbenchCommandRejected("constraint_conflict", "当前零件没有有效模板工序；未自动解析路线或覆盖原工序。")
        diagnostics = template_diagnostics(rows, facts, batch)
        if payload["strict_mode"] and diagnostics:
            raise WorkbenchCommandRejected("constraint_conflict", "模板资料不完整，已按严格选项停止刷新。")
        projection = BatchProjection(facts)
        before = projection.entity(batch)
        return {"entity_ref": ref, "business_code": batch["batch_id"], "operation": "batch.sync_confirm", "strict_mode": payload["strict_mode"],
                "before": before["operations"], "after": [{"sequence": row["seq"], "label": row["op_type_name"],
                    "source": row["source"], "setup_hours": row["setup_hours"], "unit_hours": row["unit_hours"], "external_days": row["ext_days"],
                    "machine_ref": None, "operator_ref": None, "supplier_ref": projection.ref("supplier", row["supplier_id"])} for row in rows],
                "warnings": diagnostics, "commit_policy": "atomic"}

    def sync(self, ref, payload):
        if not self.conn.in_transaction:
            raise RuntimeError("工序同步必须由工作台命令事务持有。")
        preview = self.sync_preview(ref, payload)
        TemplateLineageWriter(self.conn).require_ready()
        batch = self.reader.batch(ref)
        rows = [row for row in self.reader.load()["PartOperations"] if row["part_no"] == batch["part_no"] and row["status"] == "active"]
        BatchOperationRepository(self.conn).delete_by_batch(batch["batch_id"])
        for row in rows:
            insert_operation(self.conn, batch["batch_id"], row, template=True)
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
            raise WorkbenchCommandRejected("invalid_input", "工序字段与实际归属不匹配。", 422)
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
        if machine and machine["op_type_id"] != row["op_type_id"]:
            raise WorkbenchCommandRejected("constraint_conflict", "设备与工序工种不匹配。")
        if row["operator_id"]:
            OperatorQualificationService(self.conn, self.logger).require(operator_id=row["operator_id"],
                op_type_id=row["op_type_id"], machine_id=row["machine_id"])

    def _validate_external(self, projection, batch, row, changes):
        group = projection.group(batch, row)
        if group and group["merge_mode"] == "merged" and "ext_days" in changes:
            raise WorkbenchCommandRejected("constraint_conflict", "合并外协组不能逐道改周期；请保留整组周期规则。")
        if row["supplier_id"]:
            capable = {(r["supplier_id"], r["op_type_id"]) for r in SupplierRepository(self.conn).list_capabilities(status="active") if not r["missing_supplier"]}
            if (row["supplier_id"], row["op_type_id"]) not in capable:
                raise WorkbenchCommandRejected("constraint_conflict", "供应商未登记本外协工种能力。")
