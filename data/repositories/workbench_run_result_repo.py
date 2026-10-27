"""Persist full candidate sets independently from formal Schedule."""

from core.shared.strict_json import canonical_json


def encode_candidate_rows(candidates):
    """Encode each final artifact and task payload once for the owning INSERT."""
    return [{"candidate_ref": row["candidate_ref"], "key": row["key"], "sequence": row["sequence"],
             "status": row["status"], "task_count": len(row["tasks"]),
             "artifact_json": canonical_json(row["artifact"]),
             "tasks": [{"row_ref": task["row_ref"], "operation_ref": task["operation_ref"],
                        "payload_json": canonical_json(task["payload"])} for task in row["tasks"]]}
            for row in candidates]


class WorkbenchRunResultRepository:
    def __init__(self, conn):
        self.conn = conn

    def save(self, run_ref, candidates):
        for row in candidates:
            self.conn.execute(
                "INSERT INTO WorkbenchRunCandidates(candidate_ref,run_ref,candidate_key,sequence,status,task_count,artifact_json) VALUES (?,?,?,?,?,?,?)",
                (row["candidate_ref"], run_ref, row["key"], row["sequence"], row["status"], row["task_count"], row["artifact_json"]))
            self.conn.executemany(
                "INSERT INTO WorkbenchRunCandidateTasks(row_ref,candidate_ref,operation_ref,ordinal,payload_json) VALUES (?,?,?,?,?)",
                [(task["row_ref"], row["candidate_ref"], task["operation_ref"], ordinal, task["payload_json"])
                 for ordinal, task in enumerate(row["tasks"])])

    def consistent(self, run_ref, result):
        succeeded = result["state"] in ("complete", "partial")
        if result["result_persisted"] is not succeeded or bool(result["candidates"]) is not succeeded:
            return False
        rows = list(self.conn.execute("""SELECT c.candidate_ref,c.task_count,c.status,COUNT(t.row_ref) AS actual
            FROM WorkbenchRunCandidates c LEFT JOIN WorkbenchRunCandidateTasks t ON t.candidate_ref=c.candidate_ref
            WHERE c.run_ref=? GROUP BY c.candidate_ref""", (run_ref,)))
        if len(rows) != len(result["candidates"]):
            return False
        expected = {row["candidate_ref"]: row for row in result["candidates"]}
        return all(row[0] in expected and row[1] == row[3] == expected[row[0]]["task_count"]
                   and row[2] == expected[row[0]]["status"] for row in rows)
