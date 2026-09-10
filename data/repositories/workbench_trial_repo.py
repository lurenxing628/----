"""Trial-only writes. The command service owns the outer transaction/receipt."""

import secrets

from core.infrastructure.workbench_trial_schema import workbench_trial_contract_issues
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.models.workbench_trial_codec import dump, fingerprint, load_object


def new_ref():
    return secrets.token_hex(24)


class WorkbenchTrialRepository:
    def __init__(self, conn):
        self.conn = conn

    def require_schema(self):
        if workbench_trial_contract_issues(self.conn):
            reject("trial_schema_unavailable", "试调持久结构未安装或不完整；请由统一迁移接入，本次不会补表。", 503)

    def get(self, draft_ref):
        self.require_schema()
        row = self.conn.execute("SELECT * FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft_ref,)).fetchone()
        if row is None:
            reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
        head = dict(row)
        head["admission"] = load_object(head.pop("admission_json"), head["admission_hash"])
        head["validation"] = load_object(head.pop("validation_json"))
        count = self.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialRows WHERE draft_ref=?", (draft_ref,)).fetchone()[0]
        if count != head["row_count"] or not 0 < count <= MAX_TRIAL_TASKS:
            reject("trial_snapshot_invalid", "草稿原范围行数不一致，未截断或重建。")
        rows = []
        for raw in self.conn.execute("SELECT * FROM WorkbenchTrialRows WHERE draft_ref=? ORDER BY ordinal", (draft_ref,)):
            item = dict(raw)
            if item["ordinal"] != len(rows):
                reject("trial_snapshot_invalid", "草稿原始行顺序缺失。")
            item["original"] = load_object(item.pop("original_json"), item.pop("original_hash"))
            item["current"] = load_object(item.pop("current_json"))
            if set(item["current"]) != {"machine_ref", "operator_ref", "machine_id", "operator_id", "start", "end"}:
                reject("trial_snapshot_invalid", "草稿安排字段不完整。")
            rows.append(item)
        return head, rows

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
        self.transition(head, "editing", checked, now)

    def transition(self, head, status, checked, now):
        self._transaction()
        cur = self.conn.execute("""UPDATE WorkbenchTrialDrafts SET status=?,revision=revision+1,
            validation_json=?,updated_at=? WHERE draft_ref=? AND revision=? AND status='editing'""",
            (status, dump(checked), now, head["draft_ref"], head["revision"]))
        if cur.rowcount != 1:
            reject("stale_write", "草稿已被其他操作保存或改变，请重新读取。")

    def save(self, head, snapshot, request_key, actor, now):
        self._transaction()
        ref = snapshot["scenario_ref"]
        self.conn.execute("""INSERT INTO WorkbenchTrialScenarios
            (scenario_ref,draft_ref,name,revision,snapshot_json,snapshot_hash,saved_at,local_operator,request_key)
            VALUES (?,?,?,?,?,?,?,?,?)""", (ref, head["draft_ref"], snapshot["name"], head["revision"],
            dump(snapshot), fingerprint(snapshot), now, actor, request_key))
        self.conn.executemany("""INSERT INTO WorkbenchTrialScenarioRows
            (row_ref,task_ref,scenario_ref,source_row_ref,payload_json) VALUES (?,?,?,?,?)""",
            [(row["row_ref"], row["task_ref"], ref, row["source_row_ref"], dump(row)) for row in snapshot["tasks"]])
        self.transition(head, "saved", snapshot["validation"], now)

    def scenario(self, ref):
        self.require_schema()
        row = self.conn.execute("SELECT snapshot_json,snapshot_hash FROM WorkbenchTrialScenarios WHERE scenario_ref=?", (ref,)).fetchone()
        if row is None:
            reject("entity_not_found", "未找到指定试调场景。", 404)
        result = load_object(row[0], row[1])
        tasks = result.get("tasks")
        if type(tasks) is not list or any(type(task) is not dict or type(task.get("row_ref")) is not str for task in tasks):
            reject("trial_snapshot_invalid", "场景任务明细必须为带永久行引用的对象列表。")
        stored = {row[0]: load_object(row[1]) for row in self.conn.execute(
            "SELECT row_ref,payload_json FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?", (ref,))}
        if len(stored) != len(tasks) or stored != {row["row_ref"]: row for row in tasks}:
            reject("trial_snapshot_invalid", "场景快照与永久明细不一致。")
        return result

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
