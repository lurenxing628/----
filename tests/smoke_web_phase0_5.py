import io
import json
import os
import re
import tempfile
import time
import traceback


def find_repo_root():
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    为了兼容不同目录结构：优先使用当前 tests/ 的上一级作为 repo_root，
    其次扫描 D:\\Github 下的子目录（沿用其它 smoke 脚本的约定）。
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


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _extract_raw_rows_json(html: str) -> str:
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从预览页面提取 raw_rows_json（确认导入需要该字段）")
    # textarea 里可能带有 HTML 转义，这里做最小反转义
    raw = m.group(1)
    raw = raw.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return raw.strip()


def _extract_preview_baseline(html: str) -> str:
    m = re.search(r'<input[^>]+name="preview_baseline"[^>]+value="([^"]*)"', html, re.S)
    if not m:
        return ""
    v = m.group(1)
    v = v.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return v.strip()


def _require_preview_baseline(html: str, context: str) -> str:
    preview_baseline = _extract_preview_baseline(html)
    if not preview_baseline:
        raise RuntimeError(f"{context} 预览页面缺少 preview_baseline")
    return preview_baseline


def _assert_status(lines, name: str, resp, expect_code: int = 200):
    lines.append(f"- {name}：{resp.status_code}")
    if resp.status_code != expect_code:
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}")


def _assert_xlsx(lines, name: str, resp):
    ct = resp.headers.get("Content-Type", "")
    lines.append(f"- {name}：{resp.status_code} content-type={ct}")
    if resp.status_code != 200:
        raise RuntimeError(f"{name} 返回非 200")
    if "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in ct:
        raise RuntimeError(f"{name} content-type 异常：{ct}")


