import os
import sys
import tempfile
import time
import traceback


def find_repo_root():
    """
    约定：项目在 D:\\Github 下，且根目录包含 app.py 与 schema.sql。
    （保持与 Phase0/Phase1 冒烟测试一致，便于在用户机器上复用。）
    """
    base = r"D:\Github"
    for d in os.listdir(base):
        p = os.path.join(base, d)
        if not os.path.isdir(p):
            continue
        if os.path.exists(os.path.join(p, "app.py")) and os.path.exists(os.path.join(p, "schema.sql")):
            return p
    raise RuntimeError("未找到项目根目录：要求在 D:\\Github 下存在包含 app.py 与 schema.sql 的目录")


def write_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase2（Models + Repositories）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    # 临时目录（避免污染真实 db/logs/backups）
    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase2_")
    test_db = os.path.join(tmpdir, "aps_phase2_test.db")
    lines.append("")
    lines.append("## 0. 测试环境")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    # 确保可以 import 项目模块
    sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import AppError, ErrorCode
    from core.infrastructure.transaction import TransactionManager
    from data.repositories import (
        CalendarRepository,
        ConfigRepository,
        MachineRepository,
        OperationLogRepository,
        OperatorMachineRepository,
        OperatorRepository,
        OpTypeRepository,
        ScheduleHistoryRepository,
    )

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

    try:
        # 基础表检查
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
        lines.append("")
        lines.append("## 1. Schema 检查（Phase2 相关表）")
        lines.append(f"- 表数量：{len(tables)}")
        for t in [
            "Operators",
            "Machines",
            "OperatorMachine",
            "OpTypes",
            "WorkCalendar",
            "ScheduleConfig",
            "OperationLogs",
            "ScheduleHistory",
        ]:
            lines.append(f"- 是否存在 {t}：{t in tables}")

        tx = TransactionManager(conn)

        op_repo = OperatorRepository(conn)
        ot_repo = OpTypeRepository(conn)
        m_repo = MachineRepository(conn)
        om_repo = OperatorMachineRepository(conn)
        cal_repo = CalendarRepository(conn)
        cfg_repo = ConfigRepository(conn)
        log_repo = OperationLogRepository(conn)
        hist_repo = ScheduleHistoryRepository(conn)

        lines.append("")
        lines.append("## 2. Operators 仓库：CRUD + UNIQUE 异常（中文）")
        with tx.transaction():
            op_repo.create({"operator_id": "OP001", "name": "张三", "status": "active", "remark": "测试"})
        got = op_repo.get("OP001")
        if not got or got.name != "张三":
            raise RuntimeError("Operators.get 校验失败：未读到 OP001 或字段不一致")
        with tx.transaction():
            op_repo.update("OP001", {"remark": "已更新"})
        got2 = op_repo.get("OP001")
        if not got2 or got2.remark != "已更新":
            raise RuntimeError("Operators.update 校验失败：remark 未更新")

        # UNIQUE 冲突（重复插入）
        try:
            with tx.transaction():
                op_repo.create({"operator_id": "OP001", "name": "重复", "status": "active"})
            raise RuntimeError("期望触发 UNIQUE 冲突，但未触发")
        except AppError as e:
            lines.append(f"- UNIQUE 异常捕获：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.DUPLICATE_ENTRY or "不能重复" not in e.message:
                raise RuntimeError("UNIQUE 异常未翻译为中文 DUPLICATE_ENTRY")

        lines.append("")
        lines.append("## 3. Machines 仓库：CRUD + FK 异常（中文）")
        # 先创建一个工种用于正常场景
        with tx.transaction():
            ot_repo.create({"op_type_id": "OT001", "name": "数车", "category": "internal", "default_hours": 1})
        with tx.transaction():
            m_repo.create({"machine_id": "MC001", "name": "CNC-01", "op_type_id": "OT001", "status": "active"})
        if not m_repo.get("MC001"):
            raise RuntimeError("Machines.get 校验失败：未读到 MC001")

        # FK 冲突：引用不存在的 op_type_id
        try:
            with tx.transaction():
                m_repo.create({"machine_id": "MC_FK", "name": "CNC-FK", "op_type_id": "OT_NOT_EXIST", "status": "active"})
            raise RuntimeError("期望触发 FK 冲突，但未触发")
        except AppError as e:
            lines.append(f"- FK 异常捕获：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.DB_INTEGRITY_ERROR or "引用的记录不存在" not in e.message:
                raise RuntimeError("FK 异常未翻译为中文 DB_INTEGRITY_ERROR")

        lines.append("")
        lines.append("## 4. OperatorMachine 仓库：联动 + UNIQUE/FK 异常（中文）")
        # 正常关联
        with tx.transaction():
            om_repo.add("OP001", "MC001", skill_level="normal", is_primary="no")
        links = om_repo.list_by_operator("OP001")
        if len(links) != 1:
            raise RuntimeError("OperatorMachine.list_by_operator 校验失败：期望 1 条关联")

        # UNIQUE 冲突：重复关联
        try:
            with tx.transaction():
                om_repo.add("OP001", "MC001")
            raise RuntimeError("期望触发 OperatorMachine UNIQUE 冲突，但未触发")
        except AppError as e:
            lines.append(f"- OperatorMachine UNIQUE：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.DUPLICATE_ENTRY:
                raise RuntimeError("OperatorMachine UNIQUE 未翻译为 DUPLICATE_ENTRY")

        # FK 冲突：引用不存在的 operator
        try:
            with tx.transaction():
                om_repo.add("OP_NOT_EXIST", "MC001")
            raise RuntimeError("期望触发 OperatorMachine FK 冲突，但未触发")
        except AppError as e:
            lines.append(f"- OperatorMachine FK：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.DB_INTEGRITY_ERROR:
                raise RuntimeError("OperatorMachine FK 未翻译为 DB_INTEGRITY_ERROR")

        lines.append("")
        lines.append("## 5. WorkCalendar 仓库：upsert + range 查询")
        with tx.transaction():
            cal_repo.upsert({"date": "2026-01-20", "day_type": "workday", "shift_hours": 8, "efficiency": 1.0, "allow_normal": "yes", "allow_urgent": "yes", "remark": "默认"})
            cal_repo.upsert({"date": "2026-01-21", "day_type": "workday", "shift_hours": 6, "efficiency": 0.9, "allow_normal": "yes", "allow_urgent": "yes", "remark": ""})
            # 再次 upsert 覆盖
            cal_repo.upsert({"date": "2026-01-21", "day_type": "holiday", "shift_hours": 0, "efficiency": 1.0, "allow_normal": "no", "allow_urgent": "no", "remark": "停工"})
        d = cal_repo.get("2026-01-21")
        if not d or d.day_type != "holiday":
            raise RuntimeError("WorkCalendar.upsert 校验失败：2026-01-21 未被覆盖为 holiday")
        rng = cal_repo.list_range("2026-01-20", "2026-01-21")
        lines.append(f"- range 查询行数：{len(rng)}（期望 2）")
        if len(rng) != 2:
            raise RuntimeError("WorkCalendar.list_range 校验失败")

        lines.append("")
        lines.append("## 6. ScheduleConfig 仓库：set/get")
        with tx.transaction():
            cfg_repo.set("sort_strategy", "priority_first", description="当前排序策略")
            cfg_repo.set("priority_weight", "0.4", description="权重模式-优先级权重")
        if cfg_repo.get_value("sort_strategy") != "priority_first":
            raise RuntimeError("ScheduleConfig.get_value 校验失败：sort_strategy")
        all_cfg = cfg_repo.list_all()
        lines.append(f"- 配置条数：{len(all_cfg)}（期望 >= 2）")

        lines.append("")
        lines.append("## 7. OperationLogs / ScheduleHistory 仓库：基本写入与查询")
        with tx.transaction():
            log_repo.create(
                {
                    "log_level": "INFO",
                    "module": "smoke_phase2",
                    "action": "import",
                    "target_type": "operator",
                    "target_id": "OP001",
                    "operator": "system",
                    "detail": '{"filename":"demo.xlsx","mode":"overwrite","time_cost_ms":1}',
                    "error_code": None,
                    "error_message": None,
                }
            )
            hist_repo.create(
                {
                    "version": 1,
                    "strategy": "priority_first",
                    "batch_count": 1,
                    "op_count": 1,
                    "result_status": "ok",
                    "result_summary": '{"strategy_params":{"sort_strategy":"priority_first"}}',
                    "created_by": "system",
                }
            )
        recent_logs = log_repo.list_recent(limit=5, module="smoke_phase2")
        recent_hist = hist_repo.list_recent(limit=5)
        lines.append(f"- OperationLogs（module=smoke_phase2）记录数：{len(recent_logs)}（期望 >= 1）")
        lines.append(f"- ScheduleHistory 记录数：{len(recent_hist)}（期望 >= 1）")
        if len(recent_logs) < 1 or len(recent_hist) < 1:
            raise RuntimeError("留痕表写入/查询校验失败")

        # 关键 SQL 输出（便于验收留痕）
        lines.append("")
        lines.append("## 8. 关键 SQL 输出（用于验收留痕）")
        op_cnt = conn.execute("SELECT COUNT(1) FROM Operators").fetchone()[0]
        mc_cnt = conn.execute("SELECT COUNT(1) FROM Machines").fetchone()[0]
        link_cnt = conn.execute("SELECT COUNT(1) FROM OperatorMachine").fetchone()[0]
        lines.append(f"- Operators 行数：{op_cnt}")
        lines.append(f"- Machines 行数：{mc_cnt}")
        lines.append(f"- OperatorMachine 行数：{link_cnt}")

        # 成功结论
        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Phase2（Models + Repositories）冒烟测试通过（CRUD/UNIQUE/FK/日历/配置/留痕）。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = os.path.join(repo_root, "evidence", "Phase2", "smoke_phase2_report.md")
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
        lines.append("# Phase2（Models + Repositories）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase2", "smoke_phase2_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

