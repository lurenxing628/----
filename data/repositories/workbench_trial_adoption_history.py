"""Bounded SELECT-only receipt discovery. No schema, repair or process cache."""

from core.models.workbench_trial import reject

MAX_SCAN_ROWS = 100000
MAX_RECEIPTS = 1000
MAX_DIRECTORY_BYTES = 8 * 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_SCENARIO_BYTES = 32 * 1024 * 1024


class TrialAdoptionHistoryRepository:
    def __init__(self, conn):
        self.conn = conn

    def receipts(self, scenario_ref):
        # There is no action/context index in the frozen schema. Bound the
        # header scan as well as matching bodies, instead of hiding a full scan.
        selected, byte_count = [], 0
        sql = "SELECT request_key,action,context_ref FROM WorkbenchCommandReceipts ORDER BY request_key LIMIT ?"
        for index, row in enumerate(self.conn.execute(sql, (MAX_SCAN_ROWS + 1,))):
            if index >= MAX_SCAN_ROWS:
                reject("query_too_large", "命令目录超过100000条读取上限，未返回截断采用历史。", 413)
            if (row["action"], row["context_ref"]) != ("trial.scenario.adopt", scenario_ref):
                continue
            if len(selected) >= MAX_RECEIPTS:
                reject("query_too_large", "本场景采用回执超过1000条读取上限，未截断。", 413)
            item = self.receipt(row["request_key"], MAX_RECEIPT_BYTES)
            byte_count += len(item["outcome_json"].encode("utf-8"))
            if byte_count > MAX_DIRECTORY_BYTES:
                reject("query_too_large", "采用回执目录超过8 MiB读取上限，未截断。", 413)
            selected.append(item)
        return sorted(selected, key=lambda r: (r["committed_at_utc"], r["request_key"]), reverse=True)

    def receipt(self, key, limit=MAX_SCENARIO_BYTES):
        row = self.conn.execute("SELECT length(CAST(outcome_json AS BLOB)) FROM WorkbenchCommandReceipts WHERE request_key=?", (key,)).fetchone()
        if row is None:
            reject("adoption_history_invalid", "原命令回执缺失，不能证明保存来源。")
        self.bound(row[0], limit)
        row = dict(self.conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE request_key=?", (key,)).fetchone())
        if type(row["outcome_json"]) is not str:
            reject("adoption_history_invalid", "采用回执不是有效结构化文本，未转换原值。")
        return row

    @staticmethod
    def bound(size, limit):
        if type(size) is not int or size < 0:
            reject("adoption_history_invalid", "历史证据字段缺失或类型无效。")
        if size > limit:
            reject("query_too_large", "历史证据超过本批读取大小上限，未截断或转换原值。", 413)

    def history(self, version):
        heads = self.conn.execute("SELECT id,length(CAST(result_summary AS BLOB)) AS bytes FROM ScheduleHistory WHERE version=? ORDER BY id LIMIT 2", (version,)).fetchall()
        if len(heads) != 1:
            return None
        self.bound(heads[0]["bytes"], MAX_RECEIPT_BYTES)
        return dict(self.conn.execute("SELECT id,version,result_status,result_summary,created_by FROM ScheduleHistory WHERE id=?", (heads[0]["id"],)).fetchone())

    def scenario_headers(self, scenario_ref):
        row = self.conn.execute("SELECT scenario_ref,draft_ref,name,revision,snapshot_hash,saved_at,local_operator,request_key,length(CAST(snapshot_json AS BLOB)) AS bytes FROM WorkbenchTrialScenarios WHERE scenario_ref=?", (scenario_ref,)).fetchone()
        if row is None:
            reject("entity_not_found", "未找到指定试调场景，未改查最新场景。", 404)
        header = dict(row)
        self.bound(header.pop("bytes"), MAX_SCENARIO_BYTES)
        draft = self.conn.execute("SELECT draft_ref,base_kind,base_ref,revision,status,admission_hash,request_key,length(CAST(admission_json AS BLOB)) AS bytes FROM WorkbenchTrialDrafts WHERE draft_ref=?", (header["draft_ref"],)).fetchone()
        if draft is None:
            reject("adoption_history_invalid", "场景的原永久草稿缺失。")
        draft = dict(draft)
        self.bound(draft.pop("bytes"), MAX_SCENARIO_BYTES)
        return header, draft
