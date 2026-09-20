"""Append-only shipment membership and confirmations on the command connection.

Judgement (missing schema, unknown receipt, member drift, row caps) belongs to
core.services.workbench.outsourcing; this module only returns what is stored.
"""

import json
import secrets

from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_outsourcing_schema import contract_issues
from core.infrastructure.workbench_outsourcing_source_schema import contract_issues as source_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.models.workbench_command import canonical_json


class WorkbenchOutsourcingRepository:
    def __init__(self, conn):
        self.conn = conn

    def schema_issues(self):
        """Receipt, source-confirmation, metadata and plan-identity contract issues; empty when complete."""
        return (contract_issues(self.conn) + source_contract_issues(self.conn) +
                workbench_metadata_contract_issues(self.conn) + workbench_plan_identity_contract_issues(self.conn))

    def header(self, ref):
        """Receipt header with decoded origin/identity and the stored member refs; None when absent.

        result["target"]["operation_refs"] is what the member table holds today;
        result["origin"]["operation_refs"] is what the receipt recorded at registration.
        """
        row = self.conn.execute("SELECT * FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref=?", (ref,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["origin"] = json.loads(result.pop("origin_json"))
        result["identity"] = json.loads(result.pop("identity_json"))
        members = [row[0] for row in self.conn.execute("SELECT operation_ref FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref=? ORDER BY operation_ref", (ref,))]
        result["target"] = {"kind": result["target_kind"], "batch_ref": result["batch_ref"],
                            "supplier_ref": result["supplier_ref"], "operation_refs": members}
        return result

    def latest(self, ref):
        """Highest-sequence confirmation fact of the receipt; None when the receipt has no fact."""
        row = self.conn.execute("SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? ORDER BY sequence DESC LIMIT 1", (ref,)).fetchone()
        return dict(row) if row is not None else None

    def membership(self, refs):
        marks = ",".join("?" for _ in refs)
        return [dict(row) for row in self.conn.execute("SELECT * FROM WorkbenchOutsourcingMembers WHERE operation_ref IN (" + marks + ") ORDER BY operation_ref", refs)]

    def refs(self, batch_ref, limit):
        """Up to limit + 1 receipt refs (optionally within a batch) so the caller can detect the cap."""
        where, params = (" WHERE batch_ref=?", (batch_ref,)) if batch_ref else ("", ())
        rows = self.conn.execute("SELECT outsourcing_ref FROM WorkbenchOutsourcingReceipts" + where +
                                 " ORDER BY outsourcing_ref LIMIT ?", params + (limit + 1,)).fetchall()
        return [row[0] for row in rows]

    def plan_identity_revision(self):
        """计划身份时钟当前修订号（singleton=1 行的 revision）。"""
        return self.conn.execute("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1").fetchone()[0]

    def has_confirm_receipts(self):
        """是否已有任何 outsourcing.confirm 命令回执。"""
        return self.conn.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action='outsourcing.confirm' LIMIT 1").fetchone() is not None

    def history(self, ref, number, size):
        count = self.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=?", (ref,)).fetchone()[0]
        rows = self.conn.execute("SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? ORDER BY sequence DESC LIMIT ? OFFSET ?",
                                 (ref, size, (number - 1) * size)).fetchall()
        return [dict(row) for row in rows], {"number": number, "size": size, "total": count, "pages": (count + size - 1) // size}

    def append(self, prepared, *, request_key, local_operator, now):
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing persistence requires the command transaction")
        previous = prepared["previous"]
        ref = prepared["ref"] or secrets.token_hex(24)
        target, source = prepared["target"], prepared["source"]
        if previous is None:
            self.conn.execute("""INSERT INTO WorkbenchOutsourcingReceipts
                (outsourcing_ref,target_kind,batch_ref,supplier_ref,origin_json,identity_json,created_at) VALUES (?,?,?,?,?,?,?)""",
                (ref, target["kind"], target["batch_ref"], target["supplier_ref"], canonical_json(source["public"]), canonical_json(source["identity"]), now))
            self.conn.executemany("INSERT INTO WorkbenchOutsourcingMembers(operation_ref,outsourcing_ref) VALUES (?,?)",
                                  [(op, ref) for op in target["operation_refs"]])
        fact_ref = secrets.token_hex(24)
        values = prepared["after"]
        self.conn.execute("""INSERT INTO WorkbenchOutsourcingFacts
            (fact_ref,outsourcing_ref,sequence,previous_fact_ref,sent,planned,returned,confirmed_state,
             declared_operator,local_operator,reason,recorded_at,before_json,source_facts_json,request_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fact_ref, ref, previous["sequence"] + 1 if previous else 1, previous["fact_ref"] if previous else None,
             values["sent"], values["planned"], values["returned"], values["confirmedState"],
             prepared["input"]["declared_operator"], local_operator, prepared["input"]["reason"], now,
             canonical_json(prepared["before"]), canonical_json(source["facts"]), request_key))
        if previous is None:
            self.conn.executemany("INSERT INTO WorkbenchOutsourcingSourceConfirmations(operation_ref,batch_ref,fact_ref) VALUES (?,?,?)",
                                  [(op, target["batch_ref"], fact_ref) for op in source["source_confirmations"]])
        return {"outsourcing_ref": ref, "fact_ref": fact_ref}
