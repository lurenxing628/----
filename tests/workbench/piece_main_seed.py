"""EQ fixture-only writes; actual EF split layout and retained historical sources."""

import os
import sqlite3
from contextlib import closing

from tests.workbench.piece_chain_support import piece_layout
from tests.workbench.plan_catalog_support import candidate, scenario
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.run_live_server_support import seed_run_data


def seed(app, **_options):
    original = seed_run_data(app, include_formal=False)
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        case = JobCase(conn)
        case.op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='B1'").fetchone()[0]
        for index in (2, 3):
            suffix = str(index)
            conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?, 'T1')", ("M" + suffix, "Lathe " + suffix))
            conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", ("O" + suffix, "Operator " + suffix))
            conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", ("O" + suffix, "M" + suffix))
        ids = piece_layout(case, parallel=True, common=True, unit=.25)
        pieces = ("item-A", "item-B", "item-C")
        if os.environ.get("PIECE_MAIN_LONG_IDS") == "1":
            labels = ("分件甲原始身份" + "中文保留" * 16, "分件乙原始身份" + "X" * 120,
                      "分件丙原始身份" + "连续业务编号" * 12)
            mapping = dict(zip(pieces, labels))
            conn.executemany("UPDATE BatchOperations SET piece_id=? WHERE piece_id=?", [(mapping[piece], piece) for piece in pieces])
            ids = {(mapping.get(piece, piece), sequence): op for (piece, sequence), op in ids.items()}
            pieces = labels
        case.batch("B2", quantity=1)
        rival = case.operation(batch="B2", seq=10, unit_hours=.5)
        conn.commit()
        for version in (1, 2, 3, 4):
            case.plan(version, [ids[None, 10]], start="2026-09-09T08:00:00", end="2026-09-09T08:45:00")
        candidate(conn, 3, "critical_best", op_id=ids[None, 10])
        scenario(conn, "piece-main-old-scene", 3, op_id=ids[None, 10])
        conn.commit()
        with app.app_context():
            receipt = case.command("create", case.task(4, ids[None, 10]), case.values(3,
                actual_end="2026-09-09T08:45:00", effective_processing_hours=.75))
        assert receipt["ok"], receipt
        expected = [{"operation_id": op, "piece_id": piece, "sequence": sequence,
                     "target_quantity": 3 if piece is None else 1, "batch_quantity": 3,
                     "total_hours": .75 if piece is None else .25}
                    for (piece, sequence), op in ids.items()]
        expected.append({"operation_id": rival, "piece_id": None, "sequence": 10,
                         "target_quantity": 1, "batch_quantity": 1, "total_hours": .5})
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        return {**original, "batches": ["B1", "B2"], "pieces": list(pieces), "task_count": 9, "operations": expected,
                "seed_source": "tests/workbench/piece_chain_support.py:piece_layout",
                "original_plan_ref": case.plan_ref(4), "official_version": 4,
                "original_receipt_ref": receipt["receipt_ref"],
                "original_production_reports": conn.execute("SELECT count(*) FROM WorkbenchProductionReports").fetchone()[0],
                "original_legacy_events": conn.execute("SELECT count(*) FROM OperationExecutionEvents").fetchone()[0]}
