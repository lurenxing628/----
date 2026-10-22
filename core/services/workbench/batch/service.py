"""Prepare batch changes from one capture, then apply them in the command transaction."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.errors import BusinessError, ErrorCode, ValidationError
from core.models.batch import Batch
from core.models.workbench_batch import public_ref
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.services.batch.service import BatchService
from data.repositories.batch_repo import BatchRepository

from .facts import BatchFacts, index_relations, require_deletable, require_unreferenced


@dataclass
class BatchChange:
    action: str
    business_code: str
    entity_ref: Optional[str]
    fields: Dict[str, Any]
    created: Optional[Batch] = None


class BatchChangePreparation:
    """Current rows, identities and relations shared by every change before the first write."""

    def __init__(self, facts):
        self.facts = facts
        self.identities = {row["ref"]: row for row in facts["WorkbenchEntityRefs"] if row["active"]}
        self.batches = {row["batch_id"]: row for row in facts["Batches"]}
        self.parts = {row["part_no"]: row for row in facts["Parts"]}
        self.used_codes = set(self.batches)
        self._relations = None

    @property
    def relations(self):
        if self._relations is None:
            self._relations = index_relations(self.facts)
        return self._relations

    def resolve(self, ref, kind):
        public_ref(ref)
        identity = self.identities.get(ref)
        if identity is None or identity["kind"] != kind:
            raise WorkbenchCommandRejected("entity_not_found", "这条记录已经不在了，请刷新后重新选择。", 404)
        key = identity["entity_key"]
        if key != key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "批次号或图号存在首尾空格，请先核对原记录。")
        return key

    def batch(self, ref):
        key = self.resolve(ref, "batch")
        row = self.batches.get(key)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "批次和系统编号对不上，请联系维护人员核对资料。", 500)
        return row

    def prepare(self, action, payload, ref=None):
        """Consume the normalized command input; no further input conversion during apply."""
        if action == "create":
            part_no = self.resolve(payload["part_ref"], "part")
            part = self.parts.get(part_no)
            if part is None:
                raise WorkbenchCommandRejected("storage_failure", "零件和系统编号对不上，请联系维护人员核对资料。", 500)
            return self.create(Batch(batch_id=payload["business_code"], part_no=part_no,
                                     part_name=part["part_name"], **payload["fields"]))
        batch = self.batch(ref)
        code = batch["batch_id"]
        if action == "delete":
            require_deletable(self.relations[code])
            self.used_codes.remove(code)
            return BatchChange(action, code, ref, {})
        changes = {key: value for key, value in payload["fields"].items() if batch[key] != value}
        if "quantity" in changes or "ready_status" in changes:
            relations = self.relations[code]
            if "quantity" in changes:
                require_unreferenced(relations)
            if relations["materials"]:
                if "ready_status" in changes and ("quantity" not in changes or changes["ready_status"] != "no"):
                    raise WorkbenchCommandRejected("constraint_conflict", "此批次的齐套按物料需求计算，请在物料需求中核对需求量和到料量。")
                if "quantity" in changes:
                    changes["ready_status"] = "no"
        return BatchChange(action, code, ref, changes)

    def create(self, batch):
        if batch.batch_id in self.used_codes:
            raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS,
                f"批次号“{batch.batch_id}”已存在，这次没有保存。请改用别的批次号，或去修改已有的那个批次。")
        self.used_codes.add(batch.batch_id)
        return BatchChange("create", batch.batch_id, None, {}, batch)

    def copy(self, source, code, *, quantity=None, ready_status="no", ready_date=None):
        """Copies keep the existing legacy date/text normalization, using the captured part."""
        svc = BatchService
        quantity = svc._normalize_int(source["quantity"] if quantity is None else quantity, field="数量")
        if quantity <= 0:
            raise ValidationError("“数量”必须大于 0", field="数量")
        part_name = svc._normalize_text(source["part_name"]) or self.parts[source["part_no"]]["part_name"]
        priority = svc._normalize_text(source["priority"]) or "normal"
        svc._validate_enum(priority, ("normal", "urgent", "critical"), "优先级")
        return self.create(Batch(batch_id=code, part_no=source["part_no"], part_name=part_name,
            quantity=quantity, due_date=svc._normalize_date(source["due_date"]),
            priority=priority, ready_status=ready_status, ready_date=ready_date,
            remark=svc._normalize_text(source["remark"])))


class WorkbenchBatchService:
    def __init__(self, conn, logger=None, facts=None):
        self.conn = conn
        self.facts = facts if facts is not None else BatchFacts(conn, logger)
        self.repo = BatchRepository(conn, logger=logger)

    def preparation(self, facts=None):
        return BatchChangePreparation(self.facts.load() if facts is None else facts)

    def apply_prepared(self, change):
        if not self.conn.in_transaction:
            raise RuntimeError("批次命令必须在 WorkbenchCommandService 最外层事务中执行。")
        ref = change.entity_ref
        if change.action == "create":
            self.repo.create(change.created)
            identity = self.facts.identities.find_active("batch", change.business_code)
            if identity is None:
                raise RuntimeError("新增批次没有永久引用。")
            ref = identity.ref
        elif change.action == "delete":
            self.repo.delete(change.business_code)
        elif change.fields:
            self.repo.update(change.business_code, change.fields)
        result = "unchanged" if change.action == "update" and not change.fields else "committed"
        return WorkbenchCommandOutcome(result, {"entity_ref": ref, "business_code": change.business_code})
