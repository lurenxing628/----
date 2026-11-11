"""Shared resource query snapshots and bounded write-command primitives."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Iterator

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity, is_entity_ref
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_resource_query_repo import WorkbenchResourceQueryRepository
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository

from .catalogs import WorkbenchResourceCatalogService
from .entities import WorkbenchResourceService
from .metrics import WorkbenchResourceMetricsService
from .scope import ResourceFactScope
from .states import ResourceChangePreparation
from .suppliers import WorkbenchSupplierService
from .table_facts import capture_change_facts


class WorkbenchResourceQueryService:
    def __init__(self, conn, kind, logger=None):
        self.conn, self.kind = conn, kind
        self.repo = WorkbenchResourceQueryRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.logger = logger
        if kind == "supplier":
            self.domain = WorkbenchSupplierService(conn, logger=logger)
        elif kind in ("machine_group", "shift_profile"):
            self.domain = WorkbenchResourceCatalogService(conn, kind, logger=logger)
        else:
            self.domain = WorkbenchResourceService(conn, kind, logger=logger)

    @contextmanager
    def read_snapshot(self, *, capture_fingerprint: bool = True) -> Iterator[ResourceFactScope]:
        tx = nullcontext() if self.conn.in_transaction else TransactionManager(self.conn).transaction()
        with tx:
            scope = ResourceFactScope(
                reader=self,
                metrics=WorkbenchResourceMetricsService(self.conn, self.logger),
                capture_fingerprint=bool(capture_fingerprint),
            )
            if scope.capture_fingerprint:
                scope.state_fingerprint()
            yield scope

    def create_relations_snapshot(self):
        return self.repo.create_relations(self.kind)

    def preparation(
        self,
        *,
        refs=(),
        codes=None,
        selected_refs=(),
        selected_codes=None,
        names=None,
        machine_authorizations: bool = False,
        known_identities=(),
    ) -> ResourceChangePreparation:
        repo = WorkbenchResourceTableRepository(self.conn, self.logger)
        facts = capture_change_facts(
            self.conn,
            self.logger,
            refs=refs,
            codes=codes,
            selected_refs=selected_refs,
            selected_codes=selected_codes,
            machine_authorizations=machine_authorizations,
            known_identities=known_identities,
        )
        owners = {kind: repo.name_owners(kind, values) for kind, values in (names or {}).items()}
        return ResourceChangePreparation(facts, name_reader=repo.name_owners, names=owners)

    def preparation_for(self, action, payload, *, ref=None) -> ResourceChangePreparation:
        selected = [
            item
            for value in payload.get("relationships", {}).values()
            for item in (value if isinstance(value, list) else [value])
            if item is not None
        ]
        names = (
            {self.kind: [payload["label"]]}
            if self.kind in ("op_type", "machine_group", "shift_profile") and "label" in payload
            else None
        )
        return self.preparation(
            refs=[] if ref is None else [ref],
            codes={self.kind: [payload["business_code"]]} if action == "create" else {},
            selected_refs=selected,
            names=names,
        )

    def resolve_refs(self, refs):
        """refs 已由 resource_refs 准入；这里只核对每个身份仍在且属于本类资源。"""
        if not refs:
            return []
        by_ref = {
            row["ref"]: row
            for row in WorkbenchResourceTableRepository(self.conn, self.logger).identities_by_refs(refs)
        }
        result = []
        for ref in refs:
            row = by_ref.get(ref)
            if row is None or row["kind"] != self.kind:
                raise WorkbenchCommandRejected("entity_not_found", "这条资源已经删除了。请从列表重新选择。", 404)
            result.append(
                WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], row["revision"], True)
            )
        return result

    def resolve(self, ref) -> WorkbenchEntityIdentity:
        if not is_entity_ref(ref):
            raise WorkbenchCommandRejected(
                "entity_not_found", "这条资源记录已失效，页面没有打开。请从列表重新选择。", 404
            )
        return self.resolve_refs([ref])[0]

    def current_with_identity(self, identity):
        known = {
            "ref": identity.ref,
            "kind": identity.kind,
            "entity_key": identity.entity_key,
            "revision": identity.revision,
            "active": int(identity.active),
        }
        preparation = self.preparation(refs=[identity.ref], known_identities=[known])
        current = preparation.current(self.kind, identity)
        return preparation.state(self.kind, current.entity_key)
