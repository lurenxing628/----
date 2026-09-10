"""Dashboard identities and append-only handling evidence, not production facts."""

import json
import uuid

from core.infrastructure.workbench_dashboard_schema import contract_issues
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_dashboard import (
    HANDLING_FIELDS,
    MAX_BYTES,
    MAX_ROWS,
    STATUSES,
    bounded,
    payload_size,
    reference,
)
from data.repositories.workbench_dashboard_source_repo import rows


def corrupt():
    raise WorkbenchCommandRejected("dashboard_storage_invalid", "处置台账或来源身份不完整，请核对存储；本次未自动修补。", 409)


def load_handling(raw):
    try:
        value = json.loads(raw)
        if (type(value) is not dict or set(value) != {"status"} | set(HANDLING_FIELDS)
                or value["status"] not in STATUSES
                or any(value[key] is not None and type(value[key]) is not str for key in HANDLING_FIELDS)):
            corrupt()
        return value
    except (TypeError, ValueError):
        corrupt()


class WorkbenchDashboardRepository:
    items_table = "WorkbenchDashboardItems"
    states_table = "WorkbenchDashboardStates"
    history_table = "WorkbenchDashboardHistory"

    def __init__(self, conn, *, external_repo=None):
        self.conn = conn
        self.external_repo = external_repo

    def require_schema(self):
        if contract_issues(self.conn):
            raise WorkbenchCommandRejected("dashboard_unavailable", "值班台台账未安装或结构不完整，需由主线完成明确迁移；本次没有补表。", 503)

    def mappings(self, category, refs):
        column = "batch_ref" if category in ("delivery", "material") else "task_ref"
        result = {}
        refs = list(dict.fromkeys(refs))
        for start in range(0, len(refs), 300):
            chunk = refs[start:start + 300]
            selected = rows(self.conn, "SELECT * FROM WorkbenchDashboardItems WHERE category=? AND " + column + " IN (" +
                            ",".join("?" for _ in chunk) + ")", [category] + chunk)
            result.update((row[column], row) for row in selected)
        if set(result) != set(refs):
            corrupt()
        return result

    def stored(self):
        size = self.conn.execute("SELECT COALESCE(SUM(length(CAST(handling_json AS BLOB))+length(CAST(origin_json AS BLOB))),0) "
                                 "FROM " + self.states_table).fetchone()[0]
        bounded(range(size), MAX_BYTES)
        result = bounded(rows(self.conn, "SELECT i.*,s.revision,s.handling_json,s.origin_json,s.updated_at "
                              "FROM " + self.states_table + " s JOIN " + self.items_table + " i ON i.item_ref=s.item_ref "
                              "ORDER BY i.item_ref LIMIT ?", (MAX_ROWS + 1,)))
        for row in result:
            row["handling"] = load_handling(row.pop("handling_json"))
            row["origin"] = json.loads(row.pop("origin_json"))
        self._validate_states(result)
        return {row["item_ref"]: row for row in result}

    def _validate_states(self, stored):
        tails = rows(self.conn, "SELECT s.item_ref,h.after_json,c.receipt_ref,"
                     "(SELECT COUNT(*) FROM " + self.history_table + " a WHERE a.item_ref=s.item_ref) AS count "
                     "FROM " + self.states_table + " s LEFT JOIN " + self.history_table + " h ON h.item_ref=s.item_ref AND h.sequence=s.revision "
                     "LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=h.request_key")
        by_ref = {row["item_ref"]: row for row in tails}
        for row in stored:
            tail = by_ref.get(row["item_ref"])
            if (tail is None or tail["receipt_ref"] is None or tail["count"] != row["revision"] or load_handling(tail["after_json"]) != row["handling"]
                    or row["origin"].get("item_ref") != row["item_ref"] or row["origin"].get("category") != row["category"]):
                corrupt()

    def identity(self, item_ref):
        result = rows(self.conn, "SELECT * FROM " + self.items_table + " WHERE item_ref=?", (reference(item_ref),))
        if not result:
            raise WorkbenchCommandRejected("entity_not_found", "条目不存在，未改指其他来源。", 404)
        return result[0]

    def history(self, item_ref, number, size):
        if self.external_repo and not self.conn.execute("SELECT 1 FROM " + self.items_table + " WHERE item_ref=?", (item_ref,)).fetchone():
            self.external_repo.require_schema()
            self.external_repo.identity(item_ref)
            return self.external_repo.history(item_ref, number, size)
        total = self.conn.execute("SELECT COUNT(*) FROM " + self.history_table + " WHERE item_ref=?", (item_ref,)).fetchone()[0]
        pages = max(1, (total + size - 1) // size)
        if number > pages:
            raise WorkbenchCommandRejected("invalid_input", "历史页码超过范围。", 400)
        selected = rows(self.conn, "SELECT h.*,c.receipt_ref FROM " + self.history_table + " h "
                        "LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=h.request_key "
                        "WHERE h.item_ref=? ORDER BY h.sequence DESC LIMIT ? OFFSET ?", (item_ref, size, (number - 1) * size))
        public = []
        for row in selected:
            if row["receipt_ref"] is None or input_fingerprint(json.loads(row["source_facts_json"])) != row["source_hash"]:
                corrupt()
            public.append({"history_ref": row["history_ref"], "sequence": row["sequence"], "action": row["action"],
                           "before": load_handling(row["before_json"]), "after": load_handling(row["after_json"]),
                           "reason": row["reason"], "local_operator": row["local_operator"], "recorded_at": row["recorded_at"],
                           "receipt_ref": row["receipt_ref"], "source_snapshot": {
                               "snapshot_ref": row["history_ref"], "as_of": row["recorded_at"],
                               "time_basis": "factory_local", "source": json.loads(row["source_json"])}})
        return {"items": public, "page": {"number": number, "size": size, "total": total, "pages": pages,
                                           "sort": [{"field": "sequence", "direction": "desc"}]}}

    def append(self, *, item, before, after, facts, actor, action, reason, request_key, now):
        if self.external_repo and item["category"] == "external":
            self.external_repo.require_schema()
            return self.external_repo.append(item=item, before=before, after=after, facts=facts, actor=actor,
                                             action=action, reason=reason, request_key=request_key, now=now)
        if not self.conn.in_transaction:
            raise RuntimeError("Dashboard persistence requires the command transaction")
        ref, stamp = item["item_ref"], now.isoformat(timespec="seconds")
        row = self.conn.execute("SELECT revision FROM " + self.states_table + " WHERE item_ref=?", (ref,)).fetchone()
        sequence = row[0] + 1 if row else 1
        source = {key: item[key] for key in ("item_ref", "category", "subject", "source", "risk", "navigation")}
        payload_size({"source": source, "facts": facts, "before": before, "after": after})
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
