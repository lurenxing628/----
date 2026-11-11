"""Explicit batch fact scope, isolated per read snapshot or command transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Tuple

from core.models.content import content_text
from core.models.workbench_batch import public_ref
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity

if TYPE_CHECKING:
    from .facts import BatchFacts


class BatchFactScope:
    def __init__(
        self,
        reader: BatchFacts,
        *,
        command: bool = False,
        revisions: Optional[Dict[str, Any]] = None,
        material_day: Optional[str] = None,
        mode: str = "collection",
        target_ref: Optional[str] = None,
        target_refs: Optional[Tuple[str, ...]] = None,
        query_filter: Optional[Mapping[str, Any]] = None,
    ):
        if mode == "batch_closure" and target_refs is None:
            raise ValueError("Mode 'batch_closure' requires target_refs")
        self.reader = reader
        self.command = command
        self.facts: Optional[Dict[str, Any]] = None
        self.revisions = revisions
        self.material_day = material_day if material_day is not None else reader.current_material_day()
        self.mode = mode
        self.target_ref = target_ref
        self.target_refs = target_refs
        self.query_filter = query_filter
        self.stamp: Optional[int] = None
        self.lookups: Dict[str, Dict[Any, Dict[str, Any]]] = {}
        self.resolved_identity: Optional[Tuple[str, str, WorkbenchEntityIdentity]] = None
        self.resolved_batch: Optional[Tuple[str, WorkbenchEntityIdentity, Dict[str, Any]]] = None

    def current_facts(self) -> Optional[Dict[str, Any]]:
        if self.command and self.stamp is not None and (
            not self.reader.conn.in_transaction or self.reader.conn.total_changes != self.stamp
        ):
            # The command wrote, or its transaction ended: the next read must see the database again.
            # Drop the lookups with it, so an index never outlives (or keeps alive) its ledger.
            self.clear()
        return self.facts

    def clear(self) -> None:
        self.facts = None
        self.stamp = None
        self.revisions = None
        self.resolved_identity = None
        self.resolved_batch = None
        self.lookups.clear()

    def row(self, facts: Dict[str, Any], table: str, key: str, value: Any) -> Optional[Dict[str, Any]]:
        """First row with this key, indexed once per snapshot rather than scanned per ref."""
        index = self.lookups.get(table)
        if index is None:
            index = {}
            for item in facts[table]:
                index.setdefault(item[key], item)
            self.lookups[table] = index
        return index.get(value)

    def entity_tables(self) -> Dict[str, Any]:
        if self.target_refs is not None:
            return self.reader.repo.scoped_entity_tables(self.target_refs)
        return self.reader.repo.entity_tables()

    def load(self) -> Dict[str, Any]:
        facts = self.current_facts()
        if facts is None:
            facts = self.reader.load_for_scope(self)
        return facts

    def fingerprint(self) -> str:
        facts = self.current_facts()
        if facts is not None:
            revisions = facts["revisions"]
        elif self.revisions is not None and (
            not self.command
            or (
                self.stamp is not None
                and self.reader.conn.in_transaction
                and self.reader.conn.total_changes == self.stamp
            )
        ):
            revisions = self.revisions
        else:
            revisions = self.reader.read_revisions()
            if self.command and self.reader.conn.in_transaction:
                self.revisions = revisions
                self.stamp = self.reader.conn.total_changes
        return content_text(["batch-facts-v3", revisions, self.material_day])

    def _can_cache_unloaded(self) -> bool:
        if not self.command:
            return True
        if not self.reader.conn.in_transaction:
            return False
        if self.stamp is None:
            self.stamp = self.reader.conn.total_changes
        return True

    def resolve(self, ref: str, kind: str = "batch") -> WorkbenchEntityIdentity:
        public_ref(ref)
        facts = self.current_facts()
        if facts is None:
            if kind == "batch" and self.resolved_batch is not None and self.resolved_batch[0] == ref:
                return self.resolved_batch[1]
            if (
                self.resolved_identity is not None
                and self.resolved_identity[0] == ref
                and self.resolved_identity[1] == kind
            ):
                return self.resolved_identity[2]
            identity = self.reader.identities.get(ref)
        else:
            row = self.row(facts, "WorkbenchEntityRefs", "ref", ref)
            identity = (
                WorkbenchEntityIdentity(
                    row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"])
                )
                if row
                else None
            )
        if identity is None or not identity.active or identity.kind != kind:
            raise WorkbenchCommandRejected("entity_not_found", "这条记录已经不在了，请重新选择。请刷新后重新选择。", 404)
        if facts is None and self._can_cache_unloaded():
            self.resolved_identity = (ref, kind, identity)
        return identity

    def batch(self, ref: str) -> Dict[str, Any]:
        facts = self.current_facts()
        if facts is None and self.resolved_batch is not None and self.resolved_batch[0] == ref:
            return self.resolved_batch[2]
        identity = self.resolve(ref)
        if facts is None:
            row = self.reader.repo.batch_row(identity.entity_key)
        else:
            row = self.row(facts, "Batches", "batch_id", identity.entity_key)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "批次和系统编号对不上，请联系维护人员核对资料。", 500)
        if not identity.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "批次号不能为空，请先核对原记录。")
        if facts is None and self._can_cache_unloaded():
            self.resolved_batch = (ref, identity, row)
        return row
