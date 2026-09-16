"""Append-only shipment membership and confirmations on the command connection."""

import json
import secrets

from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_outsourcing_schema import contract_issues
from core.infrastructure.workbench_outsourcing_source_schema import contract_issues as source_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.models.workbench_command import canonical_json
from core.models.workbench_outsourcing import MAX_ROWS, bounded, reject


class WorkbenchOutsourcingRepository:
    def __init__(self, conn):
        self.conn = conn

    def require_schema(self):
        issues = (contract_issues(self.conn) + source_contract_issues(self.conn) +
                  workbench_metadata_contract_issues(self.conn) + workbench_plan_identity_contract_issues(self.conn))
        if issues:
            reject("真实外协登记结构尚未完整接入；未补表或改动原资料。", "outsourcing_unavailable", 503)

    def header(self, ref):
        row = self.conn.execute("SELECT * FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref=?", (ref,)).fetchone()
        if row is None:
            reject("外协原登记不存在，未改读其他对象。", "entity_not_found", 404)
        result = dict(row)
        result["origin"] = json.loads(result.pop("origin_json"))
        result["identity"] = json.loads(result.pop("identity_json"))
        members = [row[0] for row in self.conn.execute("SELECT operation_ref FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref=? ORDER BY operation_ref", (ref,))]
        result["target"] = {"kind": result["target_kind"], "batch_ref": result["batch_ref"],
                            "supplier_ref": result["supplier_ref"], "operation_refs": members}
        if members != result["origin"]["operation_refs"]:
            reject("外协成员映射与原登记不一致，未忽略缺失成员。", "outsourcing_unavailable", 503)
        return bounded(result)

    def latest(self, ref):
        row = self.conn.execute("SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? ORDER BY sequence DESC LIMIT 1", (ref,)).fetchone()
        if row is None:
            reject("外协登记缺少确认事实，请恢复完整记录。", "outsourcing_unavailable", 503)
        return bounded(dict(row))

    def membership(self, refs):
        marks = ",".join("?" for _ in refs)
        return [dict(row) for row in self.conn.execute("SELECT * FROM WorkbenchOutsourcingMembers WHERE operation_ref IN (" + marks + ") ORDER BY operation_ref", refs)]

    def refs(self, batch_ref=None):
        where, params = (" WHERE batch_ref=?", (batch_ref,)) if batch_ref else ("", ())
        rows = self.conn.execute("SELECT outsourcing_ref FROM WorkbenchOutsourcingReceipts" + where +
                                 " ORDER BY outsourcing_ref LIMIT ?", params + (MAX_ROWS + 1,)).fetchall()
        if len(rows) > MAX_ROWS:
            reject("外协登记超过10000项，请限定批次。", "query_too_large", 413)
        return [row[0] for row in rows]

    def history(self, ref, number, size):
        count = self.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=?", (ref,)).fetchone()[0]
        rows = self.conn.execute("SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? ORDER BY sequence DESC LIMIT ? OFFSET ?",
                                 (ref, size, (number - 1) * size)).fetchall()
        return bounded([dict(row) for row in rows]), {"number": number, "size": size, "total": count, "pages": (count + size - 1) // size}

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
