"""Extend ED's read-only fixture factory, retaining separate valid/invalid owners."""

import sqlite3
from contextlib import closing

from tests.workbench.ed_material_process_seed import seed as seed_ed


def seed(app):
    result = seed_ed(app)
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        for state, data in result["states"].items():
            code = data["part"]
            conn.execute("UPDATE ExternalGroups SET end_seq=25 WHERE part_no=? AND start_seq=20", (code,))
            conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,
                ext_days,ext_group_id,setup_hours,unit_hours)
                VALUES (?,25,'PROC-EX','热处理','external','PROC-S',NULL,?,0,0)""", (code, code + "-组-20"))
            data["route"] = data["route"].replace("30检验", "25热处理30检验")
            conn.execute("UPDATE Parts SET route_raw=? WHERE part_no=?", (data["route"], code))
            data["damaged"] = {}
            for kind in ("total", "cross_part", "member", "member_value", "operation", "separate"):
                target = "ER-" + state + "-" + kind
                data["damaged"][kind] = target
                conn.execute("""INSERT INTO Parts(part_no,part_name,route_raw,route_parsed,remark)
                    SELECT ?,part_name,route_raw,route_parsed,remark FROM Parts WHERE part_no=?""", (target, code))
                conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id,remark)
                    SELECT ?||'-'||start_seq,?,start_seq,end_seq,merge_mode,total_days,supplier_id,remark
                    FROM ExternalGroups WHERE part_no=?""", (target, target, code))
                conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,
                    ext_days,ext_group_id,setup_hours,unit_hours)
                    SELECT ?,seq,op_type_id,op_type_name,source,supplier_id,ext_days,
                    CASE WHEN ext_group_id IS NULL THEN NULL WHEN seq IN (20,25) THEN ?||'-20' ELSE ?||'-40' END,
                    setup_hours,unit_hours FROM PartOperations WHERE part_no=?""", (target, target, target, code))
                if kind == "total":
                    conn.execute("UPDATE ExternalGroups SET total_days=NULL WHERE group_id=?", (target + "-20",))
                elif kind == "cross_part":
                    conn.execute("UPDATE ExternalGroups SET part_no='PROC-002' WHERE group_id=?", (target + "-20",))
                elif kind == "member":
                    conn.execute("UPDATE PartOperations SET source='internal' WHERE part_no=? AND seq=25", (target,))
                elif kind in ("member_value", "operation"):
                    conn.execute("UPDATE PartOperations SET ext_days=? WHERE part_no=? AND seq=20",
                                 (-1 if kind == "member_value" else 3.25, target))
                else:
                    conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id=?", (target + "-20",))
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    return result
