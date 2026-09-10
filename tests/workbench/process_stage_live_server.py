"""Dedicated stage-write fixture; reuse isolation guards, never the old live probe."""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

from live_environment import REPO, write_json
from resource_live_server import serve

sys.path.insert(0, str(REPO))
from tests.workbench.process_query_support import seed_process
from tests.workbench.process_stage_api_support import seed_history, seed_stage_scale


def seed(app):
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        objects = [list(row) for row in conn.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")]
        write_json(Path(app.config["DATABASE_PATH"]).with_name("process-stage-fixture-schema.json"), {
            "version": conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0],
            "schema_sha256": hashlib.sha256(json.dumps(objects, ensure_ascii=True).encode("ascii")).hexdigest(),
            "process_objects": [row for row in objects if "process" in row[1].lower()],
        })
        seed_process(conn)
        seed_history(conn)
        conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,'internal')",
                         [("STAGE-TYPE-" + str(i), "Choice " + str(i)) for i in range(2000)])
        conn.executemany("INSERT INTO Suppliers(supplier_id,name,default_days,status) VALUES (?,?,2,'active')",
                         [("STAGE-SUP-" + str(i), "Supplier choice " + str(i)) for i in range(2000)])
        for width in (1920, 1392):
            for theme in ("light", "dark"):
                code = "STAGE-" + str(width) + "-" + theme
                conn.execute("""INSERT INTO Parts(part_no,part_name,route_raw,route_parsed,remark)
                    SELECT ?,part_name,route_raw,route_parsed,remark FROM Parts WHERE part_no='PROC-001'""", (code,))
                group = code + "-GROUP"
                conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id,remark)
                    SELECT ?,?,start_seq,end_seq,merge_mode,total_days,supplier_id,remark FROM ExternalGroups WHERE group_id='PROC-G'""", (group, code))
                conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,supplier_id,ext_days,
                    ext_group_id,setup_hours,unit_hours,private_stage_note)
                    SELECT ?,seq,op_type_name,op_type_id,source,supplier_id,ext_days,
                    CASE WHEN ext_group_id IS NULL THEN NULL ELSE ? END,setup_hours,unit_hours,private_stage_note
                    FROM PartOperations WHERE part_no='PROC-001'""", (code, group))
        # Scale templates are revisited sequentially across themes, not duplicated.
        if os.environ.get("WORKBENCH_PROCESS_STAGE_SCOPE", "all") != "regular":
            seed_stage_scale(conn, "STAGE-2000", 2000, confirmed_route=False)
            seed_stage_scale(conn, "STAGE-10000", 10000)
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def state(db):
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: [dict(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')]
                for table in tables}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sys.exit(serve(parser.parse_args().root, fixture_seed=seed, state_reader=state))
