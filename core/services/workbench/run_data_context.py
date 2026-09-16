"""Run identity across controlled restores; no replay and no database writes."""

import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional, Set

from core.models.workbench_command import input_fingerprint
from core.services.workbench.system_journal import SystemMaintenanceJournal, file_fingerprint
from core.services.workbench.system_reads import backup_signature


def restored_context_ref(database_scope, records):
    """Only successful restores change the generation; backup/delete/restart do not."""
    restores = sorted(row["job_ref"] for row in records
                      if row["action"] == "restore" and row["state"] == "succeeded" and row["code"] == "verified")
    return input_fingerprint({"database_scope": database_scope, "successful_restores": restores})


class RunDataContext:
    def __init__(self, conn, journal_dir=None, backup_dir=None):
        path = next(row[2] for row in conn.execute("PRAGMA database_list") if row[1] == "main")
        self.database_path = os.path.realpath(path)
        self.journal = SystemMaintenanceJournal(journal_dir or self.database_path + ".system-journal", self.database_path)
        self.backup_dir = backup_dir

    def _records(self):
        self.journal.assert_ready()
        return self.journal.records()

    def ref(self):
        return restored_context_ref(self.journal.database_scope, self._records())

    def resolve_missing(self, request_key, previous_context=None):
        """Call only after current run and admission receipt have both been checked."""
        records = self._records()
        restores = [row for row in records if row["action"] == "restore"
                    and row["state"] == "succeeded" and row["code"] == "verified"]
        if not restores:
            return "unresolved"
        current = restored_context_ref(self.journal.database_scope, restores)
        if previous_context is not None:
            # Older browser records carry no data_context_before; None stays a member so
            # membership tests keep the same answer as before.
            known: Set[Optional[str]] = {restored_context_ref(self.journal.database_scope, [])}
            for row in restores:
                known.add(row.get("data_context_before"))
                known.add(restored_context_ref(self.journal.database_scope,
                                              [old for old in restores if old["job_ref"] != row["job_ref"]]))
            return "context_replaced" if previous_context != current and previous_context in known else "unresolved"
        # Version 1 browser records had no generation. The most recent registered
        # protection copy can prove membership, without guessing from current IDs.
        latest = max(restores, key=lambda row: (row["updated_at"], row["job_ref"]))
        return "context_replaced" if self._protected_request(latest, request_key) else "unresolved"

    def _protected_request(self, row, request_key):
        protection = row.get("protection")
        if not self.backup_dir or not isinstance(protection, dict):
            return False
        name, digest = protection.get("filename"), protection.get("sha256")
        if (not isinstance(name, str) or os.path.basename(name) != name or "\\" in name
                or not name.startswith("aps_backup_") or not name.endswith(".db")
                or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            return False
        path = os.path.join(self.backup_dir, name)
        try:
            before = backup_signature(path)
            if file_fingerprint(path) != digest:
                return False
            # The file is journal-authorized and read-only. Never open a user path
            # or migrate a backup while answering a status lookup.
            with closing(sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
                found = conn.execute("""SELECT 1 FROM WorkbenchRunJobs j
                    JOIN WorkbenchCommandReceipts r ON r.request_key=j.request_key
                    WHERE j.request_key=? AND r.action='scheduling.run' LIMIT 1""", (request_key,)).fetchone()
            return bool(found) and backup_signature(path) == before and file_fingerprint(path) == digest
        except (OSError, sqlite3.Error):
            # Missing/changed historical evidence does not prove non-execution.
            return False