def _query_recent_logs(conn, module: str, action: str, target_type: str, limit: int = 10):
    rows = conn.execute(
        """
        SELECT id, log_time, log_level, module, action, target_type, target_id, detail
        FROM OperationLogs
        WHERE module=? AND action=? AND target_type=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (module, action, target_type, limit),
    ).fetchall()
    return rows


def _parse_detail_json(detail: str) -> dict:
    try:
        return json.loads(detail) if detail else {}
    except Exception as e:
        raise RuntimeError(f"OperationLogs.detail 不是有效 JSON：{e} detail={detail!r}")


def _require_keys(d: dict, keys, context: str):
    missing = [k for k in keys if k not in d]
    if missing:
        raise RuntimeError(f"{context} 缺少键：{missing}（detail={d}）")


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase0~Phase5 Web + Excel 端到端冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{os.sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    # 临时目录（避免污染真实 db/logs/backups/templates_excel）
    tmpdir = tempfile.mkdtemp(prefix="aps_web_smoke_")
    test_db = os.path.join(tmpdir, "aps_web_smoke.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    # 确保可 import 项目模块
    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    # Flask test_client（不启动 server）
    import importlib

    app_mod = importlib.import_module("app")
    test_app = app_mod.create_app()
    client = test_app.test_client()

    lines.append("")
    lines.append("## 1. 基础页面可用性")
    _assert_status(lines, "GET /", client.get("/"), 200)
    _assert_status(lines, "GET /personnel/", client.get("/personnel/"), 200)
    _assert_status(lines, "GET /equipment/", client.get("/equipment/"), 200)
    _assert_status(lines, "GET /process/", client.get("/process/"), 200)

    # 统一用于校验留痕字段
    import_keys = [
        "filename",
        "mode",
        "time_cost_ms",
        "total_rows",
        "new_count",
        "update_count",
        "skip_count",
        "error_count",
        "errors_sample",
    ]
    export_keys = ["template_or_export_type", "filters", "row_count", "time_range", "time_cost_ms"]

    # =====================
    # 2) Equipment: Machines
    # =====================
    lines.append("")
    lines.append("## 2. 设备管理：设备信息 Excel（上传→预览→确认→导出）")

    _assert_xlsx(lines, "GET /equipment/excel/machines/template", client.get("/equipment/excel/machines/template"))

    machines_rows = [
        {"设备编号": "MC001", "设备名称": "CNC-01", "工种": None, "状态": "active"},
        {"设备编号": "MC002", "设备名称": "CNC-02", "工种": None, "状态": "maintain"},
        {"设备编号": "MC_BAD", "设备名称": "", "工种": None, "状态": "active"},  # ERROR：名称为空
    ]
    buf = _make_xlsx_bytes(["设备编号", "设备名称", "工种", "状态"], machines_rows)
    resp = client.post(
        "/equipment/excel/machines/preview",
        data={"mode": "overwrite", "file": (buf, "machines.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /equipment/excel/machines/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    if "导入预览" not in html:
        raise RuntimeError("设备 Excel 预览页面未包含“导入预览”")
    raw_rows_json = _extract_raw_rows_json(html)
    preview_baseline = _require_preview_baseline(html, "machines")

    resp2 = client.post(
        "/equipment/excel/machines/confirm",
        data={"mode": "overwrite", "filename": "machines.xlsx", "raw_rows_json": raw_rows_json, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /equipment/excel/machines/confirm", resp2, 200)

    # 严格模式：存在错误行时，确认导入应被拒绝（不写入任何设备）
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html2:
        raise RuntimeError("设备 Excel 确认导入未按严格模式拒绝（期望出现“导入被拒绝”提示）")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Machines WHERE machine_id IN ('MC001','MC002')").fetchone()[0]
        lines.append(f"- 严格拒绝校验：MC001/MC002 行数={cnt}（期望 0）")
        if cnt != 0:
            raise RuntimeError("严格拒绝失败：存在错误行时仍写入了 Machines 表")

        logs = _query_recent_logs(conn, module="equipment", action="import", target_type="machine", limit=10)
        lines.append(f"- OperationLogs 校验（equipment/import/machine）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("设备导入留痕缺失（OperationLogs equipment/import/machine）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, import_keys, "设备导入留痕(detail)")
        # 应包含错误样本（因为我们构造了 1 条 ERROR）
        if not isinstance(d.get("errors_sample"), list) or len(d.get("errors_sample")) < 1:
            raise RuntimeError("设备导入留痕 errors_sample 期望至少 1 条")
    finally:
        conn.close()

    # 再用“全合法”数据导入一次，应成功写入
    machines_rows_ok = [
        {"设备编号": "MC001", "设备名称": "CNC-01", "工种": None, "状态": "active"},
        {"设备编号": "MC002", "设备名称": "CNC-02", "工种": None, "状态": "maintain"},
    ]
    buf_ok = _make_xlsx_bytes(["设备编号", "设备名称", "工种", "状态"], machines_rows_ok)
    resp_ok = client.post(
        "/equipment/excel/machines/preview",
        data={"mode": "overwrite", "file": (buf_ok, "machines_ok.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /equipment/excel/machines/preview（valid）", resp_ok, 200)
    html_ok = resp_ok.data.decode("utf-8", errors="ignore")
    raw_rows_json_ok = _extract_raw_rows_json(html_ok)
    preview_baseline_ok = _require_preview_baseline(html_ok, "machines valid")
    resp_ok2 = client.post(
        "/equipment/excel/machines/confirm",
        data={"mode": "overwrite", "filename": "machines_ok.xlsx", "raw_rows_json": raw_rows_json_ok, "preview_baseline": preview_baseline_ok},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /equipment/excel/machines/confirm（valid）", resp_ok2, 200)

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Machines WHERE machine_id IN ('MC001','MC002')").fetchone()[0]
        lines.append(f"- Machines 写入校验：MC001/MC002 行数={cnt}（期望 2）")
        if cnt != 2:
            raise RuntimeError("设备确认导入未写入 Machines 表")
    finally:
        conn.close()

    _assert_xlsx(lines, "GET /equipment/excel/machines/export", client.get("/equipment/excel/machines/export"))
    conn = get_connection(test_db)
    try:
        logs = _query_recent_logs(conn, module="equipment", action="export", target_type="machine", limit=5)
        lines.append(f"- OperationLogs 校验（equipment/export/machine）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("设备导出留痕缺失（OperationLogs equipment/export/machine）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, export_keys, "设备导出留痕(detail)")
    finally:
        conn.close()

    # =====================
    # 3) Personnel: Operators
    # =====================
    lines.append("")
    lines.append("## 3. 人员管理：人员基本信息 Excel（上传→预览→确认→导出）")

    _assert_xlsx(lines, "GET /personnel/excel/operators/template", client.get("/personnel/excel/operators/template"))

    operators_rows = [
        {"工号": "OP100", "姓名": "测试员A", "状态": "active", "备注": "web_smoke"},
        {"工号": "OP101", "姓名": "测试员B", "状态": "inactive", "备注": None},
        {"工号": "OP_BAD", "姓名": "", "状态": "active", "备注": None},  # ERROR：姓名为空
    ]
    buf = _make_xlsx_bytes(["工号", "姓名", "状态", "备注"], operators_rows)
    resp = client.post(
        "/personnel/excel/operators/preview",
        data={"mode": "overwrite", "file": (buf, "operators.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /personnel/excel/operators/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    if "导入预览" not in html:
        raise RuntimeError("人员 Excel 预览页面未包含“导入预览”")
    raw_rows_json = _extract_raw_rows_json(html)
    preview_baseline = _require_preview_baseline(html, "operators")

    resp2 = client.post(
        "/personnel/excel/operators/confirm",
        data={"mode": "overwrite", "filename": "operators.xlsx", "raw_rows_json": raw_rows_json, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /personnel/excel/operators/confirm", resp2, 200)

    # 严格模式：存在错误行时，确认导入应被拒绝（不写入任何人员）
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html2:
        raise RuntimeError("人员 Excel 确认导入未按严格模式拒绝（期望出现“导入被拒绝”提示）")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Operators WHERE operator_id IN ('OP100','OP101')").fetchone()[0]
        lines.append(f"- 严格拒绝校验：OP100/OP101 行数={cnt}（期望 0）")
        if cnt != 0:
            raise RuntimeError("严格拒绝失败：存在错误行时仍写入了 Operators 表")

        logs = _query_recent_logs(conn, module="personnel", action="import", target_type="operator", limit=10)
        lines.append(f"- OperationLogs 校验（personnel/import/operator）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("人员导入留痕缺失（OperationLogs personnel/import/operator）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, import_keys, "人员导入留痕(detail)")
        if not isinstance(d.get("errors_sample"), list) or len(d.get("errors_sample")) < 1:
            raise RuntimeError("人员导入留痕 errors_sample 期望至少 1 条")
    finally:
        conn.close()

    # 再用“全合法”数据导入一次，应成功写入
    operators_rows_ok = [
        {"工号": "OP100", "姓名": "测试员A", "状态": "active", "备注": "web_smoke"},
        {"工号": "OP101", "姓名": "测试员B", "状态": "inactive", "备注": None},
    ]
    buf_ok = _make_xlsx_bytes(["工号", "姓名", "状态", "备注"], operators_rows_ok)
    resp_ok = client.post(
        "/personnel/excel/operators/preview",
        data={"mode": "overwrite", "file": (buf_ok, "operators_ok.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /personnel/excel/operators/preview（valid）", resp_ok, 200)
    html_ok = resp_ok.data.decode("utf-8", errors="ignore")
    raw_rows_json_ok = _extract_raw_rows_json(html_ok)
    preview_baseline_ok = _require_preview_baseline(html_ok, "operators valid")
    resp_ok2 = client.post(
        "/personnel/excel/operators/confirm",
        data={"mode": "overwrite", "filename": "operators_ok.xlsx", "raw_rows_json": raw_rows_json_ok, "preview_baseline": preview_baseline_ok},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /personnel/excel/operators/confirm（valid）", resp_ok2, 200)

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Operators WHERE operator_id IN ('OP100','OP101')").fetchone()[0]
        lines.append(f"- Operators 写入校验：OP100/OP101 行数={cnt}（期望 2）")
        if cnt != 2:
            raise RuntimeError("人员确认导入未写入 Operators 表")
    finally:
        conn.close()

    _assert_xlsx(lines, "GET /personnel/excel/operators/export", client.get("/personnel/excel/operators/export"))
    conn = get_connection(test_db)
    try:
        logs = _query_recent_logs(conn, module="personnel", action="export", target_type="operator", limit=5)
        lines.append(f"- OperationLogs 校验（personnel/export/operator）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("人员导出留痕缺失（OperationLogs personnel/export/operator）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, export_keys, "人员导出留痕(detail)")
    finally:
        conn.close()

    # =====================
    # 4) Personnel: Links
    # =====================
    lines.append("")
    lines.append("## 4. 人员管理：人员设备关联 Excel（上传→预览→确认→导出）")

    _assert_xlsx(lines, "GET /personnel/excel/links/template", client.get("/personnel/excel/links/template"))

    link_rows = [
        {"工号": "OP100", "设备编号": "MC001"},  # OK
        {"工号": "OP_NOT_EXIST", "设备编号": "MC001"},  # ERROR：人员不存在
    ]
    buf = _make_xlsx_bytes(["工号", "设备编号"], link_rows)
    resp = client.post(
        "/personnel/excel/links/preview",
        data={"mode": "overwrite", "file": (buf, "op_links.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /personnel/excel/links/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(html)
    preview_baseline = _require_preview_baseline(html, "personnel links")

    resp2 = client.post(
        "/personnel/excel/links/confirm",
        data={"mode": "overwrite", "filename": "op_links.xlsx", "raw_rows_json": raw_rows_json, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /personnel/excel/links/confirm", resp2, 200)

    # 严格模式：存在错误行时，确认导入应被拒绝（不写入任何关联）
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html2:
        raise RuntimeError("人员设备关联 Excel 确认导入未按严格模式拒绝（期望出现“导入被拒绝”提示）")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(1) FROM OperatorMachine WHERE operator_id='OP100' AND machine_id='MC001'"
        ).fetchone()[0]
        lines.append(f"- 严格拒绝校验：OP100-MC001 行数={cnt}（期望 0）")
        if cnt != 0:
            raise RuntimeError("严格拒绝失败：存在错误行时仍写入了 OperatorMachine 表")

        logs = _query_recent_logs(conn, module="personnel", action="import", target_type="operator_machine", limit=10)
        lines.append(f"- OperationLogs 校验（personnel/import/operator_machine）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("人员设备关联导入留痕缺失（OperationLogs personnel/import/operator_machine）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, ["filename", "mode", "time_cost_ms"], "人员设备关联导入留痕(detail)")
    finally:
        conn.close()

    # 再用“全合法”数据导入一次，应成功写入关联
    link_rows_ok = [
        {"工号": "OP100", "设备编号": "MC001"},  # OK
    ]
    buf_ok = _make_xlsx_bytes(["工号", "设备编号"], link_rows_ok)
    resp_ok = client.post(
        "/personnel/excel/links/preview",
        data={"mode": "overwrite", "file": (buf_ok, "op_links_ok.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /personnel/excel/links/preview（valid）", resp_ok, 200)
    html_ok = resp_ok.data.decode("utf-8", errors="ignore")
    raw_rows_json_ok = _extract_raw_rows_json(html_ok)
    preview_baseline_ok = _require_preview_baseline(html_ok, "personnel links valid")
    resp_ok2 = client.post(
        "/personnel/excel/links/confirm",
        data={"mode": "overwrite", "filename": "op_links_ok.xlsx", "raw_rows_json": raw_rows_json_ok, "preview_baseline": preview_baseline_ok},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /personnel/excel/links/confirm（valid）", resp_ok2, 200)

    conn = get_connection(test_db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(1) FROM OperatorMachine WHERE operator_id='OP100' AND machine_id='MC001'"
        ).fetchone()[0]
        lines.append(f"- OperatorMachine 写入校验：OP100-MC001 行数={cnt}（期望 1）")
        if cnt != 1:
            raise RuntimeError("人员设备关联确认导入未写入 OperatorMachine 表")
    finally:
        conn.close()

    _assert_xlsx(lines, "GET /personnel/excel/links/export", client.get("/personnel/excel/links/export"))

    # =====================
    # 5) Process: OpTypes / Suppliers / Routes / PartOps Export
    # =====================
    lines.append("")
    lines.append("## 5. 工艺管理：工种/供应商/工艺路线 Excel（上传→预览→确认→导出）")

    # 5.1 OpTypes
    _assert_xlsx(lines, "GET /process/excel/op-types/template", client.get("/process/excel/op-types/template"))
    op_type_rows = [
        {"工种ID": "OT_IN_1", "工种名称": "数铣", "归属": "internal"},
        {"工种ID": "OT_IN_2", "工种名称": "钳", "归属": "internal"},
        {"工种ID": "OT_IN_3", "工种名称": "数车", "归属": "internal"},
        {"工种ID": "OT_EX_1", "工种名称": "标印", "归属": "external"},
        {"工种ID": "OT_EX_2", "工种名称": "总检", "归属": "external"},
    ]
    buf = _make_xlsx_bytes(["工种ID", "工种名称", "归属"], op_type_rows)
    resp = client.post(
        "/process/excel/op-types/preview",
        data={"mode": "overwrite", "file": (buf, "op_types.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /process/excel/op-types/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(html)
    preview_baseline = _require_preview_baseline(html, "op_types")
    resp2 = client.post(
        "/process/excel/op-types/confirm",
        data={"mode": "overwrite", "filename": "op_types.xlsx", "raw_rows_json": raw_rows_json, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /process/excel/op-types/confirm", resp2, 200)

    # 5.2 Suppliers（依赖 OpTypes）
    _assert_xlsx(lines, "GET /process/excel/suppliers/template", client.get("/process/excel/suppliers/template"))
    supplier_rows = [
        {"供应商ID": "S001", "名称": "外协-标印厂", "对应工种": "标印", "默认周期": 0.5},
        {"供应商ID": "S002", "名称": "外协-总检厂", "对应工种": "总检", "默认周期": 1.0},
    ]
    buf = _make_xlsx_bytes(["供应商ID", "名称", "对应工种", "默认周期"], supplier_rows)
    resp = client.post(
        "/process/excel/suppliers/preview",
        data={"mode": "overwrite", "file": (buf, "suppliers.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /process/excel/suppliers/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(html)
    preview_baseline = _require_preview_baseline(html, "suppliers")
    resp2 = client.post(
        "/process/excel/suppliers/confirm",
        data={"mode": "overwrite", "filename": "suppliers.xlsx", "raw_rows_json": raw_rows_json, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /process/excel/suppliers/confirm", resp2, 200)

    # 5.3 Routes（导入后应触发解析并生成模板）
    _assert_xlsx(lines, "GET /process/excel/routes/template", client.get("/process/excel/routes/template"))
    route_rows = [
        {"图号": "A1234", "名称": "壳体-大", "工艺路线字符串": "5数铣10钳20数车35标印40总检"},
    ]
    buf = _make_xlsx_bytes(["图号", "名称", "工艺路线字符串"], route_rows)
    resp = client.post(
        "/process/excel/routes/preview",
        data={"mode": "overwrite", "file": (buf, "routes.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /process/excel/routes/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(html)
    preview_baseline = _require_preview_baseline(html, "routes")
    resp2 = client.post(
        "/process/excel/routes/confirm",
        data={"mode": "overwrite", "filename": "routes.xlsx", "raw_rows_json": raw_rows_json, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /process/excel/routes/confirm", resp2, 200)

    conn = get_connection(test_db)
    try:
        part_cnt = conn.execute("SELECT COUNT(1) FROM Parts WHERE part_no='A1234'").fetchone()[0]
        ops_cnt = conn.execute("SELECT COUNT(1) FROM PartOperations WHERE part_no='A1234' AND status='active'").fetchone()[0]
        grp_cnt = conn.execute("SELECT COUNT(1) FROM ExternalGroups WHERE part_no='A1234'").fetchone()[0]
        lines.append(f"- Parts/PartOperations/ExternalGroups 生成校验：parts={part_cnt} ops={ops_cnt} groups={grp_cnt}（期望 >=1）")
        if part_cnt < 1 or ops_cnt < 1 or grp_cnt < 1:
            raise RuntimeError("工艺路线导入后未生成模板（Parts/PartOperations/ExternalGroups）")

        # 抽样核对留痕字段（process/import/*）
        logs = _query_recent_logs(conn, module="process", action="import", target_type="part_route", limit=10)
        lines.append(f"- OperationLogs 校验（process/import/part_route）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("工艺路线导入留痕缺失（OperationLogs process/import/part_route）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, import_keys, "工艺路线导入留痕(detail)")
    finally:
        conn.close()

    # 5.4 Part operations export
    _assert_xlsx(lines, "GET /process/excel/part-operations/export", client.get("/process/excel/part-operations/export"))

    lines.append("")
    lines.append("## 结论")
    lines.append("- 通过：Phase0~Phase5 Web+Excel 关键链路端到端冒烟测试通过。")
    lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    report_path = os.path.join(repo_root, "evidence", "Phase0_to_Phase5", "web_smoke_report.md")
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
        lines.append("# Phase0~Phase5 Web + Excel 端到端冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase0_to_Phase5", "web_smoke_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

