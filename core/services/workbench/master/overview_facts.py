"""SELECT-only raw collections for master data overview."""

from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.template_source import TemplateSourceFacts
from core.services.workbench.facts.source_revisions import (
    MASTER_OVERVIEW_SOURCE_KEYS,
    read_source_revisions,
)
from data.repositories.workbench_master_query_repo import WorkbenchMasterQueryRepository


def plain(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, bytes):
        return {"storage_type": "blob", "hex": value.hex()}
    if isinstance(value, float) and not math.isfinite(value):
        return {"storage_type": "float", "value": str(value)}
    return value


@dataclass
class MasterOverviewFactScope:
    conn: Any
    repo: WorkbenchMasterQueryRepository
    as_of: str
    material_day: str
    snapshot_state: Dict[str, Any]
    tables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    gaps: List[Dict[str, str]] = field(default_factory=list)
    identities: Dict[Tuple[str, str], Dict[str, Any]] = field(default_factory=dict)
    _indexes: Dict[Tuple[str, str], Dict[Any, Dict[str, Any]]] = field(default_factory=dict)
    _groups: Dict[Tuple[str, str], Dict[Any, List[Dict[str, Any]]]] = field(default_factory=dict)
    template_source_facts: Optional[TemplateSourceFacts] = None

    def rows(self, table: str) -> List[Dict[str, Any]]:
        return self.tables[table]

    def index(self, table: str, key: str) -> Dict[Any, Dict[str, Any]]:
        cache_key = (table, key)
        if cache_key not in self._indexes:
            self._indexes[cache_key] = {row[key]: row for row in self.rows(table)}
        return self._indexes[cache_key]

    def grouped(self, table: str, key: str) -> Dict[Any, List[Dict[str, Any]]]:
        cache_key = (table, key)
        if cache_key not in self._groups:
            groups: Dict[Any, List[Dict[str, Any]]] = {}
            for row in self.rows(table):
                groups.setdefault(row[key], []).append(row)
            self._groups[cache_key] = groups
        return self._groups[cache_key]

    def ref(self, kind: str, key: Any) -> str:
        row = self.identities.get((kind, str(plain(key))))
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "基础资料缺少有效的系统编号，请联系维护人员核对资料。", 500)
        return row["ref"]

    def _load(self) -> None:
        self.tables = self.repo.overview_tables()
        self.identities = {
            (row["kind"], row["entity_key"]): row
            for row in self.rows("WorkbenchEntityRefs")
            if row["active"] == 1
        }
        self.template_source_facts = TemplateSourceFacts(
            self.rows("PartOperations"),
            self.rows("ExternalGroups"),
            self.rows("Suppliers"),
            self.rows("WorkbenchSupplierOpTypes"),
            self.rows("WorkbenchSupplierProfiles"),
        )


class MasterOverviewFacts:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchMasterQueryRepository(conn)

    @contextmanager
    def read_snapshot(self, *, as_of: datetime, bind_snapshot=None) -> Iterator[MasterOverviewFactScope]:
        """``as_of`` is the request's read time; the material day is its factory-local date."""
        with TransactionManager(self.conn).transaction():
            as_of_text = as_of.isoformat(timespec="seconds")
            material_day = as_of.date().isoformat()
            revisions = read_source_revisions(self.conn, MASTER_OVERVIEW_SOURCE_KEYS)
            snapshot_state = {
                "revisions": revisions,
                "material_day": material_day,
            }
            if bind_snapshot is not None:
                bind_snapshot(snapshot_state, as_of_text)
            scope = MasterOverviewFactScope(
                conn=self.conn,
                repo=self.repo,
                as_of=as_of_text,
                material_day=material_day,
                snapshot_state=snapshot_state,
            )
            scope._load()
            yield scope
