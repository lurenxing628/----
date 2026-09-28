"""Batch CRUD through BatchService, owned by the common command transaction."""

from core.models.workbench_batch import normalize_batch_input
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.batch.service import BatchService

from .facts import BatchFacts, related, require_deletable, require_unreferenced


class WorkbenchBatchService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.facts = BatchFacts(conn, logger)
        self.domain = BatchService(conn, logger=logger)

    @staticmethod
    def normalize(action, payload):
        return normalize_batch_input(action, payload)

    def apply(self, action, payload, ref=None):
        if not self.conn.in_transaction:
            raise RuntimeError("批次命令必须在 WorkbenchCommandService 最外层事务中执行。")
        payload = self.normalize(action, payload)
        if action == "create":
            part = self.facts.resolve(payload["part_ref"], "part")
            if part.entity_key != part.entity_key.strip():
                raise WorkbenchCommandRejected("constraint_conflict", "原图号含首尾空格，请先核对。")
            batch = self.domain.create(payload["business_code"], part.entity_key, **payload["fields"])
            identity = self.facts.identities.find_active("batch", batch.batch_id)
            if identity is None:
                raise RuntimeError("新增批次没有永久引用。")
            return WorkbenchCommandOutcome("committed", {"entity_ref": identity.ref, "business_code": batch.batch_id})
        batch = self.facts.batch(ref)
        if action == "delete":
            require_deletable(self.facts.load(), batch)
            self.domain.delete(batch["batch_id"])
        else:
            return self._update(ref, batch, payload)
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"]})


    def _update(self, ref, batch, payload):
        changes = {key: value for key, value in payload["fields"].items() if batch[key] != value}
        if not changes:
            return WorkbenchCommandOutcome("unchanged", {"entity_ref": ref, "business_code": batch["batch_id"]})
        if "quantity" in changes:
            require_unreferenced(self.facts.load(), batch)
        materials = related(self.facts.load(), batch)["materials"]
        if materials and "ready_status" in changes and ("quantity" not in changes or changes["ready_status"] != "no"):
            raise WorkbenchCommandRejected("constraint_conflict", "此批次的齐套按物料需求计算，请在物料需求中核对需求量和到料量。")
        if materials and "quantity" in changes:
            changes["ready_status"] = "no"
        self.domain.update(batch["batch_id"], **changes)
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"]})
