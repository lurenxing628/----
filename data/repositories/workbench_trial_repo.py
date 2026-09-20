"""Trial-only reads/writes. The command service owns the outer transaction, receipt and every ruling."""

import secrets

from core.infrastructure.workbench_trial_schema import workbench_trial_contract_issues
from core.models.workbench_trial_codec import dump, fingerprint, load_object


def new_ref():
    return secrets.token_hex(24)


class WorkbenchTrialRepository:
    def __init__(self, conn):
        self.conn = conn

    def schema_issues(self):
        """Trial contract issues as reported by the schema probe; [] when the schema is complete."""
        return workbench_trial_contract_issues(self.conn)

    def draft_header(self, draft_ref):
        """The whole WorkbenchTrialDrafts row (JSON columns undecoded), or None."""
        row = self.conn.execute("SELECT * FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft_ref,)).fetchone()
        return None if row is None else dict(row)

    def draft_row_count(self, draft_ref):
        return self.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialRows WHERE draft_ref=?", (draft_ref,)).fetchone()[0]

    def draft_rows(self, draft_ref):
        """All WorkbenchTrialRows of one draft in stored ordinal order (JSON columns undecoded)."""
        return [dict(raw) for raw in self.conn.execute(
            "SELECT * FROM WorkbenchTrialRows WHERE draft_ref=? ORDER BY ordinal", (draft_ref,))]

    def create(self, admission, rows, checked, request_key, actor, now):
        self._transaction()
        ref = new_ref()
        key, value = next(iter(admission["input"]["base"].items()))
        self.conn.execute("""INSERT INTO WorkbenchTrialDrafts
            (draft_ref,base_kind,base_ref,admission_json,admission_hash,row_count,revision,status,
             validation_json,created_at,updated_at,local_operator,request_key)
            VALUES (?,?,?,?,?,?,1,'editing',?,?,?,?,?)""",
            (ref, key, value, dump(admission), fingerprint(admission), len(rows), dump(checked), now, now, actor, request_key))
        self.conn.executemany("""INSERT INTO WorkbenchTrialRows
            (row_ref,task_ref,draft_ref,operation_ref,source_task_ref,source_row_ref,ordinal,
             original_json,original_hash,current_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [(row["row_ref"], row["task_ref"], ref, row["operation_ref"], row["source_task_ref"],
              row["source_row_ref"], index, dump(row["original"]), fingerprint(row["original"]), dump(row["current"]))
             for index, row in enumerate(rows)])
        return ref

    def change(self, head, row, before, checked, request_key, actor, now):
        """Record one arrangement change; True when the draft head advanced, False when it was stale."""
        self._transaction()
        cur = self.conn.execute("UPDATE WorkbenchTrialRows SET current_json=? WHERE row_ref=? AND draft_ref=?",
                               (dump(row["current"]), row["row_ref"], head["draft_ref"]))
        if cur.rowcount != 1:
            raise RuntimeError("Trial row was not updated exactly once")
        self.conn.execute("""INSERT INTO WorkbenchTrialChanges
            (change_ref,draft_ref,task_ref,revision,before_json,after_json,validation_json,
             recorded_at,local_operator,request_key) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (new_ref(), head["draft_ref"], row["task_ref"], head["revision"] + 1, dump(before),
             dump(row["current"]), dump(checked), now, actor, request_key))
        return self.transition(head, "editing", checked, now)

    def transition(self, head, status, checked, now):
        """True when exactly the editing head at this revision advanced; False when another write got there first."""
        self._transaction()
        cur = self.conn.execute("""UPDATE WorkbenchTrialDrafts SET status=?,revision=revision+1,
            validation_json=?,updated_at=? WHERE draft_ref=? AND revision=? AND status='editing'""",
            (status, dump(checked), now, head["draft_ref"], head["revision"]))
        return cur.rowcount == 1

    def save(self, head, snapshot, request_key, actor, now):
        """Persist a scenario snapshot plus permanent rows; True when the draft head advanced to saved."""
        self._transaction()
        ref = snapshot["scenario_ref"]
        self.conn.execute("""INSERT INTO WorkbenchTrialScenarios
            (scenario_ref,draft_ref,name,revision,snapshot_json,snapshot_hash,saved_at,local_operator,request_key)
            VALUES (?,?,?,?,?,?,?,?,?)""", (ref, head["draft_ref"], snapshot["name"], head["revision"],
            dump(snapshot), fingerprint(snapshot), now, actor, request_key))
        self.conn.executemany("""INSERT INTO WorkbenchTrialScenarioRows
            (row_ref,task_ref,scenario_ref,source_row_ref,payload_json) VALUES (?,?,?,?,?)""",
            [(row["row_ref"], row["task_ref"], ref, row["source_row_ref"], dump(row)) for row in snapshot["tasks"]])
        return self.transition(head, "saved", snapshot["validation"], now)

    def scenario_header(self, ref):
        """The whole WorkbenchTrialScenarios row of one scenario, or None."""
        row = self.conn.execute("SELECT * FROM WorkbenchTrialScenarios WHERE scenario_ref=?", (ref,)).fetchone()
        return None if row is None else dict(row)

    def scenario_rows(self, ref):
        """(row_ref, payload_json) of every permanent scenario row, payload undecoded."""
        return [dict(row) for row in self.conn.execute(
            "SELECT row_ref,payload_json FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?", (ref,))]

    def changes(self, draft_ref):
        result = []
        for row in self.conn.execute("""SELECT change_ref,task_ref,before_json,after_json,validation_json,
            recorded_at,local_operator FROM WorkbenchTrialChanges WHERE draft_ref=? ORDER BY revision""", (draft_ref,)):
            result.append({"change_ref": row[0], "task_ref": row[1], "before": load_object(row[2]), "after": load_object(row[3]),
                           "validation": load_object(row[4]), "recorded_at": row[5], "local_operator": row[6]})
        return result

    def _transaction(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Trial writes require the caller's transaction")
