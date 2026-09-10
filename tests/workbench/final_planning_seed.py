"""D acceptance inputs and passive official-table witnesses, all private."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from tests.workbench.piece_main_seed import seed as piece_seed
from tests.workbench.test_run_jobs_support import JobCase


def seed(app, **options):
    result = piece_seed(app, **options)
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        case = JobCase(conn)
        for piece in ("item-A", "item-B", "item-C", None):
            sequence = 60 if piece is None else 50
            op = case.operation(seq=sequence, piece_id=piece,
                                op_code="D-point-" + str(piece), unit_hours=0)
            result["operations"].append({"operation_id": op, "piece_id": piece,
                "sequence": sequence, "target_quantity": 3 if piece is None else 1,
                "batch_quantity": 3, "total_hours": 0})
        rival = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='B2'").fetchone()[0]
        conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,"
                     "start_time,end_time,lock_status) VALUES (4,?,'M1','O1',"
                     "'2026-09-09 09:00:00','2026-09-09 09:30:00','locked')", (rival,))
        for index in range(1, 22):
            batch = f"Z-D-{index:02d}"
            case.batch(batch, ready_status="partial" if index % 3 == 0 else "no")
            case.operation(batch=batch)
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        result.update(task_count=len(result["operations"]), locked_operation_id=rival,
                      points=4, picker_batch_count=23, profile="D-positive-common-piece-points")
    return result


def observe_official_tables(app, root):
    from flask import request

    @app.after_request
    def record(response):
        if request.path.startswith("/api/workbench/"):
            with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only=ON")
                conn.execute("BEGIN")
                official = {name: [dict(row) for row in conn.execute(
                    'SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name in ("Schedule", "ScheduleHistory")}
            row = {"path": request.path, "method": request.method,
                   "status": response.status_code, "official": official}
            with (Path(root) / "final_planning_official.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return response
