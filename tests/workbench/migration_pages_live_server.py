"""Guarded real-application fixture for the integrated process/plan/report pages."""

import argparse
import sqlite3
import sys
from pathlib import Path

from live_environment import REPO
from resource_live_server import seed_resources, serve

sys.path.insert(0, str(REPO))
from tests.workbench.plan_read_support import seed_plans
from tests.workbench.process_query_support import seed_process
from tests.workbench.process_stage_api_support import seed_history
from tests.workbench.process_stage_live_server import state
from tests.workbench.report_api_support import event


def seed(app):
    seed_resources(app)
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        seed_process(conn)
        seed_history(conn)
        first = seed_plans(conn)
        conn.execute("UPDATE Parts SET part_name='跨夜加工与执行核对' WHERE part_no='CAT-P'")
        conn.execute("UPDATE Batches SET part_name='跨夜加工与执行核对',due_date='2026-09-08' WHERE batch_id='CAT-B'")
        conn.execute("UPDATE Machines SET name='精密车床一号',op_type_id='RT-IN' WHERE machine_id='PRIVATE-M1'")
        conn.execute("UPDATE Operators SET name='夜班操作人员' WHERE operator_id='PRIVATE-O1'")
        conn.execute("UPDATE BatchOperations SET op_type_name='跨夜车削',source='internal',setup_hours=0,unit_hours=8 WHERE id=?", (first,))
        conn.execute("""UPDATE Schedule SET start_time='2026-09-07 22:30:00',end_time='2026-09-08 06:30:00'
            WHERE version=3 AND op_id=?""", (first,))
        for day, start, end in (("2026-09-07", "22:30", "06:30"), ("2026-09-08", "08:00", "18:00")):
            conn.execute("""INSERT INTO WorkCalendar(date,day_type,shift_start,shift_end,shift_hours,
                efficiency,allow_normal,allow_urgent) VALUES (?,'workday',?,?,?,1,'yes','yes')""",
                         (day, start, end, 8 if day.endswith("07") else 10))
        ids = [first]
        for number in range(2, 24):
            cursor = conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours)
                VALUES (?,'CAT-B',?,'精加工','internal',0,1)""", ("INTEGRATED-" + str(number), number))
            ids.append(cursor.lastrowid)
            conn.execute("""INSERT INTO Schedule(version,op_id,start_time,end_time,machine_id,operator_id)
                VALUES (3,?,'2026-09-08 08:00:00','2026-09-08 09:00:00','PRIVATE-M1','PRIVATE-O1')""", (cursor.lastrowid,))
        event(conn, ids[0], "start", "2026-09-07 22:30:00", actual_machine_id="RT-M", actual_operator_id="RT-O")
        event(conn, ids[0], "finish", "2026-09-08 06:40:00", quantity_done=1)
        event(conn, ids[1], "start", "2026-09-08 08:00:00")
        event(conn, ids[1], "finish", "2026-09-08 09:10:01", quantity_done=1)
        event(conn, ids[2], "start", "2026-09-08 08:00:00")
        conn.executemany("INSERT INTO Parts(part_no,part_name,remark) VALUES (?,?,?)",
                         [("CROSSPAGE-" + str(index).zfill(3), "跨页核对零件 " + str(index), "保留未展示的原备注")
                          for index in range(1, 64)])
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    sys.exit(serve(parser.parse_args().root, fixture_seed=seed, state_reader=state))
