"""Complex nonempty data prepared before any user interaction; Python 3.8."""

import sqlite3
from contextlib import closing


def seed(app):
    from tests.workbench.process_query_support import seed_process

    states = [str(width) + "-" + theme for width in (1920, 1392) for theme in ("light", "dark")]
    result = {"states": {}, "empty_part": "PROC-002", "locked_part": "P1"}
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        seed_process(conn)
        long_operation = "精密车削工序长中文名称与表格换行及归属核对"
        conn.execute("UPDATE OpTypes SET name=? WHERE op_type_id='PROC-IN'", (long_operation,))
        for state in states:
            prefix = "ED物料-" + state + "-"
            target = prefix + "021-精密长轴承毛坯批次编号零一二三四五六七八九"
            for number in range(1, 26):
                code = target if number == 21 else prefix + str(number).zfill(3)
                conn.execute("""INSERT INTO Materials(material_id,name,spec,unit,stock_qty,status,remark)
                    VALUES (?,?,?,?,?,'active',?)""", (code, "高强度耐腐蚀精密轴承毛坯材料名称需要完整核对" * 2,
                    None if number == 1 else "直径120毫米/长度850毫米/按长规格与批号分别验收", None if number == 1 else "千克",
                    0 if number in (1, 21) else number + .125,
                    None if number == 1 else "原备注必须完整保留：本批材料只用于离线验证，不得替换其他记录。\n" * 3))
            code = "ED工艺-" + state + "-长中文图号精密轴套工序与外协组核对"
            route = "10" + long_operation + "20热处理30检验40热处理"
            conn.execute("""INSERT INTO Parts(part_no,part_name,route_raw,route_parsed,remark)
                VALUES (?,?,?,'yes',?)""", (code,
                "多阶段精密轴套工艺名称与长中文资料展示核对" * 2, route, "零件原备注必须保留\n" * 5))
            for seq in (20, 40):
                group = code + "-组-" + str(seq)
                conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id,remark)
                    VALUES (?,?,?,?,'merged',?,'PROC-S',?)""", (group, code, seq, seq, 6.75 if seq == 20 else 9.5,
                    "外协组原备注：多次委外热处理工艺需按本组范围核对，不得影响另一外协组。" * 3))
            for seq, name, kind, source, setup, unit in ((10, long_operation, "PROC-IN", "internal", .5, .125),
                    (20, "热处理", "PROC-EX", "external", 0, 0), (30, "检验", "PROC-Q", "internal", 0, 0),
                    (40, "热处理", "PROC-EX", "external", 0, 0)):
                external = source == "external"
                conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,
                    ext_days,ext_group_id,setup_hours,unit_hours,status) VALUES (?,?,?,?,?,?,?,?,?,?,'active')""",
                    (code, seq, kind, name, source, "PROC-S" if external else None,
                     None, code + "-组-" + str(seq) if external else None, setup, unit))
            result["states"][state] = {"material_prefix": prefix, "material": target,
                "empty_material": prefix + "001", "part": code, "route": route, "long_operation": long_operation}
            scale = "ED工艺-" + state + "-六十三道工序分页只读"
            conn.execute("INSERT INTO Parts(part_no,part_name,route_parsed) VALUES (?,?,'yes')", (scale, "工序分页及空筛选核对"))
            conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours)
                VALUES (?,?,'PROC-IN',?,'internal',0,1)""", [(scale, n, ("复核子集" if n <= 25 else "其余工序") + str(n)) for n in range(1, 64)])
            result["states"][state]["scale_part"] = scale
        conn.execute("UPDATE Suppliers SET name=? WHERE supplier_id='PROC-S'",
                     ("热处理外协供应商全称与多个工艺组确认范围核对" * 2,))
        conn.commit()
        from tests.workbench.calibration_adoption_support import INTENT, PREVIEW_INTENT, service
        ref = conn.execute("""SELECT r.ref FROM WorkbenchEntityRefs r JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
            WHERE r.kind='template_operation' AND r.active=1 AND o.part_no='P1' AND o.seq=1""").fetchone()[0]
        with app.app_context():
            adoption = service(conn, clock=None)
            preview = adoption.preview(ref, PREVIEW_INTENT)
            assert preview["validation"]["can_adopt"], preview
            adoption.confirm(ref, preview["write_context"]["write_token"], "ed-fixture-calibration-lock-0001", INTENT)
        result["locked_ref"] = ref
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    return result
