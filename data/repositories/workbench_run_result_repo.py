"""Persist full candidate sets independently from formal Schedule."""

from core.shared.strict_json import canonical_json

from .schedule_repo import STORED_INSTANT_COLUMNS, stored_instants

_TASK_INSERT_SQL = (
    "INSERT INTO WorkbenchRunCandidateTasks("
    "row_ref,candidate_ref,operation_ref,ordinal,op_id,source,machine_id,operator_id,"
    "start_time,end_time,start_us,end_us,is_point_event,locked"
    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


def _encode_task_row(task, ordinal: int):
    return {
        "row_ref": task["row_ref"],
        "operation_ref": task["operation_ref"],
        "ordinal": ordinal,
        "op_id": task["op_id"],
        "source": task["source"],
        "machine_id": task["machine_id"],
        "operator_id": task["operator_id"],
        **dict(zip(STORED_INSTANT_COLUMNS, stored_instants(task["start_time"], task["end_time"]))),
        "locked": int(task["locked"]),
    }


def encode_candidate_rows(candidates):
    """Encode each final artifact and structured task row once for the owning INSERT."""
    return [
        {
            "candidate_ref": row["candidate_ref"],
            "key": row["key"],
            "sequence": row["sequence"],
            "task_count": len(row["tasks"]),
            "artifact_json": canonical_json(row["artifact"]),
            "tasks": [_encode_task_row(task, ordinal) for ordinal, task in enumerate(row["tasks"])],
        }
        for row in candidates
    ]


class WorkbenchRunResultRepository:
    def __init__(self, conn):
        self.conn = conn

    def save(self, run_ref, candidates):
        for row in candidates:
            self.conn.execute(
                "INSERT INTO WorkbenchRunCandidates("
                "candidate_ref,run_ref,candidate_key,sequence,task_count,artifact_json"
                ") VALUES (?,?,?,?,?,?)",
                (
                    row["candidate_ref"],
                    run_ref,
                    row["key"],
                    row["sequence"],
                    row["task_count"],
                    row["artifact_json"],
                ),
            )
            self.conn.executemany(
                _TASK_INSERT_SQL,
                [
                    (
                        task["row_ref"],
                        row["candidate_ref"],
                        task["operation_ref"],
                        task["ordinal"],
                        task["op_id"],
                        task["source"],
                        task["machine_id"],
                        task["operator_id"],
                        task["start_time"],
                        task["end_time"],
                        task["start_us"],
                        task["end_us"],
                        task["is_point_event"],
                        task["locked"],
                    )
                    for task in row["tasks"]
                ],
            )
