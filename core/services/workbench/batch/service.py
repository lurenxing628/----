"""Prepare batch changes from bounded captures, then apply them in the command transaction."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, cast

from core.errors import BusinessError, ErrorCode, ValidationError
from core.models.batch import Batch
from core.models.workbench_batch import normalize_batch_fields, public_ref, text
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from data.repositories.batch_repo import BatchRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository

from .facts import index_relations, require_deletable, require_unreferenced
from .scope import BatchFactScope

# 齐套状态不在这里：复制、拆分写入的齐套状态都是本次算出的内部值，不读原批次。
# 优先级也不在这里：库里的优先级由 Batches.priority 的值域约束保证合法，复制、拆分沿用时不会被拒。
_STORED_LABELS = {"fields.quantity": "数量", "fields.due_date": "交期", "fields.ready_date": "齐套日期",
                  "fields.remark": "备注", "part_name": "零件名称"}


@contextmanager
def stored_batch_values(ref, source, verb):
    """复制、拆分沿用原批次在库里的值；准入不过时点名是哪个原批次的哪一项，不当成这次填错。"""
    try:
        yield
    except ValidationError as exc:
        field = cast(str, exc.field)
        code, label = source["batch_id"], _STORED_LABELS[field]
        remedy = ("零件名称在批次里改不了，请联系维护人员核对这个批次的资料。" if field == "part_name"
                  else f"请先打开这个批次，把{label}核对改好后再{verb}。")
        raise WorkbenchCommandRejected(
            "constraint_conflict", f"原批次“{code}”在系统里存的{label}不对，这次没有{verb}。{remedy}",
            conflicts=[{"entity_ref": ref, "business_code": code, "field": field}]) from exc


@dataclass
class BatchChange:
    action: str
    business_code: str
    entity_ref: Optional[str]
    fields: Dict[str, Any]
    created: Optional[Batch] = None


class BatchChangePreparation:
    """Current rows, identities and relations shared by every change before the first write."""

    scope: BatchFactScope
    facts: Any

    def __init__(
        self,
        scope: BatchFactScope,
        *,
        tables: Optional[Dict[str, Any]] = None,
        relation_refs: Optional[Sequence[str]] = None,
    ):
        self.scope = scope
        self.facts = scope.current_facts()
        self._relation_refs = tuple(relation_refs) if relation_refs is not None else None
        if self.facts is None and tables is None and scope.mode in ("single_instance", "single_create"):
            self.identities = {}
            self.batches = {}
            self.parts = {}
            self.used_codes = set()
        else:
            loaded = tables if tables is not None else (self.facts if self.facts is not None else scope.entity_tables())
            self.identities = {row["ref"]: row for row in loaded["WorkbenchEntityRefs"] if row["active"]}
            self.batches = {row["batch_id"]: row for row in loaded["Batches"]}
            self.parts = {row["part_no"]: row for row in loaded["Parts"]}
            self.used_codes = set(loaded.get("batch_codes", self.batches))
        self._relations = None

    @property
    def relations(self):
        if self._relations is None:
            if self.facts is None:
                if self._relation_refs is not None:
                    revisions = self.scope.revisions or self.scope.reader.read_revisions()
                    raw = self.scope.reader.capture_closure(self._relation_refs, revisions=revisions)
                    self.facts = self.scope.reader.project_captured(raw, material_day=self.scope.material_day)
                else:
                    self.facts = self.scope.load()
            self._relations = index_relations(self.facts)
        return self._relations

    def resolve(self, ref, kind):
        public_ref(ref)
        identity = self.identities.get(ref)
        if identity is None or identity["kind"] != kind:
            raise WorkbenchCommandRejected("entity_not_found", "这条记录已经不在了，请刷新后重新选择。", 404)
        key = identity["entity_key"]
        if not key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "批次号或图号不能为空，请先核对原记录。")
        return key

    def _resolve_single_part(self, part_ref: str) -> Dict[str, Any]:
        identity = self.scope.resolve(part_ref, "part")
        part_no = identity.entity_key
        if not part_no.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "批次号或图号不能为空，请先核对原记录。")
        part = self.scope.reader.repo.part_row(part_no)
        if part is None:
            raise WorkbenchCommandRejected("storage_failure", "零件和系统编号对不上，请联系维护人员核对资料。", 500)
        return part

    def batch(self, ref):
        if self.scope.mode == "single_instance":
            return self.scope.batch(ref)
        key = self.resolve(ref, "batch")
        row = self.batches.get(key)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "批次和系统编号对不上，请联系维护人员核对资料。", 500)
        return row

    def prepare(self, action, payload, ref=None):
        """Consume the normalized command input; no further input conversion during apply."""
        if action == "create":
            if self.scope.mode == "single_create" and self.facts is None and not self.identities:
                part = self._resolve_single_part(payload["part_ref"])
                part_no = part["part_no"]
                if self.scope.reader.repo.batch_exists(payload["business_code"]):
                    self.used_codes.add(payload["business_code"])
            else:
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
            self.used_codes.discard(code)
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
        """Copies admit the stored source fields like user input; callers wrap this in stored_batch_values."""
        fields = normalize_batch_fields({
            "quantity": source["quantity"] if quantity is None else quantity,
            "due_date": source["due_date"],
            "priority": source["priority"],
            "ready_status": ready_status,
            "ready_date": ready_date,
            "remark": source["remark"],
        })
        return self.create(Batch(batch_id=code, part_no=source["part_no"],
                                 part_name=text(source["part_name"], "part_name"), **fields))


class WorkbenchBatchService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.repo = BatchRepository(conn, logger=logger)

    def preparation(self, scope: BatchFactScope):
        return BatchChangePreparation(scope)

    def import_preparation(
        self,
        scope: BatchFactScope,
        *,
        batch_refs: Sequence[str],
        relation_refs: Sequence[str],
        part_refs: Sequence[str],
        create_codes: Sequence[str],
    ) -> BatchChangePreparation:
        tables = scope.reader.repo.import_apply_tables(
            batch_refs=batch_refs,
            part_refs=part_refs,
            create_codes=create_codes,
        )
        return BatchChangePreparation(scope, tables=tables, relation_refs=relation_refs)

    def apply_prepared_many(self, changes):
        if not self.conn.in_transaction:
            raise RuntimeError("批次命令必须在 WorkbenchCommandService 最外层事务中执行。")
        if not changes:
            return []
        created_codes = []
        for change in changes:
            if change.action == "create":
                self.repo.create(change.created)
                created_codes.append(change.business_code)
            elif change.action == "delete":
                self.repo.delete(change.business_code)
            elif change.fields:
                self.repo.update(change.business_code, change.fields)
        identities = self.identities.active_map("batch", created_codes) if created_codes else {}
        outcomes = []
        for change in changes:
            ref = change.entity_ref
            if change.action == "create":
                identity = identities.get(change.business_code)
                if identity is None:
                    raise RuntimeError("新增批次没有永久引用。")
                ref = identity.ref
            result = "unchanged" if change.action == "update" and not change.fields else "committed"
            outcomes.append(WorkbenchCommandOutcome(result, {"entity_ref": ref, "business_code": change.business_code}))
        return outcomes

    def apply_prepared(self, change):
        return self.apply_prepared_many([change])[0]
