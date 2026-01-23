import os
import tempfile
import time
import traceback
from datetime import datetime


def find_repo_root():
    """
    兼容不同目录结构：
    - 优先使用当前 tests/ 的上一级作为 repo_root
    - fallback：扫描 D:\\Github 下包含 app.py 与 schema.sql 的目录
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root

    base = r"D:\Github"
    try:
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if not os.path.isdir(p):
                    continue
                if os.path.exists(os.path.join(p, "app.py")) and os.path.exists(os.path.join(p, "schema.sql")):
                    return p
    except Exception:
        pass

    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def write_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase6（Scheduler：批次/工序/日历/配置）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{os.sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase6_")
    test_db = os.path.join(tmpdir, "aps_phase6_test.db")
    lines.append("")
    lines.append("## 0. 测试环境")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import AppError, ValidationError
    from core.services.scheduler import BatchService, CalendarService, ConfigService, ScheduleService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

    try:
        # 0) 准备基础数据（工种/供应商/人员/设备/零件模板）
        lines.append("")
        lines.append("## 1. 准备基础数据（工艺模板/资源）")

        # 工种：内部 + 外部
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_1", "数铣", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_1", "标印", "external"))

        # 供应商（外部）
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            ("S001", "外协-标印厂", "OT_EX_1", 1.0, "active"),
        )

        # 人员/设备
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP002", "李四", "inactive"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "CNC-01", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC002", "CNC-02", "maintain"))
        # 人员-设备关联：用于验证“排产补充只能选择可操作组合”
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))

        # 零件 + 模板工序：5内部，35外部（属于合并周期组）
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("A1234", "壳体-大", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("A1234", 5, "OT_IN_1", "数铣", "internal", None, None, None, 0.5, 0.2, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("A1234", 35, "OT_EX_1", "标印", "external", "S001", None, "A1234_EXT_1", 0, 0, "active"),
        )
        conn.execute(
            "INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days) VALUES (?, ?, ?, ?, ?, ?)",
            ("A1234_EXT_1", "A1234", 35, 35, "merged", 3),
        )
        conn.commit()

        batch_svc = BatchService(conn, logger=None, op_logger=None)

        # 1.1) 模板缺失时：批次创建自动解析 route_raw 并生成模板
        lines.append("")
        lines.append("## 1.1 批次创建：模板缺失时自动解析 route_raw")
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P_AUTO", "自动解析件", "5数铣10数铣", "no"),
        )
        conn.commit()
        b_auto = batch_svc.create_batch_from_template(batch_id="B_AUTO", part_no="P_AUTO", quantity=1, priority="normal", ready_status="yes")
        ops_auto = batch_svc.list_operations("B_AUTO")
        tmpl_cnt = conn.execute("SELECT COUNT(1) AS c FROM PartOperations WHERE part_no='P_AUTO'").fetchone()["c"]
        lines.append(f"- 自动解析：PartOperations={tmpl_cnt} BatchOperations={len(ops_auto)}（期望均 > 0）")
        if tmpl_cnt <= 0 or len(ops_auto) <= 0:
            raise RuntimeError("模板缺失自动解析失败：未生成 PartOperations 或 BatchOperations")

        # 2) 批次创建事务：失败时不留脏数据
        lines.append("")
        lines.append("## 2. 批次创建事务：失败回滚（不留脏数据）")
        # 先插入一个“干扰”批次与工序，使得 op_code 全局唯一冲突
        batch_svc.create(batch_id="DUMMY", part_no="A1234", quantity=1, priority="normal", ready_status="no")
        conn.execute(
            """
            INSERT INTO BatchOperations
            (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("BFAIL_05", "DUMMY", None, 5, "OT_IN_1", "数铣", "internal", None, None, None, 0, 0, None, "pending"),
        )
        conn.commit()

        try:
            batch_svc.create_batch_from_template(batch_id="BFAIL", part_no="A1234", quantity=10, priority="urgent", ready_status="yes")
            raise RuntimeError("期望触发 UNIQUE(op_code) 冲突，但未触发")
        except AppError as e:
            lines.append(f"- 触发预期异常：code={e.code.value} message={e.message}")

        # 验证：BFAIL 不存在，且没有 batch_id=BFAIL 的工序
        b = batch_svc.batch_repo.get("BFAIL")
        op_cnt = conn.execute("SELECT COUNT(1) AS c FROM BatchOperations WHERE batch_id='BFAIL'").fetchone()["c"]
        lines.append(f"- 回滚校验：BFAIL 批次存在={bool(b)}（期望 False），BFAIL 工序数={op_cnt}（期望 0）")
        if b is not None or op_cnt != 0:
            raise RuntimeError("事务回滚失败：出现“批次有了但工序没生成/部分生成”的脏数据")

        # 3) 正常创建批次并生成工序
        lines.append("")
        lines.append("## 3. 正常创建批次并生成工序（op_code 规则）")
        b1 = batch_svc.create_batch_from_template(batch_id="B001", part_no="A1234", quantity=50, due_date="2026-01-25", priority="urgent", ready_status="yes")
        ops = batch_svc.list_operations("B001")
        lines.append(f"- 批次：{b1.batch_id} 图号={b1.part_no} 数量={b1.quantity} 工序数={len(ops)}（期望 2）")
        codes = [o.op_code for o in ops]
        lines.append(f"- op_code：{codes}")
        if len(ops) != 2 or "B001_05" not in codes or "B001_35" not in codes:
            raise RuntimeError("批次工序生成失败：op_code 或数量不符合预期")

        # 4) 工序补充：内部工序设备/人员/工时 + 可清空
        lines.append("")
        lines.append("## 4. 工序补充：内部工序（设备/人员/工时）")
        sch_svc = ScheduleService(conn, logger=None, op_logger=None)
        op_internal = next(o for o in ops if o.source == "internal")

        # 不可用设备/人员应报错（中文）
        try:
            sch_svc.update_internal_operation(op_internal.id, machine_id="MC002", operator_id="OP001", setup_hours=0.1, unit_hours=0.1)
            raise RuntimeError("期望维护状态设备不可用，但未报错")
        except AppError as e:
            lines.append(f"- 维护设备不可用：{e.message}")
        try:
            sch_svc.update_internal_operation(op_internal.id, machine_id="MC001", operator_id="OP002", setup_hours=0.1, unit_hours=0.1)
            raise RuntimeError("期望停用人员不可用，但未报错")
        except AppError as e:
            lines.append(f"- 停用人员不可用：{e.message}")

        # 正常写入
        updated = sch_svc.update_internal_operation(op_internal.id, machine_id="MC001", operator_id="OP001", setup_hours=0.5, unit_hours=0.2)
        lines.append(f"- 写入后：machine={updated.machine_id} operator={updated.operator_id} setup={updated.setup_hours} unit={updated.unit_hours}")
        if updated.machine_id != "MC001" or updated.operator_id != "OP001":
            raise RuntimeError("内部工序补充写入失败")

        # 人机不匹配应报错（中文）
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC003", "CNC-03", "active"))
        conn.commit()
        try:
            sch_svc.update_internal_operation(op_internal.id, machine_id="MC003", operator_id="OP001", setup_hours=0.5, unit_hours=0.2)
            raise RuntimeError("期望人机不匹配时报错，但未报错")
        except AppError as e:
            lines.append(f"- 人机不匹配限制生效：{e.message}")

        # 清空（依赖 repo.update 支持 NULL）
        cleared = sch_svc.update_internal_operation(op_internal.id, machine_id="", operator_id="", setup_hours=0, unit_hours=0)
        row = conn.execute("SELECT machine_id, operator_id FROM BatchOperations WHERE id=?", (op_internal.id,)).fetchone()
        lines.append(f"- 清空后：machine_id={row['machine_id']} operator_id={row['operator_id']}（期望均为 NULL）")
        if row["machine_id"] is not None or row["operator_id"] is not None:
            raise RuntimeError("清空设备/人员失败（字段未变为 NULL）")

        # 5) 外部工序：merged 外部组禁止逐道设置周期
        lines.append("")
        lines.append("## 5. 工序补充：外部工序（合并周期限制）")
        op_ext = next(o for o in ops if o.source == "external")
        hint = sch_svc.get_external_merge_hint(op_ext.id)
        lines.append(f"- merge_hint：{hint}")
        try:
            sch_svc.update_external_operation(op_ext.id, supplier_id="S001", ext_days=2)
            raise RuntimeError("期望 merged 外部组禁止逐道设置 ext_days，但未报错")
        except ValidationError as e:
            lines.append(f"- merged 限制生效：{e.message}")

        # 6) 配置：默认值 + 权重校验
        lines.append("")
        lines.append("## 6. 排产配置：默认值/更新/校验")
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        snap = cfg_svc.get_snapshot()
        lines.append(f"- 默认：{snap.to_dict()}")
        cfg_svc.set_strategy("weighted")
        cfg_svc.set_weights(0.4, 0.5, 0.1, require_sum_1=True)
        snap2 = cfg_svc.get_snapshot()
        lines.append(f"- 更新后：{snap2.to_dict()}")
        try:
            cfg_svc.set_weights(0.4, 0.4, 0.1, require_sum_1=True)
            raise RuntimeError("期望权重总和校验失败，但未报错")
        except ValidationError as e:
            lines.append(f"- 权重总和校验：{e.message}")

        # 7) 日历：upsert + adjust + add_working_hours
        lines.append("")
        lines.append("## 7. 工作日历：upsert + 工作时间计算")
        cal_svc = CalendarService(conn, logger=None, op_logger=None)
        cal_svc.upsert("2026-01-21", day_type="workday", shift_hours=2, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="短班次")
        cal_svc.upsert("2026-01-22", day_type="holiday", shift_hours=0, efficiency=1.0, allow_normal="no", allow_urgent="no", remark="停工")
        start_dt = datetime(2026, 1, 21, 8, 0, 0)
        end_dt = cal_svc.add_working_hours(start_dt, 3, priority="normal")
        lines.append(f"- add_working_hours：start={start_dt} hours=3 end={end_dt}（期望跨天到 2026-01-23 09:00）")
        # 2026-01-21 仅 2h（08:00-10:00），2026-01-22 停工，剩 1h 到 2026-01-23 09:00（默认工作日）
        if end_dt.strftime("%Y-%m-%d %H:%M") != "2026-01-23 09:00":
            raise RuntimeError("add_working_hours 结果不符合预期")

        # 成功结论
        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Phase6（Scheduler 基础能力）冒烟测试通过（事务/工序补充/日历/配置）。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = os.path.join(repo_root, "evidence", "Phase6", "smoke_phase6_report.md")
    write_report(report_path, lines)
    print("OK")
    print(report_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        repo_root = None
        try:
            repo_root = find_repo_root()
        except Exception:
            pass

        lines = []
        lines.append("# Phase6（Scheduler：批次/工序/日历/配置）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase6", "smoke_phase6_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

