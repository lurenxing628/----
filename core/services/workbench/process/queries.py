"""Snapshot-bound process query entry opening explicit ProcessFactScope instances."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Iterator

from core.infrastructure.transaction import TransactionManager
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .scope import ProcessFactScope


class WorkbenchProcessQueryService:
    def __init__(self, conn, logger=None, *, part_ref=None):
        self.conn = conn
        self.repo = WorkbenchProcessQueryRepository(conn, logger=logger, part_ref=part_ref)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)

    @contextmanager
    def read_snapshot(self) -> Iterator[ProcessFactScope]:
        tx = nullcontext() if self.conn.in_transaction else TransactionManager(self.conn).transaction()
        with tx:
            scope = ProcessFactScope(reader=self)
            scope.state_fingerprint()
            yield scope
