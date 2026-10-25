"""Bounded SELECT-only receipt and history bodies; no schema or write decisions."""


class TrialAdoptionHistoryRepository:
    def __init__(self, conn):
        self.conn = conn

    def adoption_receipts(self, action, scenario_ref, limit):
        cursor = self.conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE action=? AND context_ref=? "
                                   "ORDER BY committed_at_utc DESC,request_key DESC LIMIT ?", (action, scenario_ref, limit))
        return (dict(row) for row in cursor)

    def receipt_row(self, key):
        row = self.conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE request_key=?", (key,)).fetchone()
        return None if row is None else dict(row)

    def receipt_action(self, request_key):
        row = self.conn.execute("SELECT action,context_ref FROM WorkbenchCommandReceipts WHERE request_key=?", (request_key,)).fetchone()
        return None if row is None else tuple(row)
