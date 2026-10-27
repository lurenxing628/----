"""Run identity across controlled restores; no replay and no database writes."""

import os

from core.infrastructure.connection_guards import main_database_path
from core.models.content import content_text

from .system_journal import SystemMaintenanceJournal


def restored_context_ref(database_scope, records):
    """Only successful restores change the generation; backup/delete/restart do not."""
    restores = sorted(row["job_ref"] for row in records
                      if row["action"] == "restore" and row["state"] == "succeeded" and row["code"] == "verified")
    return content_text({"database_scope": database_scope, "successful_restores": restores})


class RunDataContext:
    def __init__(self, conn, journal_dir=None):
        self.database_path = os.path.realpath(main_database_path(conn))
        self.journal = SystemMaintenanceJournal(journal_dir or self.database_path + ".system-journal", self.database_path)

    def capture(self):
        """Capture validated maintenance facts for one operation."""
        records = self.journal.records()
        self.journal.assert_ready(records)
        return records

    def ref(self, *, records=None):
        records = self.capture() if records is None else records
        return restored_context_ref(self.journal.scope_from_records(records), records)

    def resolve_missing(self, previous_context, *, records):
        """Call only after current run and admission receipt have both been checked; records come from capture().

        ``previous_context`` is the generation the browser saw when it submitted. A later successful
        restore replaced it only when it is the original generation or one restore's recorded
        ``data_context_before``; any other generation cannot be proven and stays unresolved.
        """
        restores = [row for row in records if row["action"] == "restore"
                    and row["state"] == "succeeded" and row["code"] == "verified"]
        if not restores:
            return "unresolved"
        scope = self.journal.scope_from_records(records)
        replaced = {restored_context_ref(scope, [])} | {row["data_context_before"] for row in restores}
        if previous_context != restored_context_ref(scope, restores) and previous_context in replaced:
            return "context_replaced"
        return "unresolved"
