"""Trial-only reads/writes. The command service owns the outer transaction, receipt and every ruling."""

import secrets

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_trial_schema import workbench_trial_contract_issues
from core.models.workbench_trial import MAX_TRIAL_TASKS
from core.models.workbench_trial_codec import dump, dump_document, load_object
from core.models.workbench_trial_scenario_archive import EncodedScenario

HISTORY_REFERENCE_FORMAT = "trial-change-history-ref-v1"


def new_ref():
    return secrets.token_hex(24)


class WorkbenchTrialRepository:
    def __init__(self, conn):
        self.conn = conn

    def schema_issues(self):
        """Trial contract issues as reported by the schema probe; [] when the schema is complete."""
        return schema_contract_memo(self.conn).get_schema(workbench_trial_contract_issues)

    def draft_header(self, draft_ref):
        """The whole WorkbenchTrialDrafts row (JSON columns undecoded), or None."""
        row = self.conn.execute("SELECT * FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft_ref,)).fetchone()
        return None if row is None else dict(row)

    def draft_rows(self, draft_ref, *, limit=MAX_TRIAL_TASKS + 1):
        """All WorkbenchTrialRows of one draft in stored ordinal order (JSON columns undecoded)."""
        return [dict(raw) for raw in self.conn.execute(
            "SELECT * FROM WorkbenchTrialRows WHERE draft_ref=? ORDER BY ordinal LIMIT ?", (draft_ref, limit))]

    def create(self, admission, rows, checked, request_key, actor, now):
        self._transaction()
        ref = new_ref()
        key, value = next(iter(admission["input"]["base"].items()))
        admission_json, admission_hash = dump_document(admission)
        self.conn.execute("""INSERT INTO WorkbenchTrialDrafts
            (draft_ref,base_kind,base_ref,admission_json,admission_hash,row_count,revision,status,
             validation_json,created_at,updated_at,local_operator,request_key)
            VALUES (?,?,?,?,?,?,1,'editing',?,?,?,?,?)""",
            (ref, key, value, admission_json, admission_hash, len(rows), dump(checked), now, now, actor, request_key))
        stored_rows = []
        for index, row in enumerate(rows):
            original_json, original_hash = dump_document(row["original"])
            stored_rows.append((row["row_ref"], row["task_ref"], ref, row["operation_ref"], row["source_task_ref"],
                                row["source_row_ref"], index, original_json, original_hash, dump(row["current"])))
        self.conn.executemany("""INSERT INTO WorkbenchTrialRows
            (row_ref,task_ref,draft_ref,operation_ref,source_task_ref,source_row_ref,ordinal,
             original_json,original_hash,current_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            stored_rows)
        head = {"draft_ref": ref, "base_kind": key, "base_ref": value, "admission": admission,
                "admission_hash": admission_hash, "row_count": len(rows), "revision": 1, "status": "editing",
                "validation": checked, "created_at": now, "updated_at": now, "local_operator": actor,
                "request_key": request_key}
        return head, [dict(row, draft_ref=ref, ordinal=index) for index, row in enumerate(rows)]

    def change(self, head, row, before, checked, request_key, actor, now):
        """Record one arrangement change; True when the draft head advanced, False when it was stale."""
        self._transaction()
        current_json, checked_json = dump(row["current"]), dump(checked)
        cur = self.conn.execute("UPDATE WorkbenchTrialRows SET current_json=? WHERE row_ref=? AND draft_ref=?",
                               (current_json, row["row_ref"], head["draft_ref"]))
        if cur.rowcount != 1:
            raise RuntimeError("Trial row was not updated exactly once")
        self.conn.execute("""INSERT INTO WorkbenchTrialChanges
            (change_ref,draft_ref,task_ref,revision,before_json,after_json,validation_json,
             recorded_at,local_operator,request_key) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (new_ref(), head["draft_ref"], row["task_ref"], head["revision"] + 1, dump(before),
             current_json, checked_json, now, actor, request_key))
        return self._transition(head, "editing", checked_json, now)

    def transition(self, head, status, checked, now):
        """True when exactly the editing head at this revision advanced; False when another write got there first."""
        self._transaction()
        return self._transition(head, status, dump(checked), now)

    def _transition(self, head, status, checked_json, now):
        cur = self.conn.execute("""UPDATE WorkbenchTrialDrafts SET status=?,revision=revision+1,
            validation_json=?,updated_at=? WHERE draft_ref=? AND revision=? AND status='editing'""",
            (status, checked_json, now, head["draft_ref"], head["revision"]))
        return cur.rowcount == 1

    def save(self, head, snapshot, encoded: EncodedScenario, request_key, actor, now):
        """Persist ordered metadata and permanent task bodies under the full document size limit."""
        self._transaction()
        ref = snapshot["scenario_ref"]
        self.conn.execute("""INSERT INTO WorkbenchTrialScenarios
            (scenario_ref,draft_ref,name,revision,snapshot_json,snapshot_hash,saved_at,local_operator,request_key)
            VALUES (?,?,?,?,?,?,?,?,?)""", (ref, head["draft_ref"], snapshot["name"], head["revision"],
            encoded.header, None, now, actor, request_key))
        self.conn.executemany("""INSERT INTO WorkbenchTrialScenarioRows
            (row_ref,task_ref,scenario_ref,source_row_ref,payload_json) VALUES (?,?,?,?,?)""",
            [(row["row_ref"], row["task_ref"], ref, row["source_row_ref"], text)
             for row, text in zip(snapshot["tasks"], encoded.tasks)])
        return self.transition(head, "saved", snapshot["validation"], now)

    def scenario_header(self, ref):
        """The whole WorkbenchTrialScenarios row of one scenario, or None."""
        row = self.conn.execute("SELECT * FROM WorkbenchTrialScenarios WHERE scenario_ref=?", (ref,)).fetchone()
        return None if row is None else dict(row)

    def iter_scenario_rows(self, ref):
        cursor = self.conn.execute("SELECT row_ref,payload_json FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?", (ref,))
        return (dict(row) for row in cursor)

    def changes(self, draft_ref, *, through_revision=None):
        if through_revision is None:
            cursor = self.conn.execute("""SELECT change_ref,task_ref,before_json,after_json,validation_json,
                recorded_at,local_operator FROM WorkbenchTrialChanges WHERE draft_ref=? ORDER BY revision""", (draft_ref,))
        else:
            cursor = self.conn.execute("""SELECT change_ref,task_ref,before_json,after_json,validation_json,
                recorded_at,local_operator FROM WorkbenchTrialChanges
                WHERE draft_ref=? AND revision<=? ORDER BY revision""", (draft_ref, through_revision))
        result, validations = [], {}
        for row in cursor:
            if row[4] not in validations:
                validations[row[4]] = load_object(row[4])
            result.append({"change_ref": row[0], "task_ref": row[1], "before": load_object(row[2]), "after": load_object(row[3]),
                           "validation": validations[row[4]], "recorded_at": row[5], "local_operator": row[6]})
        return result

    def public_history(self, draft_ref, *, through_revision=None):
        """Original historical evidence, with the established public arrangement fields."""
        result = self.changes(draft_ref, through_revision=through_revision)
        for item in result:
            for side in ("before", "after"):
                item[side] = {key: item[side][key] for key in ("machine_ref", "operator_ref", "start", "end")}
        return result

    def history_reference(self, draft_ref):
        """Bind a command to the immutable change ledger at its committed revision."""
        revision = self.conn.execute("SELECT revision FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft_ref,)).fetchone()[0]
        return {"format": HISTORY_REFERENCE_FORMAT, "draft_ref": draft_ref, "through_revision": revision}

    def _transaction(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Trial writes require the caller's transaction")
