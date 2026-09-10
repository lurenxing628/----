"""Only real plan facts are seeded; the production engine must derive every chain edge."""

from tests.workbench.execution_ledger_support import LedgerCase


def chain_plan(api):
    with api.db() as conn:
        case = LedgerCase(conn)
        conn.executemany("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',10)",
                         [("CHAIN-B2",), ("CHAIN-B3",), ("CHAIN-B4",)])
        conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')",
                         [("CHAIN-M3", "链设备三"), ("CHAIN-M4", "独立设备四")])
        conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)",
                         [("CHAIN-O2", "链人员二"), ("CHAIN-O3", "链人员三"), ("CHAIN-O4", "独立人员四")])
        conn.execute("UPDATE Schedule SET end_time='2026-09-09 09:00:00' WHERE version=1 AND op_id=1")
        specs = [("CHAIN-OP2", "B1", 2, "M2", "CHAIN-O2", "09:00:00", "10:00:00"),
                 ("CHAIN-OP3", "CHAIN-B2", 1, "M2", "CHAIN-O3", "10:30:00", "11:30:00"),
                 ("CHAIN-OP4", "CHAIN-B3", 1, "CHAIN-M3", "CHAIN-O3", "12:00:00", "13:00:00"),
                 ("CHAIN-OP5", "CHAIN-B4", 1, "CHAIN-M4", "CHAIN-O4", "08:00:00", "08:30:00")]
        ids = [1]
        for code, batch, sequence, machine, operator, start, end in specs:
            operation = case.op(code, seq=sequence, batch=batch)
            conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,?,?,?,?)",
                         (operation, machine, operator, "2026-09-09 " + start, "2026-09-09 " + end))
            ids.append(operation)
        conn.commit()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        return {"plan_ref": case.plan_ref(1), "task_refs": [case.task(1, op) for op in ids], "operation_ids": ids,
                "expected_edge_types": ["process", "machine", "operator"], "expected_gap_minutes": [0, 30, 30],
                "seed_method": "Five Schedule rows; no chain table, output dictionary, route stub or engine replacement."}
