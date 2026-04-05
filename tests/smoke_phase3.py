import os
import sys
import tempfile
import time
import traceback
from typing import Optional


def find_repo_root():
    """
    约定：项目在 D:\\Github 下，且根目录包含 app.py 与 schema.sql。
    （保持与 Phase0/Phase1/Phase2 冒烟测试一致，便于在用户机器上复用。）
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


def is_blank_value(value) -> bool:
    return value is None or str(value).strip() == ""


def validate_operator_row(row: dict) -> Optional[str]:
    if is_blank_value(row.get("工号")):
        return "“工号”不能为空"
    if is_blank_value(row.get("姓名")):
        return "“姓名”不能为空"
    status = row.get("状态")
    if status is None or str(status).strip() == "":
        return "“状态”不能为空（允许：active / inactive）"
    status = str(status).strip()
    if status not in ("active", "inactive"):
        return "“状态”不合法（允许：active / inactive）"
    return None


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase3（人员管理模块）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    # 临时目录（避免污染真实 db/logs/backups）
    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase3_")
    test_db = os.path.join(tmpdir, "aps_phase3_test.db")
    lines.append("")
    lines.append("## 0. 测试环境")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import AppError, ErrorCode
    from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
    from core.services.common.openpyxl_backend import OpenpyxlBackend
    from core.services.personnel import OperatorMachineService, OperatorService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
        lines.append("")
        lines.append("## 1. Schema 检查（Phase3 相关表）")
        for t in ["Operators", "Machines", "OperatorMachine", "OpTypes", "BatchOperations", "Batches", "Parts"]:
            lines.append(f"- 是否存在 {t}：{t in tables}")

        # 准备 OpTypes + Machines（Machines 依赖 OpTypes 外键）
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT001", "数车", "internal"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC001", "CNC-01", "OT001", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC002", "CNC-02", "OT001", "active"))
        conn.commit()

        lines.append("")
        lines.append("## 2. 人员服务：创建/更新/清空备注（中文校验）")
        op_svc = OperatorService(conn)
        op = op_svc.create(operator_id="OP001", name="张三", status="active", remark="测试备注")
        if op.operator_id != "OP001":
            raise RuntimeError("OperatorService.create 校验失败：未创建 OP001")

        op_svc.update(operator_id="OP001", remark="")  # 清空备注
        got = op_svc.get("OP001")
        lines.append(f"- 清空备注后 remark={got.remark!r}（期望 None）")
        if got.remark is not None:
            raise RuntimeError("备注清空失败：期望 remark 为 None")

        # 非法状态校验（中文）
        try:
            op_svc.create(operator_id="OP_BAD", name="坏数据", status="BAD")
            raise RuntimeError("期望触发状态校验失败，但未触发")
        except AppError as e:
            lines.append(f"- 非法状态异常：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.VALIDATION_ERROR:
                raise RuntimeError("非法状态未翻译为 VALIDATION_ERROR")

        lines.append("")
        lines.append("## 3. 人员-设备关联服务：新增/预览/导入（复合键）")
        link_svc = OperatorMachineService(conn)
        link_svc.add_link("OP001", "MC001")
        links = link_svc.list_by_operator("OP001")
        lines.append(f"- OP001 关联数量：{len(links)}（期望 1）")
        if len(links) != 1:
            raise RuntimeError("关联新增失败：期望 1 条")

        preview_rows = link_svc.preview_import_links(
            rows=[
                {"工号": "OP001", "设备编号": "MC001"},  # 已存在
                {"工号": "OP001", "设备编号": "MC002"},  # 新增
                {"工号": "OP_NOT_EXIST", "设备编号": "MC001"},  # 人员不存在
                {"工号": "OP001", "设备编号": "MC002"},  # 文件内重复
            ],
            mode=ImportMode.OVERWRITE,
        )
        statuses = [r.status.value for r in preview_rows]
        lines.append(f"- 预览状态序列：{statuses}")
        if statuses[0] != RowStatus.UNCHANGED.value:
            raise RuntimeError("已存在关联预览状态不正确（期望 UNCHANGED）")
        if statuses[1] != RowStatus.NEW.value:
            raise RuntimeError("新增关联预览状态不正确（期望 NEW）")
        if statuses[2] != RowStatus.ERROR.value or statuses[3] != RowStatus.ERROR.value:
            raise RuntimeError("错误行预览状态不正确（期望 ERROR）")

        stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=ImportMode.OVERWRITE)
        lines.append(f"- 导入统计：{stats}")
        if stats.get("new_count") != 1:
            raise RuntimeError("导入新增统计不正确（期望 1）")
        if stats.get("skip_count") != 1:
            raise RuntimeError("导入跳过统计不正确（期望 1：包含 UNCHANGED 行）")
        if (
            int(stats.get("new_count", 0))
            + int(stats.get("update_count", 0))
            + int(stats.get("skip_count", 0))
            + int(stats.get("error_count", 0))
            != int(stats.get("total_rows", 0))
        ):
            raise RuntimeError(f"导入统计口径不闭合：{stats!r}")

        lines.append("")
        lines.append("## 4. 人员 Excel 预览：NEW/UPDATE/ERROR")
        excel_svc = ExcelService(backend=OpenpyxlBackend(), logger=None, op_logger=None)
        existing = op_svc.build_existing_for_excel()
        preview_ops = excel_svc.preview_import(
            rows=[
                {"工号": "OP001", "姓名": "张三(改)", "状态": "active", "备注": None},  # UPDATE
                {"工号": "OP002", "姓名": "李四", "状态": "inactive", "备注": "备注"},  # NEW
                {"工号": "OP003", "姓名": "", "状态": "active"},  # ERROR
            ],
            id_column="工号",
            existing_data=existing,
            validators=[validate_operator_row],
            mode=ImportMode.OVERWRITE,
        )
        st = [p.status.value for p in preview_ops]
        lines.append(f"- 预览状态序列：{st}")
        if st[0] != RowStatus.UPDATE.value or st[1] != RowStatus.NEW.value or st[2] != RowStatus.ERROR.value:
            raise RuntimeError("人员 Excel 预览状态不符合预期（UPDATE/NEW/ERROR）")

        lines.append("")
        lines.append("## 5. REPLACE 保护：存在批次引用时禁止清空人员")
        # 构造最小引用链：Parts -> Batches -> BatchOperations(operator_id)
        conn.execute("INSERT INTO Parts (part_no, part_name) VALUES (?, ?)", ("P001", "示例零件"))
        conn.execute("INSERT INTO Batches (batch_id, part_no, quantity, status) VALUES (?, ?, ?, ?)", ("B001", "P001", 1, "pending"))
        conn.execute(
            """
            INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name, source, machine_id, operator_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B001_01", "B001", 1, "数车", "internal", "MC001", "OP001", "pending"),
        )
        conn.commit()

        try:
            op_svc.ensure_replace_allowed()
            raise RuntimeError("期望 REPLACE 保护触发，但未触发")
        except AppError as e:
            lines.append(f"- 保护异常：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.OPERATOR_IN_USE:
                raise RuntimeError("REPLACE 保护错误码不正确（期望 OPERATOR_IN_USE）")

        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Phase3（人员管理模块）冒烟测试通过（CRUD/备注清空/关联预览与导入/Excel 预览/REPLACE 保护）。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = os.path.join(repo_root, "evidence", "Phase3", "smoke_phase3_report.md")
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
        lines.append("# Phase3（人员管理模块）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase3", "smoke_phase3_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

