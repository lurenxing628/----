import os
import tempfile
import time
import traceback


def find_repo_root():
    """
    约定：用户机器常见路径为 D:\\Github\\<项目>，且根目录包含 app.py 与 schema.sql。
    为了兼容本地/CI/不同目录结构，增加 fallback：使用当前 tests/ 的上一级作为 repo_root。
    """
    # 1) 优先：tests/ 的上一级目录（脚本与代码同仓库时最可靠）
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root

    # 2) 兼容：按既有约定扫描 D:\Github
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


def is_blank_value(value) -> bool:
    return value is None or str(value).strip() == ""


def validate_machine_row(row: dict, op_type_repo) -> str:
    """
    Excel 行校验（按文档列名）：
    - 设备编号、设备名称必填
    - 状态限定 active/inactive/maintain（允许中文：可用/停用/维修）
    - 工种允许填写 op_type_id 或 工种名称；不识别则报中文错误
    """
    if is_blank_value(row.get("设备编号")):
        return "“设备编号”不能为空"
    if is_blank_value(row.get("设备名称")):
        return "“设备名称”不能为空"

    status = row.get("状态")
    if status is None or str(status).strip() == "":
        return "“状态”不能为空（允许：active / inactive / maintain）"
    status = str(status).strip()
    if status in ("可用", "启用", "正常"):
        status = "active"
    elif status in ("停用", "禁用", "不可用"):
        status = "inactive"
    elif status in ("维修", "维护", "维护中", "维修中", "保养"):
        status = "maintain"
    from core.models.enums import MACHINE_STATUS_VALUES

    if status not in MACHINE_STATUS_VALUES:
        return "“状态”不合法（允许：active / inactive / maintain；或中文：可用/停用/维修）"
    row["状态"] = status

    ot_value = row.get("工种")
    if ot_value is None or str(ot_value).strip() == "":
        return None
    ot_value = str(ot_value).strip()
    ot = op_type_repo.get(ot_value) or op_type_repo.get_by_name(ot_value)
    if not ot:
        return f"工种“{ot_value}”不存在，请先维护工种配置。"
    # 标准化为名称（便于差异对比）
    row["工种"] = ot.name
    return None


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase4（设备管理模块）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{os.sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase4_")
    test_db = os.path.join(tmpdir, "aps_phase4_test.db")
    lines.append("")
    lines.append("## 0. 测试环境")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import AppError, ErrorCode
    from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
    from core.services.common.openpyxl_backend import OpenpyxlBackend
    from core.services.equipment import MachineDowntimeService, MachineService
    from core.services.personnel import OperatorMachineService
    from data.repositories import OpTypeRepository

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
        lines.append("")
        lines.append("## 1. Schema 检查（Phase4 相关表）")
        for t in ["Machines", "MachineDowntimes", "OperatorMachine", "OpTypes", "BatchOperations", "Batches", "Parts", "Operators"]:
            lines.append(f"- 是否存在 {t}：{t in tables}")

        # 准备 OpTypes（Machines 外键依赖）
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT001", "数车", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT002", "数铣", "internal"))
        conn.commit()

        lines.append("")
        lines.append("## 2. 设备服务：创建/更新/清空字段（中文校验）")
        m_svc = MachineService(conn)
        m = m_svc.create(machine_id="MC001", name="CNC-01", op_type_id="OT001", status="active", remark="测试备注")
        if m.machine_id != "MC001":
            raise RuntimeError("MachineService.create 校验失败：未创建 MC001")

        # 清空备注与工种（验证 repo.update 支持 NULL）
        m_svc.update(machine_id="MC001", remark="", op_type_id="")
        got = m_svc.get("MC001")
        lines.append(f"- 清空后：remark={got.remark!r} op_type_id={got.op_type_id!r}（期望均为 None）")
        if got.remark is not None or got.op_type_id is not None:
            raise RuntimeError("字段清空失败：期望 remark/op_type_id 为 None")

        # 非法状态校验（中文）
        try:
            m_svc.create(machine_id="MC_BAD", name="坏数据", status="BAD")
            raise RuntimeError("期望触发状态校验失败，但未触发")
        except AppError as e:
            lines.append(f"- 非法状态异常：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.VALIDATION_ERROR:
                raise RuntimeError("非法状态未翻译为 VALIDATION_ERROR")

        lines.append("")
        lines.append("## 3. 设备-人员关联：新增/查询（双向一致底层表）")
        # 准备人员
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP002", "李四", "inactive"))
        conn.commit()

        link_svc = OperatorMachineService(conn)
        link_svc.add_link("OP001", "MC001")
        links_by_machine = link_svc.list_by_machine("MC001")
        lines.append(f"- MC001 关联数量：{len(links_by_machine)}（期望 1）")
        if len(links_by_machine) != 1:
            raise RuntimeError("设备侧关联新增失败：期望 1 条")

        lines.append("")
        lines.append("## 4. 设备 Excel 预览：NEW/UPDATE/ERROR（含工种识别）")
        op_type_repo = OpTypeRepository(conn)
        existing = m_svc.build_existing_for_excel()
        excel_svc = ExcelService(backend=OpenpyxlBackend(), logger=None, op_logger=None)

        preview = excel_svc.preview_import(
            rows=[
                {"设备编号": "MC001", "设备名称": "CNC-01(改)", "工种": "数车", "状态": "可用"},  # UPDATE
                {"设备编号": "MC002", "设备名称": "CNC-02", "工种": "OT002", "状态": "maintain"},  # NEW（工种用ID）
                {"设备编号": "MC003", "设备名称": "CNC-03", "工种": "不存在工种", "状态": "active"},  # ERROR（工种）
                {"设备编号": "MC004", "设备名称": "", "工种": "数车", "状态": "active"},  # ERROR（名称）
                {"设备编号": "MC005", "设备名称": "CNC-05", "工种": "数车", "状态": "BAD"},  # ERROR（状态）
            ],
            id_column="设备编号",
            existing_data=existing,
            validators=[lambda r: validate_machine_row(r, op_type_repo=op_type_repo)],
            mode=ImportMode.OVERWRITE,
        )
        st = [p.status.value for p in preview]
        lines.append(f"- 预览状态序列：{st}")
        if st[0] != RowStatus.UPDATE.value or st[1] != RowStatus.NEW.value:
            raise RuntimeError("设备 Excel 预览状态不符合预期（UPDATE/NEW）")
        if st[2] != RowStatus.ERROR.value or st[3] != RowStatus.ERROR.value or st[4] != RowStatus.ERROR.value:
            raise RuntimeError("设备 Excel 预览错误行状态不正确（期望 ERROR）")

        lines.append("")
        lines.append("## 5. REPLACE 保护：存在批次引用时禁止清空设备")
        # 构造最小引用链：Parts -> Batches -> BatchOperations(machine_id)
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
            m_svc.ensure_replace_allowed()
            raise RuntimeError("期望 REPLACE 保护触发，但未触发")
        except AppError as e:
            lines.append(f"- 保护异常：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.MACHINE_IN_USE:
                raise RuntimeError("REPLACE 保护错误码不正确（期望 MACHINE_IN_USE）")

        lines.append("")
        lines.append("## 6. 设备停机计划：新增/重叠校验/取消")
        dt_svc = MachineDowntimeService(conn)
        d1 = dt_svc.create(machine_id="MC001", start_time="2026-01-22 08:00", end_time="2026-01-22 12:00", reason_code="maintenance")
        lines.append(f"- 新增停机：id={d1.id} machine={d1.machine_id} {d1.start_time}~{d1.end_time} reason={d1.reason_code}")
        if not d1.id:
            raise RuntimeError("新增停机失败：未返回 id")

        # 重叠区间应报错（复用 SCHEDULE_CONFLICT 码）
        try:
            dt_svc.create(machine_id="MC001", start_time="2026-01-22 11:00", end_time="2026-01-22 13:00", reason_code="breakdown")
            raise RuntimeError("期望停机时间段重叠报错，但未报错")
        except AppError as e:
            lines.append(f"- 重叠校验：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.SCHEDULE_CONFLICT:
                raise RuntimeError("停机重叠错误码不正确（期望 SCHEDULE_CONFLICT）")

        # 取消后允许再次添加同一时间段
        dt_svc.cancel(d1.id, machine_id="MC001")
        d2 = dt_svc.create(machine_id="MC001", start_time="2026-01-22 08:00", end_time="2026-01-22 12:00", reason_code="maintenance")
        lines.append(f"- 取消后重建停机：id={d2.id}（期望成功）")

        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Phase4（设备管理模块）冒烟测试通过（CRUD/字段清空/关联/Excel 预览/REPLACE 保护/停机计划）。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = os.path.join(repo_root, "evidence", "Phase4", "smoke_phase4_report.md")
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
        lines.append("# Phase4（设备管理模块）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase4", "smoke_phase4_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

