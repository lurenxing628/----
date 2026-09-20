"""Bounded SELECT-only receipt discovery facts. No schema, repair, process cache or ruling."""


class TrialAdoptionHistoryRepository:
    def __init__(self, conn):
        self.conn = conn

    def receipt_headers(self, limit):
        """(request_key, action, context_ref) of the first `limit` command receipts by request_key.

        There is no action/context index in the frozen schema; the caller bounds the header scan
        by asking for one row past its cap instead of hiding a full scan."""
        return [dict(row) for row in self.conn.execute(
            "SELECT request_key,action,context_ref FROM WorkbenchCommandReceipts ORDER BY request_key LIMIT ?", (limit,))]

    def receipt_size(self, key):
        """{"bytes": outcome_json byte length} of one command receipt, or None when the receipt is missing."""
        row = self.conn.execute("SELECT length(CAST(outcome_json AS BLOB)) AS bytes FROM WorkbenchCommandReceipts WHERE request_key=?",
                                (key,)).fetchone()
        return None if row is None else dict(row)

    def receipt_row(self, key):
        """The whole WorkbenchCommandReceipts row of one receipt, or None."""
        row = self.conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE request_key=?", (key,)).fetchone()
        return None if row is None else dict(row)

    def history_heads(self, version):
        """(id, bytes of result_summary) of up to two ScheduleHistory rows at one version, id ascending."""
        return [dict(row) for row in self.conn.execute(
            "SELECT id,length(CAST(result_summary AS BLOB)) AS bytes FROM ScheduleHistory WHERE version=? ORDER BY id LIMIT 2",
            (version,)).fetchall()]

    def history_row(self, history_id):
        """(id, version, result_status, result_summary, created_by) of one ScheduleHistory row, or None."""
        row = self.conn.execute("SELECT id,version,result_status,result_summary,created_by FROM ScheduleHistory WHERE id=?",
                                (history_id,)).fetchone()
        return None if row is None else dict(row)

    def scenario_row_sizes(self, scenario_ref):
        """payload_json byte sizes of a scenario's permanent rows, at most 10001 values (one past the 10000 cap)."""
        return [row[0] for row in self.conn.execute(
            "SELECT length(CAST(payload_json AS BLOB)) FROM WorkbenchTrialScenarioRows WHERE scenario_ref=? LIMIT 10001",
            (scenario_ref,)).fetchall()]

    def draft_admission(self, draft_ref):
        """{"admission_json": ...} of one draft, or None."""
        row = self.conn.execute("SELECT admission_json FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft_ref,)).fetchone()
        return None if row is None else dict(row)

    def receipt_action(self, request_key):
        """(action, context_ref) of one command receipt, or None."""
        row = self.conn.execute("SELECT action,context_ref FROM WorkbenchCommandReceipts WHERE request_key=?", (request_key,)).fetchone()
        return None if row is None else tuple(row)

    def sized_scenario_header(self, scenario_ref):
        """Scenario header columns plus "bytes" (snapshot_json size), snapshot itself unread; None when missing."""
        row = self.conn.execute("SELECT scenario_ref,draft_ref,name,revision,snapshot_hash,saved_at,local_operator,request_key,"
                                "length(CAST(snapshot_json AS BLOB)) AS bytes FROM WorkbenchTrialScenarios WHERE scenario_ref=?",
                                (scenario_ref,)).fetchone()
        return None if row is None else dict(row)

    def sized_draft_header(self, draft_ref):
        """Draft header columns plus "bytes" (admission_json size), admission itself unread; None when missing."""
        row = self.conn.execute("SELECT draft_ref,base_kind,base_ref,revision,status,admission_hash,request_key,"
                                "length(CAST(admission_json AS BLOB)) AS bytes FROM WorkbenchTrialDrafts WHERE draft_ref=?",
                                (draft_ref,)).fetchone()
        return None if row is None else dict(row)
