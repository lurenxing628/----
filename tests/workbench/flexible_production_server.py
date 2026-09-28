"""Dedicated disposable fixture for stage materials and quantity-lot controls."""

import argparse
import sqlite3
import sys
from pathlib import Path

from resource_live_server import seed_resources, serve


def seed(app):
    seed_resources(app)
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('FLEX-P','分阶段用料验证零件')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity,status,ready_status) VALUES ('FLEX-B','FLEX-P',100,'pending','no')")
        for sequence in (1, 2):
            conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,
                setup_hours,unit_hours,machine_id,operator_id,status) VALUES (?,'FLEX-B',?,'RT-IN','Turning','internal',0,.01,'RT-M','RT-O','pending')""",
                         ("FLEX-B-" + str(sequence), sequence))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sys.exit(serve(parser.parse_args().root, fixture_seed=seed))
