"""Batch CRUD through BatchService, owned by the common command transaction."""

from core.models.workbench_batch import normalize_batch_input
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.batch.service import BatchService

from .facts import BatchFacts, index_relations, related, require_deletable, require_unreferenced


class WorkbenchBatchService:
    def __init__(self, conn, logger=None, facts=None):
        self.conn = conn
        # A command route passes its guard reader, so checks before the first write reuse that load.
        self.facts = facts if facts is not None else BatchFacts(conn, logger)
        self.domain = BatchService(conn, logger=logger)

    @staticmethod
    def normalize(action, payload):
        return normalize_batch_input(action, payload)

    def apply(self, action, payload, ref=None, relations_index=None):
        """relations_index：调用方在本命令第一次写入前算好的 index_relations，逐行改数量时不再每行重读整本批次数据。"""
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
            return self._update(ref, batch, payload, relations_index)
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"]})

    def delete_many(self, refs, relations_index=None):
        """一条命令删多批：第一次写入前用同一份数据取齐并校验全部批次，删除过程中不再逐批重读整本批次数据。

        删掉一批只会减少记录，不会给别的批次新增引用、物料需求或拆分记录，所以写入前的校验整条命令内都成立。
        relations_index：调用方在本命令第一次写入前已算好的 index_relations（如批量预检的投影里那份），不再重建。
        """
        if not self.conn.in_transaction:
            raise RuntimeError("批次命令必须在 WorkbenchCommandService 最外层事务中执行。")
        if not refs:
            return []
        index = index_relations(self.facts.load()) if relations_index is None else relations_index
        batches = [self.facts.batch(ref) for ref in refs]
        for batch in batches:
            require_deletable(None, batch, index[batch["batch_id"]])
        for batch in batches:
            self.domain.delete(batch["batch_id"])
        return [WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"]})
                for ref, batch in zip(refs, batches)]


    def _update(self, ref, batch, payload, relations_index=None):
        changes = {key: value for key, value in payload["fields"].items() if batch[key] != value}
        if not changes:
            return WorkbenchCommandOutcome("unchanged", {"entity_ref": ref, "business_code": batch["batch_id"]})
        # Only quantity and readiness depend on related records; other field edits skip the whole-ledger read.
        if "quantity" in changes or "ready_status" in changes:
            relations = related(self.facts.load(), batch) if relations_index is None else relations_index[batch["batch_id"]]
            if "quantity" in changes:
                require_unreferenced(None, batch, relations)
            materials = relations["materials"]
            if materials and "ready_status" in changes and ("quantity" not in changes or changes["ready_status"] != "no"):
                raise WorkbenchCommandRejected("constraint_conflict", "此批次的齐套按物料需求计算，请在物料需求中核对需求量和到料量。")
            if materials and "quantity" in changes:
                changes["ready_status"] = "no"
        self.domain.update(batch["batch_id"], **changes)
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": batch["batch_id"]})
