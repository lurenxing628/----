"""Managed isolated UI fixture with long tables, real reports and a material risk."""

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as live
from tests.workbench.run_jobs_support import JobCase

_seed = live.seed_run_data


def seed_ui_data(app, **kwargs):
    if not kwargs.get("calibration") or kwargs.get("include_formal"):
        raise ValueError("UI refinement server requires --profile calibration")
    expected = _seed(app, **kwargs)
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        case = JobCase(conn)
        for index in range(1, 25):
            code = f"UI-{index:03d}"
            case.batch(code, part_name="界面验证长表零件", due_date="2026-09-25")
            case.operation(code)
        conn.execute("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES ('UI-MATERIAL','界面验证待补材料','件',0)")
        conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) "
                     "VALUES ('B1','UI-MATERIAL',10,0,'no')")
        conn.execute("UPDATE Batches SET ready_status='no' WHERE batch_id='B1'")
        conn.commit()
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("UI fixture foreign keys are invalid")
        expected["ui_refinement"] = {"version": 1, "extra_batches": 24, "material_risk_batch": "B1",
                                     "calibration_samples": 5, "batch_count": conn.execute("SELECT COUNT(*) FROM Batches").fetchone()[0]}
    return expected


if __name__ == "__main__":
    live.seed_run_data = seed_ui_data
    sys.exit(live.main())
