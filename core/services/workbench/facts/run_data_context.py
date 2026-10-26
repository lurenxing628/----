"""Run identity across controlled restores; no replay and no database writes."""

import os
import sqlite3
from typing import Optional, Set

from core.infrastructure.connection_guards import main_database_path
from core.infrastructure.snapshot_connection import open_readonly_immutable
from core.models.content import content_text, same
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .system_journal import SystemMaintenanceJournal
from .system_reads import backup_signature


def restored_context_ref(database_scope, records):
    """Only successful restores change the generation; backup/delete/restart do not."""
    restores = sorted(row["job_ref"] for row in records
                      if row["action"] == "restore" and row["state"] == "succeeded" and row["code"] == "verified")
    return content_text({"database_scope": database_scope, "successful_restores": restores})


class RunDataContext:
    def __init__(self, conn, journal_dir=None, backup_dir=None):
        self.database_path = os.path.realpath(main_database_path(conn))
        self.journal = SystemMaintenanceJournal(journal_dir or self.database_path + ".system-journal", self.database_path)
        self.backup_dir = backup_dir

    def capture(self):
        """Capture validated maintenance facts for one operation."""
        records = self.journal.records()
        self.journal.assert_ready(records)
        return records

    def ref(self, *, records=None):
        records = self.capture() if records is None else records
        return restored_context_ref(self.journal.scope_from_records(records), records)

    def resolve_missing(self, request_key, previous_context=None, *, records):
        """Call only after current run and admission receipt have both been checked; records come from capture()."""
        restores = [row for row in records if row["action"] == "restore"
                    and row["state"] == "succeeded" and row["code"] == "verified"]
        if not restores:
            return "unresolved"
        scope = self.journal.scope_from_records(records)
        current = restored_context_ref(scope, restores)
        if previous_context is not None:
            # Older browser records carry no data_context_before; None stays a member so
            # membership tests keep the same answer as before.
            known: Set[Optional[str]] = {restored_context_ref(scope, [])}
            for row in restores:
                known.add(row.get("data_context_before"))
                known.add(restored_context_ref(scope,
                                              [old for old in restores if old["job_ref"] != row["job_ref"]]))
            if previous_context != current and previous_context in known:
                return "context_replaced"
            # Hash-only browser generations have no reconstructible original content;
            # the retained protection's actual admission receipt can still answer membership.
            latest = max(restores, key=lambda row: (row["updated_at"], row["job_ref"]))
            return "context_replaced" if previous_context != current and self._protected_request(latest, request_key) else "unresolved"
        # Version 1 browser records had no generation. The most recent registered
        # protection copy can prove membership, without guessing from current IDs.
        latest = max(restores, key=lambda row: (row["updated_at"], row["job_ref"]))
        return "context_replaced" if self._protected_request(latest, request_key) else "unresolved"

    def _protected_request(self, row, request_key):
        protection = row.get("protection")
        if not self.backup_dir or not isinstance(protection, dict):
            return False
        name = protection.get("filename")
        if (not isinstance(name, str) or os.path.basename(name) != name or "\\" in name
                or not name.startswith("aps_backup_") or not name.endswith(".db")):
            return False
        path = os.path.join(self.backup_dir, name)
        try:
            before = backup_signature(path)
            if row.get("version") == 2 and not same(protection.get("signature"), before):
                return False
            # The file is journal-authorized and read-only. Never open a user path
            # or migrate a backup while answering a status lookup.
            with open_readonly_immutable(path) as conn:
                found = WorkbenchRunRepository(conn).scheduling_run_admitted(request_key)
            return bool(found)
        except (OSError, sqlite3.Error):
            # Missing/changed historical evidence does not prove non-execution.
            return False
