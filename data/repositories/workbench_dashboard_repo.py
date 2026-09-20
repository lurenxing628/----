"""Dashboard identities and append-only handling evidence, not production facts; no rulings here."""

import uuid

from core.infrastructure.workbench_dashboard_schema import contract_issues
from core.models.workbench_command import canonical_json, input_fingerprint
from data.repositories.workbench_dashboard_source_repo import rows


class WorkbenchDashboardRepository:
    items_table = "WorkbenchDashboardItems"
    states_table = "WorkbenchDashboardStates"
    history_table = "WorkbenchDashboardHistory"

    def __init__(self, conn):
        self.conn = conn

    def schema_installed(self):
        return not contract_issues(self.conn)

    def mappings(self, category, refs):
        """{anchor ref: item row} for the category; the service decides whether every ref is mapped."""
        column = "batch_ref" if category in ("delivery", "material") else "task_ref"
        result = {}
        refs = list(dict.fromkeys(refs))
        for start in range(0, len(refs), 300):
            chunk = refs[start:start + 300]
            selected = rows(self.conn, "SELECT * FROM WorkbenchDashboardItems WHERE category=? AND " + column + " IN (" +
                            ",".join("?" for _ in chunk) + ")", [category] + chunk)
            result.update((row[column], row) for row in selected)
        return result

    def stored_bytes(self):
        return self.conn.execute("SELECT COALESCE(SUM(length(CAST(handling_json AS BLOB))+length(CAST(origin_json AS BLOB))),0) "
                                 "FROM " + self.states_table).fetchone()[0]

    def stored_rows(self, limit):
        """Raw current states joined with their identities (handling_json/origin_json undecoded); reads limit+1 rows."""
        return rows(self.conn, "SELECT i.*,s.revision,s.handling_json,s.origin_json,s.updated_at "
                    "FROM " + self.states_table + " s JOIN " + self.items_table + " i ON i.item_ref=s.item_ref "
                    "ORDER BY i.item_ref LIMIT ?", (limit + 1,))

    def state_tails(self):
        """Per stored state: the history row at its revision, its receipt ref and the history count."""
        return rows(self.conn, "SELECT s.item_ref,h.after_json,c.receipt_ref,"
                    "(SELECT COUNT(*) FROM " + self.history_table + " a WHERE a.item_ref=s.item_ref) AS count "
                    "FROM " + self.states_table + " s LEFT JOIN " + self.history_table + " h ON h.item_ref=s.item_ref AND h.sequence=s.revision "
                    "LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=h.request_key")

    def identity(self, item_ref):
        result = rows(self.conn, "SELECT * FROM " + self.items_table + " WHERE item_ref=?", (item_ref,))
        return result[0] if result else None

    def has_item(self, item_ref):
        return self.conn.execute("SELECT 1 FROM " + self.items_table + " WHERE item_ref=?", (item_ref,)).fetchone() is not None

    def history_count(self, item_ref):
        return self.conn.execute("SELECT COUNT(*) FROM " + self.history_table + " WHERE item_ref=?", (item_ref,)).fetchone()[0]

    def history_rows(self, item_ref, size, offset):
        return rows(self.conn, "SELECT h.*,c.receipt_ref FROM " + self.history_table + " h "
                    "LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=h.request_key "
                    "WHERE h.item_ref=? ORDER BY h.sequence DESC LIMIT ? OFFSET ?", (item_ref, size, offset))

    def append(self, *, item, before, after, facts, actor, action, reason, request_key, now):
        if not self.conn.in_transaction:
            raise RuntimeError("Dashboard persistence requires the command transaction")
        ref, stamp = item["item_ref"], now.isoformat(timespec="seconds")
        row = self.conn.execute("SELECT revision FROM " + self.states_table + " WHERE item_ref=?", (ref,)).fetchone()
        sequence = row[0] + 1 if row else 1
        source = {key: item[key] for key in ("item_ref", "category", "subject", "source", "risk", "navigation")}
        if row:
            self.conn.execute("UPDATE " + self.states_table + " SET revision=?,handling_json=?,updated_at=? WHERE item_ref=?",
                              (sequence, canonical_json(after), stamp, ref))
        else:
            self.conn.execute("INSERT INTO " + self.states_table + " VALUES (?,?,?,?,?)",
                              (ref, sequence, canonical_json(after), canonical_json(source), stamp))
        history_ref = uuid.uuid4().hex + uuid.uuid4().hex[:16]
        self.conn.execute("INSERT INTO " + self.history_table + " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (history_ref, ref, sequence, action, canonical_json(before), canonical_json(after), canonical_json(source),
                           canonical_json(facts), input_fingerprint(facts), reason, actor, stamp, request_key))
        return history_ref
