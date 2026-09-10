"""Reuse the guarded local server with real process fixtures, no production DB."""

import argparse
import sqlite3
import sys
from pathlib import Path

from live_environment import REPO
from resource_live_server import seed_resources, serve

sys.path.insert(0, str(REPO))
from tests.workbench.process_query_support import seed_process


def seed(app):
    seed_resources(app)
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        seed_process(conn)
        conn.executemany("INSERT INTO Parts(part_no,part_name,remark) VALUES (?,?,?)", [
            (f"PROC-{i:03d}", "复杂零件 " + str(i), "原备注保留") for i in range(10, 35)])
        conn.execute("INSERT INTO Parts(part_no,part_name,route_raw,route_parsed) VALUES ('PROC-LARGE','2000道工序模板','现有复杂模板','yes')")
        conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours)
            VALUES ('PROC-LARGE',?,'PROC-IN','车削','internal',.5,.125)""", [(i,) for i in range(1, 2001)])
        conn.commit()


def state(db):
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: [dict(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in tables}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sys.exit(serve(parser.parse_args().root, fixture_seed=seed, state_reader=state))
