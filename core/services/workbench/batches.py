"""Batch CRUD through BatchService, owned by the common command transaction."""

from core.models.workbench_batch import normalize_batch_input
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.scheduler.batch_service import BatchService
from core.services.workbench.batch_facts import BatchFacts, related, require_unreferenced


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
            require_unreferenced(self.facts.load(), batch)
            if related(self.facts.load(), batch)["materials"]:
                raise WorkbenchCommandRejected("constraint_conflict", "这个批次还挂着物料需求，不能直接删除。")
            self.domain.delete(batch["batch_id"])
        else:
            changes = {key: value for key, value in payload["fields"].items() if batch[key] != value}
            if not changes:
                return WorkbenchCommandOutcome("unchanged", {"entity_ref": ref, "business_code": batch["batch_id"]})
            if "quantity" in changes:
                require_unreferenced(self.facts.load(), batch)
            self.domain.update(batch["batch_id"], **changes)
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"]})
