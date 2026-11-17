"""Shipment membership, inline receipt status and append-only confirmation history.

Judgement (missing schema, unknown receipt, member drift, row caps) belongs to
core.services.workbench.outsourcing.service; this module only returns what is stored.
"""

import json
from typing import Any, Dict, List, Optional, TypedDict

from core.models.content import read_stored_json
from core.models.workbench_outsourcing import document_text, page_meta
from core.shared.refs import new_ref


class RawReceiptFacts(TypedDict):
    header: Optional[Dict[str, Any]]
    latest: Optional[Dict[str, Any]]


class WorkbenchOutsourcingRepository:
    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def _header(row, members: List[str]) -> Dict[str, Any]:
        origin = read_stored_json(row["origin_json"], dict)
        identity = read_stored_json(row["identity_json"], dict)
        return {
            "outsourcing_ref": row["outsourcing_ref"],
            "target_kind": row["target_kind"],
            "batch_ref": row["batch_ref"],
            "supplier_ref": row["supplier_ref"],
            "created_at": row["created_at"],
            "origin": origin,
            "identity": identity,
            "target": {
                "kind": row["target_kind"],
                "batch_ref": row["batch_ref"],
                "supplier_ref": row["supplier_ref"],
                "operation_refs": members,
            },
        }

    @staticmethod
    def _latest(row) -> Dict[str, Any]:
        return {
            "fact_ref": row["latest_fact_ref"],
            "outsourcing_ref": row["outsourcing_ref"],
            "sequence": row["history_count"],
            "sent": row["sent"],
            "planned": row["planned"],
            "returned": row["returned"],
            "confirmed_state": row["confirmed_state"],
            "declared_operator": row["declared_operator"],
            "local_operator": row["local_operator"],
            "reason": row["reason"],
            "recorded_at": row["recorded_at"],
        }

    def _members(self, refs: List[str]) -> Dict[str, List[str]]:
        members: Dict[str, List[str]] = {ref: [] for ref in refs}
        for row in self.conn.execute(
            "SELECT outsourcing_ref, operation_ref FROM WorkbenchOutsourcingMembers "
            "WHERE outsourcing_ref IN (SELECT value FROM json_each(?)) ORDER BY operation_ref",
            (json.dumps(refs),),
        ):
            members[row["outsourcing_ref"]].append(row["operation_ref"])
        return members

    def receipt_facts(self, refs) -> Dict[str, RawReceiptFacts]:
        """Read headers, sorted members and inline latest status for these receipt refs once."""
        captured: Dict[str, RawReceiptFacts] = {
            ref: {"header": None, "latest": None} for ref in refs
        }
        rows = {
            row["outsourcing_ref"]: row
            for row in self.conn.execute(
                "SELECT * FROM WorkbenchOutsourcingReceipts "
                "WHERE outsourcing_ref IN (SELECT value FROM json_each(?))",
                (json.dumps(list(captured)),),
            )
        }
        if not rows:
            return captured
        members = self._members(list(rows))
        for ref, row in rows.items():
            captured[ref] = {
                "header": self._header(row, members[ref]),
                "latest": self._latest(row),
            }
        return captured

    def all_receipt_facts(self, limit: int):
        """Read up to limit + 1 receipt rows; return (count_or_overflow, decoded_map)."""
        rows = self.conn.execute(
            "SELECT * FROM WorkbenchOutsourcingReceipts ORDER BY outsourcing_ref LIMIT ?",
            (limit + 1,),
        ).fetchall()
        if len(rows) > limit or not rows:
            return len(rows), {}
        members = self._members([row["outsourcing_ref"] for row in rows])
        return len(rows), {
            row["outsourcing_ref"]: {
                "header": self._header(row, members[row["outsourcing_ref"]]),
                "latest": self._latest(row),
            }
            for row in rows
        }

    def receipt_page(
        self,
        *,
        batch_ref: Optional[str],
        status: str,
        as_of_text: str,
        number: int,
        size: int,
    ):
        """Filter and slice WorkbenchOutsourcingReceipts via B-Tree indexes before reading members."""
        clauses: List[str] = []
        params: List[Any] = []
        if batch_ref is not None:
            clauses.append("batch_ref=?")
            params.append(batch_ref)
        if status == "awaiting":
            clauses.append("returned IS NULL")
        elif status == "overdue":
            clauses.append("returned IS NULL AND planned<?")
            params.append(as_of_text)
        elif status == "returned":
            clauses.append("returned IS NOT NULL")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        total = self.conn.execute(
            "SELECT COUNT(*) FROM WorkbenchOutsourcingReceipts" + where,
            params,
        ).fetchone()[0]
        offset = (number - 1) * size
        if total == 0 or offset >= total:
            return [], total
        rows = self.conn.execute(
            "SELECT * FROM WorkbenchOutsourcingReceipts"
            + where
            + " ORDER BY outsourcing_ref LIMIT ? OFFSET ?",
            [*params, size, offset],
        ).fetchall()
        members = self._members([row["outsourcing_ref"] for row in rows])
        items = [
            (
                self._header(row, members[row["outsourcing_ref"]]),
                self._latest(row),
            )
            for row in rows
        ]
        return items, total

    def history(self, ref, number: int, size: int):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=?",
            (ref,),
        ).fetchone()[0]
        rows = self.conn.execute(
            "SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? "
            "ORDER BY sequence DESC LIMIT ? OFFSET ?",
            (ref, size, (number - 1) * size),
        ).fetchall()
        return [dict(row) for row in rows], page_meta(number, size, count)

    def append(self, prepared, *, request_key, local_operator, now):
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing persistence requires the command transaction")
        previous = prepared["previous"]
        ref = prepared["ref"] or new_ref()
        fact_ref = new_ref()
        target, source = prepared["target"], prepared["source"]
        values = prepared["after"]
        declared_operator = prepared["input"]["declared_operator"]
        reason = prepared["input"]["reason"]
        sequence = previous["sequence"] + 1 if previous else 1
        before_text = document_text(prepared["before"])
        if previous is None:
            origin_text = document_text(source["public"])
            identity_text = document_text(source["identity"])
            self.conn.execute(
                """INSERT INTO WorkbenchOutsourcingReceipts(
                    outsourcing_ref,target_kind,batch_ref,supplier_ref,
                    origin_json,identity_json,created_at,
                    latest_fact_ref,history_count,sent,planned,returned,
                    confirmed_state,declared_operator,local_operator,reason,recorded_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    ref,
                    target["kind"],
                    target["batch_ref"],
                    target["supplier_ref"],
                    origin_text,
                    identity_text,
                    now,
                    fact_ref,
                    1,
                    values["sent"],
                    values["planned"],
                    values["returned"],
                    values["confirmedState"],
                    declared_operator,
                    local_operator,
                    reason,
                    now,
                ),
            )
            self.conn.executemany(
                "INSERT INTO WorkbenchOutsourcingMembers(operation_ref,outsourcing_ref) VALUES (?,?)",
                [(op, ref) for op in target["operation_refs"]],
            )
        else:
            self.conn.execute(
                """UPDATE WorkbenchOutsourcingReceipts SET
                    latest_fact_ref=?,history_count=?,sent=?,planned=?,returned=?,
                    confirmed_state=?,declared_operator=?,local_operator=?,reason=?,recorded_at=?
                WHERE outsourcing_ref=?""",
                (
                    fact_ref,
                    sequence,
                    values["sent"],
                    values["planned"],
                    values["returned"],
                    values["confirmedState"],
                    declared_operator,
                    local_operator,
                    reason,
                    now,
                    ref,
                ),
            )
        self.conn.execute(
            """INSERT INTO WorkbenchOutsourcingFacts(
                fact_ref,outsourcing_ref,sequence,previous_fact_ref,
                sent,planned,returned,confirmed_state,
                declared_operator,local_operator,reason,recorded_at,
                before_json,request_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fact_ref,
                ref,
                sequence,
                previous["fact_ref"] if previous else None,
                values["sent"],
                values["planned"],
                values["returned"],
                values["confirmedState"],
                declared_operator,
                local_operator,
                reason,
                now,
                before_text,
                request_key,
            ),
        )
        return {"outsourcing_ref": ref, "fact_ref": fact_ref}
