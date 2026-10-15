"""Dashboard identities and append-only handling evidence, not production facts; no rulings here."""

import uuid

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_dashboard_schema import contract_issues
from core.models.content import content_text
from core.models.workbench_command import canonical_json
from core.models.workbench_dashboard import MAX_BYTES, bounded
from data.repositories.workbench_dashboard_source_repo import rows


class WorkbenchDashboardRepository:
    items_table = "WorkbenchDashboardItems"
    states_table = "WorkbenchDashboardStates"
    history_table = "WorkbenchDashboardHistory"

    def __init__(self, conn):
        self.conn = conn

    def schema_installed(self):
        return not schema_contract_memo(self.conn).get_schema(contract_issues)

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

    def stored_rows(self, limit):
        """Stream identity, raw state bodies and this revision's tail/receipt in one read."""
        cursor = self.conn.execute("SELECT i.*,s.revision AS _state_revision,s.handling_json AS _state_handling_json,"
                    "s.origin_json AS _state_origin_json,s.updated_at AS _state_updated_at,h.after_json AS _tail_after_json,"
                    "c.receipt_ref AS _receipt_ref,length(CAST(s.handling_json AS BLOB))+"
                    "length(CAST(s.origin_json AS BLOB)) AS _stored_body_bytes "
                    "FROM " + self.states_table + " s JOIN " + self.items_table + " i ON i.item_ref=s.item_ref "
                    "LEFT JOIN " + self.history_table + " h ON h.item_ref=s.item_ref AND h.sequence=s.revision "
                    "LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=h.request_key "
                    "ORDER BY i.item_ref LIMIT ?", (limit + 1,))
        names = [column[0] for column in cursor.description]
        identity_columns = names[:names.index("_state_revision")]
        for raw in cursor:
            selected = dict(zip(names, raw))
            identity = {name: selected[name] for name in identity_columns}
            yield {**identity, "revision": selected["_state_revision"],
                   "handling_json": selected["_state_handling_json"], "origin_json": selected["_state_origin_json"],
                   "updated_at": selected["_state_updated_at"], "_identity": identity,
                   "_tail_after_json": selected["_tail_after_json"], "_receipt_ref": selected["_receipt_ref"],
                   "_stored_body_bytes": selected["_stored_body_bytes"]}

    def identity(self, item_ref):
        result = rows(self.conn, "SELECT * FROM " + self.items_table + " WHERE item_ref=?", (item_ref,))
        return result[0] if result else None

    def has_item(self, item_ref):
        return self.conn.execute("SELECT 1 FROM " + self.items_table + " WHERE item_ref=?", (item_ref,)).fetchone() is not None

    def history_count(self, item_ref):
        return self.conn.execute("SELECT COUNT(*) FROM " + self.history_table + " WHERE item_ref=?", (item_ref,)).fetchone()[0]

    def history_rows(self, item_ref, size, offset):
        return rows(self.conn, "SELECT h.*,c.receipt_ref,c.action AS receipt_action,c.context_ref AS receipt_context_ref,"
                    "c.outcome_json AS receipt_outcome_json FROM " + self.history_table + " h "
                    "LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=h.request_key "
                    "WHERE h.item_ref=? ORDER BY h.sequence DESC LIMIT ? OFFSET ?", (item_ref, size, offset))

    def append(self, *, item, before, after, facts, actor, action, reason, request_key, now):
        if not self.conn.in_transaction:
            raise RuntimeError("Dashboard persistence requires the command transaction")
        ref, stamp = item["item_ref"], now.isoformat(timespec="seconds")
        row = self.conn.execute("SELECT revision FROM " + self.states_table + " WHERE item_ref=?", (ref,)).fetchone()
        sequence = row[0] + 1 if row else 1
        source = {key: item[key] for key in ("item_ref", "category", "subject", "source", "risk", "navigation")}
        before_text, after_text = canonical_json(before), canonical_json(after)
        source_text, facts_text = canonical_json(source), content_text(facts)
        # These exact fields are stored below. Count their logical document once.
        document_size = sum(len(value.encode("utf-8")) for value in (before_text, after_text, source_text, facts_text))
        bounded(range(document_size + len('{"after":,"before":,"facts":,"source":}')), MAX_BYTES)
        if row:
            self.conn.execute("UPDATE " + self.states_table + " SET revision=?,handling_json=?,updated_at=? WHERE item_ref=?",
                              (sequence, after_text, stamp, ref))
        else:
            self.conn.execute("INSERT INTO " + self.states_table + " VALUES (?,?,?,?,?)",
                              (ref, sequence, after_text, source_text, stamp))
        history_ref = uuid.uuid4().hex + uuid.uuid4().hex[:16]
        self.conn.execute("INSERT INTO " + self.history_table + " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (history_ref, ref, sequence, action, before_text, after_text, source_text,
                           facts_text, None, reason, actor, stamp, request_key))
        return history_ref
