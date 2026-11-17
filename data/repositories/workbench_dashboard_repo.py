"""Dashboard identities and append-only handling evidence, not production facts; no rulings here."""

import json

from core.models.workbench_dashboard import MAX_BYTES, bounded
from core.shared.refs import new_ref
from core.shared.strict_json import canonical_json
from data.repositories.workbench_dashboard_source_repo import rows

_ANCHOR_COLUMNS = {
    "delivery": "batch_ref",
    "material": "batch_ref",
    "actual": "task_ref",
    "downtime": "task_ref",
    "external": "outsourcing_ref",
}


class WorkbenchDashboardRepository:
    def __init__(self, conn):
        self.conn = conn

    def mappings(self, category, refs):
        """{anchor ref: item row} for the category; the service decides whether every ref is mapped."""
        column = _ANCHOR_COLUMNS[category]
        if not refs:
            return {}
        cat_sql = "+category=?" if category == "external" else "category=?"
        selected = rows(
            self.conn,
            f"SELECT * FROM WorkbenchDashboardItems WHERE {cat_sql} AND {column} IN (SELECT value FROM json_each(?))",
            (category, json.dumps(list(refs))),
        )
        return {row[column]: row for row in selected}

    def external_items(self, limit):
        """All external item identities ordered by item_ref; reads limit+1 rows."""
        return rows(
            self.conn,
            "SELECT * FROM WorkbenchDashboardItems WHERE category='external' ORDER BY item_ref LIMIT ?",
            (limit + 1,),
        )

    def stored_rows(self, limit):
        """Stream identity and raw state bodies in one read."""
        cursor = self.conn.execute(
            "SELECT i.*,s.revision AS _state_revision,s.handling_json AS _state_handling_json,"
            "s.origin_json AS _state_origin_json,s.updated_at AS _state_updated_at "
            "FROM WorkbenchDashboardStates s JOIN WorkbenchDashboardItems i ON i.item_ref=s.item_ref "
            "ORDER BY i.item_ref LIMIT ?",
            (limit + 1,),
        )
        names = [column[0] for column in cursor.description]
        identity_columns = names[:names.index("_state_revision")]
        for raw in cursor:
            selected = dict(zip(names, raw))
            identity = {name: selected[name] for name in identity_columns}
            yield {
                **identity,
                "revision": selected["_state_revision"],
                "handling_json": selected["_state_handling_json"],
                "origin_json": selected["_state_origin_json"],
                "updated_at": selected["_state_updated_at"],
                "_identity": identity,
            }

    def has_item(self, item_ref):
        return (
            self.conn.execute(
                "SELECT 1 FROM WorkbenchDashboardItems WHERE item_ref=?",
                (item_ref,),
            ).fetchone()
            is not None
        )

    def item_by_ref(self, item_ref):
        selected = rows(
            self.conn,
            "SELECT * FROM WorkbenchDashboardItems WHERE item_ref=?",
            (item_ref,),
            limit=1,
        )
        return selected[0] if selected else None

    def stored_by_ref(self, item_ref):
        selected = rows(
            self.conn,
            "SELECT * FROM WorkbenchDashboardStates WHERE item_ref=?",
            (item_ref,),
            limit=1,
        )
        return selected[0] if selected else None

    def history_count(self, item_ref):
        return self.conn.execute(
            "SELECT COUNT(*) FROM WorkbenchDashboardHistory WHERE item_ref=?",
            (item_ref,),
        ).fetchone()[0]

    def history_rows(self, item_ref, size, offset):
        return rows(
            self.conn,
            "SELECT h.history_ref,h.sequence,h.action,h.before_json,h.after_json,h.source_json,h.reason,"
            "h.local_operator,h.recorded_at,c.receipt_ref FROM WorkbenchDashboardHistory h "
            "JOIN WorkbenchCommandReceipts c ON c.request_key=h.request_key "
            "WHERE h.item_ref=? ORDER BY h.sequence DESC LIMIT ? OFFSET ?",
            (item_ref, size, offset),
        )

    def append(self, *, item, before, after, actor, action, reason, request_key, now):
        if not self.conn.in_transaction:
            raise RuntimeError("Dashboard persistence requires the command transaction")
        ref, stamp = item["item_ref"], now.isoformat(timespec="seconds")
        # 命令 guard 已在同一写事务里核对过这个版本；0 表示还没有处置记录。
        revision = item["_guard"]["revision"]
        sequence = revision + 1
        source = {key: item[key] for key in ("item_ref", "category", "subject", "source", "risk", "navigation")}
        before_text, after_text = canonical_json(before), canonical_json(after)
        source_text = canonical_json(source)
        # These exact fields are stored below. Count their logical document once.
        document_size = sum(len(value.encode("utf-8")) for value in (before_text, after_text, source_text))
        bounded(range(document_size + len('{"after":,"before":,"source":}')), MAX_BYTES)
        if revision:
            self.conn.execute(
                "UPDATE WorkbenchDashboardStates SET revision=?,handling_json=?,updated_at=? WHERE item_ref=?",
                (sequence, after_text, stamp, ref),
            )
        else:
            self.conn.execute(
                "INSERT INTO WorkbenchDashboardStates(item_ref,revision,handling_json,origin_json,updated_at) VALUES (?,?,?,?,?)",
                (ref, sequence, after_text, source_text, stamp),
            )
        history_ref = new_ref()
        self.conn.execute(
            "INSERT INTO WorkbenchDashboardHistory(history_ref,item_ref,sequence,action,before_json,after_json,source_json,reason,local_operator,recorded_at,request_key) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (history_ref, ref, sequence, action, before_text, after_text, source_text, reason, actor, stamp, request_key),
        )
        return history_ref
