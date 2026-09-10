"""Small, nonempty manufacturing fixture on the real current file schema."""

import json
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import ensure_schema, get_connection
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.run_live_server_support import seed_run_data


def seed(root, *, include_candidate_baseline=False):
    root = Path(root).resolve()
    database = root / "aps.db"
    ensure_schema(str(database), None, schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"))
    app = SimpleNamespace(config={"DATABASE_PATH": str(database)})
    expected = seed_run_data(app, include_formal=False, outsourcing=True)
    with closing(get_connection(str(database))) as conn:
        job = JobCase(conn)
        job.batch("FQ1")
        candidate_operation = job.operation(batch="FQ1")
        conn.execute("UPDATE Batches SET quantity=2,due_date='2026-09-08',ready_status='no',part_name='F operations fixture' WHERE batch_id='B1'")
        op = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='B1'").fetchone()[0]
        conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0.5 WHERE id=?", (op,))
        conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time) VALUES (1,'final-operations','success',?,'2026-09-08T12:00:00')", (json.dumps({"scheduled_ops": 1}),))
        conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,'M1','O1','2026-09-09T08:00:00','2026-09-09T10:00:00')", (op,))
        if include_candidate_baseline:
            conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,'M1','O1','2026-09-09T10:00:00','2026-09-09T10:45:00')", (candidate_operation,))
        conn.execute("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES ('F-MAT','F steel','kg',900)")
        conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) VALUES ('B1','F-MAT',10,2,'no')")
        conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_detail) VALUES ('M1','2026-09-09T09:00:00','2026-09-09T11:00:00','F maintenance record')")
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('FINAL_OPERATIONS','selected')")
        for number in range(31):
            conn.execute("INSERT INTO OperationLogs(log_time,log_level,module,action,target_type,target_id,detail) VALUES (?,?,?,?,?,?,?)",
                         (f"2026-09-10 09:00:{number:02d}", "INFO", "final_operations", "verify", "fixture", str(number), f"F operation row {number:02d}"))
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    manager = BackupManager(str(database), str(root / "backups"))
    selected = manager.backup(suffix="F_selected_source")
    with closing(get_connection(str(database))) as conn:
        conn.execute("UPDATE SystemConfig SET config_value='current' WHERE config_key='FINAL_OPERATIONS'")
        conn.commit()
    (root / "seed.json").write_text(json.dumps({**expected, "source": selected}), encoding="utf-8")
    return expected
