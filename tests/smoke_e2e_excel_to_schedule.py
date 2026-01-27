import io
import json
import os
import re
import tempfile
import time
import traceback
from datetime import date


def find_repo_root():
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    兼容不同目录结构：优先 tests/ 上一级，其次扫描 D:\\Github 下子目录。
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
    raw = m.group(1)
    # textarea 里可能带有 HTML 转义，这里做最小反转义
    raw = raw.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return raw.strip()


def _assert_status(lines, name: str, resp, expect_code: int = 200):
    lines.append(f"- {name}：{resp.status_code}")
    if resp.status_code != expect_code:
        body = None
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = None
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500] if body else None}")


def _assert_xlsx(lines, name: str, resp):
    ct = resp.headers.get("Content-Type", "")
    lines.append(f"- {name}：{resp.status_code} content-type={ct}")
    if resp.status_code != 200:
        raise RuntimeError(f"{name} 返回非 200")
    if "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in ct:
        raise RuntimeError(f"{name} content-type 异常：{ct}")


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
    lines.append("# Full E2E（从 Excel 导入开始→排产→甘特/周计划→系统管理）验收报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{os.sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    # 临时目录（避免污染真实 db/logs/backups/templates_excel）
    tmpdir = tempfile.mkdtemp(prefix="aps_full_e2e_")
    test_db = os.path.join(tmpdir, "aps_full_e2e.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    lines.append("")
    lines.append("## 0. 测试环境（隔离目录）")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")
    lines.append(f"- logs：`{test_logs}`")
    lines.append(f"- backups：`{test_backups}`")
    lines.append(f"- templates_excel：`{test_templates}`")

    # 隔离：让 app.create_app() 读取测试 DB/目录
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

    # 留痕字段键名约束（来自开发文档/系统速查表）
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

    failed = False
    try:
        lines.append("")
        lines.append("## 1. 基础页面可访问性（用于确认路由装配）")
        _assert_status(lines, "GET /", client.get("/"), 200)
        _assert_status(lines, "GET /personnel/", client.get("/personnel/"), 200)
        _assert_status(lines, "GET /equipment/", client.get("/equipment/"), 200)
        _assert_status(lines, "GET /process/", client.get("/process/"), 200)
        _assert_status(lines, "GET /scheduler/", client.get("/scheduler/"), 200)
        _assert_status(lines, "GET /system/backup", client.get("/system/backup"), 200)

        # ============================================================
        # 2) Excel 导入：设备
        # ============================================================
        lines.append("")
        lines.append("## 2. Excel：设备信息（导入→导出→留痕）")
        _assert_xlsx(lines, "GET /equipment/excel/machines/template", client.get("/equipment/excel/machines/template"))
        machines_rows = [
            {"设备编号": "MC001", "设备名称": "CNC-01", "工种": None, "状态": "active"},
            {"设备编号": "MC002", "设备名称": "CNC-02", "工种": None, "状态": "active"},
        ]
        buf = _make_xlsx_bytes(["设备编号", "设备名称", "工种", "状态"], machines_rows)
        resp = client.post(
            "/equipment/excel/machines/preview",
            data={"mode": "overwrite", "file": (buf, "machines.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /equipment/excel/machines/preview", resp, 200)
        html = resp.data.decode("utf-8", errors="ignore")
        raw_rows_json = _extract_raw_rows_json(html)
        resp2 = client.post(
            "/equipment/excel/machines/confirm",
            data={"mode": "overwrite", "filename": "machines.xlsx", "raw_rows_json": raw_rows_json},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /equipment/excel/machines/confirm", resp2, 200)
        _assert_xlsx(lines, "GET /equipment/excel/machines/export", client.get("/equipment/excel/machines/export"))

        # ============================================================
        # 3) Excel 导入：人员 + 人员设备关联
        # ============================================================
        lines.append("")
        lines.append("## 3. Excel：人员基本信息 + 人员设备关联（导入→导出→留痕）")
        _assert_xlsx(lines, "GET /personnel/excel/operators/template", client.get("/personnel/excel/operators/template"))
        operators_rows = [
            {"工号": "OP001", "姓名": "张三", "状态": "active", "备注": "e2e"},
            {"工号": "OP002", "姓名": "李四", "状态": "active", "备注": None},
        ]
        buf = _make_xlsx_bytes(["工号", "姓名", "状态", "备注"], operators_rows)
        resp = client.post(
            "/personnel/excel/operators/preview",
            data={"mode": "overwrite", "file": (buf, "operators.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /personnel/excel/operators/preview", resp, 200)
        raw_rows_json = _extract_raw_rows_json(resp.data.decode("utf-8", errors="ignore"))
        resp2 = client.post(
            "/personnel/excel/operators/confirm",
            data={"mode": "overwrite", "filename": "operators.xlsx", "raw_rows_json": raw_rows_json},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /personnel/excel/operators/confirm", resp2, 200)
        _assert_xlsx(lines, "GET /personnel/excel/operators/export", client.get("/personnel/excel/operators/export"))

        _assert_xlsx(lines, "GET /personnel/excel/links/template", client.get("/personnel/excel/links/template"))
        links_rows = [
            {"工号": "OP001", "设备编号": "MC001"},
            {"工号": "OP001", "设备编号": "MC002"},
        ]
        buf = _make_xlsx_bytes(["工号", "设备编号"], links_rows)
        resp = client.post(
            "/personnel/excel/links/preview",
            data={"mode": "overwrite", "file": (buf, "links.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /personnel/excel/links/preview", resp, 200)
        raw_rows_json = _extract_raw_rows_json(resp.data.decode("utf-8", errors="ignore"))
        resp2 = client.post(
            "/personnel/excel/links/confirm",
            data={"mode": "overwrite", "filename": "links.xlsx", "raw_rows_json": raw_rows_json},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /personnel/excel/links/confirm", resp2, 200)
        _assert_xlsx(lines, "GET /personnel/excel/links/export", client.get("/personnel/excel/links/export"))

        # ============================================================
        # 4) Excel 导入：工艺（工种/供应商/零件工艺路线）
        # ============================================================
        lines.append("")
        lines.append("## 4. Excel：工种/供应商/零件工艺路线（导入→生成模板→留痕）")
        _assert_xlsx(lines, "GET /process/excel/op-types/template", client.get("/process/excel/op-types/template"))
        op_types_rows = [
            {"工种ID": "OT_IN", "工种名称": "数铣", "归属": "internal"},
            {"工种ID": "OT_EX", "工种名称": "标印", "归属": "external"},
        ]
        buf = _make_xlsx_bytes(["工种ID", "工种名称", "归属"], op_types_rows)
        resp = client.post(
            "/process/excel/op-types/preview",
            data={"mode": "overwrite", "file": (buf, "op_types.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /process/excel/op-types/preview", resp, 200)
        raw_rows_json = _extract_raw_rows_json(resp.data.decode("utf-8", errors="ignore"))
        resp2 = client.post(
            "/process/excel/op-types/confirm",
            data={"mode": "overwrite", "filename": "op_types.xlsx", "raw_rows_json": raw_rows_json},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /process/excel/op-types/confirm", resp2, 200)

        _assert_xlsx(lines, "GET /process/excel/suppliers/template", client.get("/process/excel/suppliers/template"))
        suppliers_rows = [
            {"供应商ID": "S001", "名称": "外协-标印厂", "对应工种": "标印", "默认周期": 2, "状态": "active"},
        ]
        buf = _make_xlsx_bytes(["供应商ID", "名称", "对应工种", "默认周期", "状态"], suppliers_rows)
        resp = client.post(
            "/process/excel/suppliers/preview",
            data={"mode": "overwrite", "file": (buf, "suppliers.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /process/excel/suppliers/preview", resp, 200)
        raw_rows_json = _extract_raw_rows_json(resp.data.decode("utf-8", errors="ignore"))
        resp2 = client.post(
            "/process/excel/suppliers/confirm",
            data={"mode": "overwrite", "filename": "suppliers.xlsx", "raw_rows_json": raw_rows_json},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /process/excel/suppliers/confirm", resp2, 200)

        _assert_xlsx(lines, "GET /process/excel/routes/template", client.get("/process/excel/routes/template"))
        # 路线：内部 + 外部（用于后续批次生成外部工序）
        routes_rows = [
            {"图号": "A1234", "名称": "壳体-大", "工艺路线字符串": "5数铣35标印"},
        ]
        buf = _make_xlsx_bytes(["图号", "名称", "工艺路线字符串"], routes_rows)
        resp = client.post(
            "/process/excel/routes/preview",
            data={"mode": "overwrite", "file": (buf, "routes.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /process/excel/routes/preview", resp, 200)
        raw_rows_json = _extract_raw_rows_json(resp.data.decode("utf-8", errors="ignore"))
        resp2 = client.post(
            "/process/excel/routes/confirm",
            data={"mode": "overwrite", "filename": "routes.xlsx", "raw_rows_json": raw_rows_json},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /process/excel/routes/confirm", resp2, 200)
        _assert_xlsx(lines, "GET /process/excel/part-operations/export", client.get("/process/excel/part-operations/export"))

        # ============================================================
        # 5) Excel 导入：批次（并从模板生成工序）
        # ============================================================
        lines.append("")
        lines.append("## 5. Excel：批次信息（导入→自动生成工序→留痕）")
        _assert_xlsx(lines, "GET /scheduler/excel/batches/template", client.get("/scheduler/excel/batches/template"))
        batches_rows = [
            {"批次号": "B001", "图号": "A1234", "数量": 2, "交期": "2099-12-31", "优先级": "urgent", "齐套": "yes", "备注": "e2e"},
        ]
        buf = _make_xlsx_bytes(["批次号", "图号", "数量", "交期", "优先级", "齐套", "备注"], batches_rows)
        resp = client.post(
            "/scheduler/excel/batches/preview",
            data={"mode": "overwrite", "file": (buf, "batches.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /scheduler/excel/batches/preview", resp, 200)
        raw_rows_json = _extract_raw_rows_json(resp.data.decode("utf-8", errors="ignore"))
        resp2 = client.post(
            "/scheduler/excel/batches/confirm",
            data={"mode": "overwrite", "filename": "batches.xlsx", "raw_rows_json": raw_rows_json, "auto_generate_ops": "1"},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /scheduler/excel/batches/confirm", resp2, 200)

        # ============================================================
        # 6) Excel 导入：工作日历（确保可导入/留痕；排产本身允许无配置兜底）
        # ============================================================
        lines.append("")
        lines.append("## 6. Excel：工作日历（导入→导出→留痕）")
        _assert_xlsx(lines, "GET /scheduler/excel/calendar/template", client.get("/scheduler/excel/calendar/template"))
        today = date.today().isoformat()
        calendar_rows = [
            {"日期": today, "类型": "workday", "可用工时": 8, "效率": 1.0, "允许普通件": "yes", "允许急件": "yes", "说明": "e2e"},
        ]
        buf = _make_xlsx_bytes(["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"], calendar_rows)
        resp = client.post(
            "/scheduler/excel/calendar/preview",
            data={"mode": "overwrite", "file": (buf, "calendar.xlsx")},
            content_type="multipart/form-data",
        )
        _assert_status(lines, "POST /scheduler/excel/calendar/preview", resp, 200)
        raw_rows_json = _extract_raw_rows_json(resp.data.decode("utf-8", errors="ignore"))
        resp2 = client.post(
            "/scheduler/excel/calendar/confirm",
            data={"mode": "overwrite", "filename": "calendar.xlsx", "raw_rows_json": raw_rows_json},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /scheduler/excel/calendar/confirm", resp2, 200)
        _assert_xlsx(lines, "GET /scheduler/excel/calendar/export", client.get("/scheduler/excel/calendar/export"))

        # ============================================================
        # 7) 补齐批次工序（内部：人机+工时；外部：周期兜底）
        # ============================================================
        lines.append("")
        lines.append("## 7. 批次工序补齐（确保排产可跑：内部人机匹配 + 外部周期）")
        conn = get_connection(test_db)
        try:
            internal = conn.execute(
                """
                SELECT id, op_code, setup_hours, unit_hours
                FROM BatchOperations
                WHERE batch_id='B001' AND source='internal'
                ORDER BY seq
                LIMIT 1
                """
            ).fetchone()
            if not internal:
                raise RuntimeError("未生成内部工序（期望 batch_id=B001 至少 1 条 internal）")
            op_id = int(internal["id"])
            op_code = internal["op_code"]
            sh = float(internal["setup_hours"] or 0.0)
            uh = float(internal["unit_hours"] or 0.0)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # 兜底：若模板工时均为 0，会导致甘特图过滤掉“零时长任务”（start==end）。
        # 为了让端到端验收包含“内部工序甘特任务”，这里确保内部工序至少有正工时。
        if (sh + uh * 2) <= 0:  # quantity=2（见批次Excel导入）
            uh = 1.0

        _assert_status(lines, "GET /scheduler/batches/B001", client.get("/scheduler/batches/B001"), 200)
        resp = client.post(
            f"/scheduler/ops/{op_id}/update",
            data={"machine_id": "MC001", "operator_id": "OP001", "setup_hours": str(sh), "unit_hours": str(uh)},
            follow_redirects=True,
        )
        _assert_status(lines, f"POST /scheduler/ops/{op_id}/update（{op_code}）", resp, 200)

        # 外部工序：若 ext_days 为空则补 1 天（使用路由保存一次）
        conn = get_connection(test_db)
        try:
            ext = conn.execute(
                """
                SELECT id, op_code, supplier_id, ext_days
                FROM BatchOperations
                WHERE batch_id='B001' AND source='external'
                ORDER BY seq
                LIMIT 1
                """
            ).fetchone()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if ext:
            ext_id = int(ext["id"])
            ext_code = ext["op_code"]
            sup_id = ext["supplier_id"] or "S001"
            ext_days = ext["ext_days"]
            # 兜底：空/非正数 都补 1 天，避免算法把外协任务判为无效
            try:
                ext_days_f = float(ext_days) if ext_days is not None and str(ext_days).strip() != "" else None
            except Exception:
                ext_days_f = None
            if ext_days_f is None or ext_days_f <= 0:
                ext_days_f = 1.0
            resp = client.post(
                f"/scheduler/ops/{ext_id}/update",
                data={"supplier_id": sup_id, "ext_days": str(ext_days_f)},
                follow_redirects=True,
            )
            _assert_status(lines, f"POST /scheduler/ops/{ext_id}/update（{ext_code} 外部）", resp, 200)

        # ============================================================
        # 8) 执行排产（从页面入口 /scheduler/run）
        # ============================================================
        lines.append("")
        lines.append("## 8. 执行排产（/scheduler/run）→ 查询 Schedule/ScheduleHistory/OperationLogs")
        resp = client.post("/scheduler/run", data={"batch_ids": ["B001"]}, follow_redirects=True)
        _assert_status(lines, "POST /scheduler/run (follow redirects)", resp, 200)

        conn = get_connection(test_db)
        try:
            hist = conn.execute("SELECT version, strategy, result_status, result_summary FROM ScheduleHistory ORDER BY id DESC LIMIT 1").fetchone()
            if not hist:
                raise RuntimeError("未写入 ScheduleHistory（期望排产后至少 1 条）")
            version = int(hist["version"])
            lines.append(f"- ScheduleHistory：version={version} strategy={hist['strategy']} result_status={hist['result_status']}")
            rs = _parse_detail_json(hist["result_summary"])
            _require_keys(rs, ["version", "strategy", "strategy_params", "selected_batch_ids", "counts", "overdue_batches", "time_cost_ms"], "ScheduleHistory.result_summary")

            sch_cnt = conn.execute("SELECT COUNT(1) AS c FROM Schedule WHERE version=?", (version,)).fetchone()["c"]
            lines.append(f"- Schedule 行数：{sch_cnt}（version={version}，期望 >=1）")
            if int(sch_cnt) < 1:
                raise RuntimeError("Schedule 未落库（期望 version 对应行数>=1）")

            # 用排程起始时间定位“正确的周”（避免周末/非工作时间导致任务被推迟到下周，从而甘特图本周无任务）
            min_start = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (version,)).fetchone()["st"]
            if not min_start:
                raise RuntimeError("Schedule 无 start_time（无法计算 week_start）")
            schedule_week_start = str(min_start)[:10]
            lines.append(f"- 甘特周起点（按排程起始时间）：{schedule_week_start}")

            # 批次状态应更新为 scheduled（本用例应能全部排到）
            b = conn.execute("SELECT status FROM Batches WHERE batch_id='B001'").fetchone()
            if not b:
                raise RuntimeError("Batches 未找到 B001")
            lines.append(f"- Batches.status：{b['status']}（期望 scheduled）")
            if (b["status"] or "").strip() != "scheduled":
                raise RuntimeError(f"B001 状态未变为 scheduled：{b['status']!r}")

            # 排产操作留痕（OperationLogs action=schedule）
            log_row = conn.execute(
                """
                SELECT id, detail
                FROM OperationLogs
                WHERE module='scheduler' AND action='schedule' AND target_type='schedule'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            if not log_row:
                raise RuntimeError("未找到排产操作留痕（OperationLogs scheduler/schedule/schedule）")
            detail = _parse_detail_json(log_row["detail"])
            _require_keys(
                detail,
                ["version", "strategy", "batch_ids", "batch_count", "op_count", "scheduled_ops", "failed_ops", "result_status", "time_cost_ms"],
                "OperationLogs scheduler/schedule detail",
            )
            lines.append(f"- OperationLogs（schedule）：log_id={log_row['id']} keys_ok")
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # ============================================================
        # 9) 甘特图与周计划（接口 + 导出）
        # ============================================================
        lines.append("")
        lines.append("## 9. 甘特图与周计划（/scheduler/gantt/data + /scheduler/week-plan/export）")
        week_start = schedule_week_start
        # 防御：非法 version 参数不应导致 500
        resp = client.get(f"/scheduler/gantt?view=machine&week_start={week_start}&version=abc")
        _assert_status(lines, "GET /scheduler/gantt?version=abc", resp, 400)
        resp = client.get(f"/scheduler/gantt/data?view=machine&week_start={week_start}&version=abc")
        _assert_status(lines, "GET /scheduler/gantt/data?version=abc", resp, 400)
        payload_bad = json.loads(resp.data.decode("utf-8", errors="ignore") or "{}")
        if payload_bad.get("success") is not False:
            raise RuntimeError(f"甘特图数据接口（非法 version）期望 success=false：{payload_bad}")
        err_bad = payload_bad.get("error") or {}
        if str(err_bad.get("code") or "") != "1001":
            raise RuntimeError(f"甘特图数据接口（非法 version）期望 error.code=1001：{payload_bad}")
        resp = client.get(f"/scheduler/week-plan?week_start={week_start}&version=abc")
        _assert_status(lines, "GET /scheduler/week-plan?version=abc", resp, 400)
        resp = client.get(f"/scheduler/week-plan/export?week_start={week_start}&version=abc")
        _assert_status(lines, "GET /scheduler/week-plan/export?version=abc", resp, 302)
        loc = resp.headers.get("Location", "") or ""
        lines.append(f"- week-plan/export invalid version redirect：{loc}")
        if "/scheduler/week-plan" not in loc:
            raise RuntimeError(f"周计划导出（非法 version）重定向异常：Location={loc!r}")

        resp = client.get(f"/scheduler/gantt?view=machine&week_start={week_start}&version={version}")
        _assert_status(lines, "GET /scheduler/gantt", resp, 200)
        resp = client.get(f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={version}")
        _assert_status(lines, "GET /scheduler/gantt/data", resp, 200)
        payload = json.loads(resp.data.decode("utf-8", errors="ignore") or "{}")
        if not payload.get("success"):
            raise RuntimeError(f"甘特图数据接口返回失败：{payload}")
        data = payload.get("data") or {}
        tasks = data.get("tasks") or []
        if not isinstance(tasks, list) or not tasks:
            raise RuntimeError("甘特图 tasks 为空（期望至少 1 条）")
        for k in ["id", "name", "start", "end", "progress", "dependencies", "custom_class"]:
            if k not in tasks[0]:
                raise RuntimeError(f"甘特图任务缺少字段：{k} task0={tasks[0]}")
        lines.append(f"- 甘特图 tasks：{len(tasks)} 条（字段齐全）")

        exp = client.get(f"/scheduler/week-plan/export?week_start={week_start}&version={version}")
        _assert_xlsx(lines, "GET /scheduler/week-plan/export", exp)

        # ============================================================
        # 10) 系统管理抽检：日志/历史页可访问
        # ============================================================
        lines.append("")
        lines.append("## 10. 系统管理抽检（logs/history/backup 页面可访问）")
        _assert_status(lines, "GET /system/logs", client.get("/system/logs"), 200)
        _assert_status(lines, f"GET /system/history?version={version}", client.get(f"/system/history?version={version}"), 200)
        _assert_status(lines, "GET /system/backup", client.get("/system/backup"), 200)

        # ============================================================
        # 10.A) 报表中心：页面可访问
        # ============================================================
        lines.append("")
        lines.append("## 10.A 报表中心抽检（页面可访问）")
        _assert_status(lines, "GET /reports/", client.get("/reports/"), 200)
        _assert_status(lines, "GET /reports/overdue", client.get(f"/reports/overdue?version={version}"), 200)
        _assert_status(
            lines,
            "GET /reports/utilization",
            client.get(f"/reports/utilization?version={version}&start_date={week_start}&end_date={week_start}"),
            200,
        )
        _assert_status(
            lines,
            "GET /reports/downtime",
            client.get(f"/reports/downtime?version={version}&start_date={week_start}&end_date={week_start}"),
            200,
        )

        # ============================================================
        # 10.X) 物料模块 MVP：物料主数据 + 批次物料需求 + 齐套回写
        # ============================================================
        lines.append("")
        lines.append("## 10.X 物料模块 MVP（物料→批次需求→齐套回写）")
        _assert_status(lines, "GET /material/materials", client.get("/material/materials"), 200)

        # 取一个已有批次用于验证回写（避免依赖固定批次号）
        conn = get_connection(test_db)
        try:
            row = conn.execute("SELECT batch_id FROM Batches ORDER BY batch_id LIMIT 1").fetchone()
            if not row:
                raise RuntimeError("缺少批次数据用于物料模块验证")
            bid = row["batch_id"]
        finally:
            conn.close()
        lines.append(f"- 选取批次：{bid}")

        # 新增物料
        resp = client.post(
            "/material/materials/create",
            data={"material_id": "MAT_E2E", "name": "测试物料", "spec": "E2E", "unit": "kg", "stock_qty": "0", "status": "active"},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /material/materials/create (follow redirects)", resp, 200)

        # 新增批次物料需求：先不齐套（available < required）
        resp = client.post(
            f"/material/batches/{bid}/requirements/add",
            data={"material_id": "MAT_E2E", "required_qty": "10", "available_qty": "0"},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /material/batches/<bid>/requirements/add (follow redirects)", resp, 200)

        conn = get_connection(test_db)
        try:
            st = conn.execute("SELECT ready_status, ready_date FROM Batches WHERE batch_id=?", (bid,)).fetchone()
            if not st:
                raise RuntimeError("批次不存在（用于物料验证）")
            lines.append(f"- 加入物料需求后批次齐套：{st['ready_status']} ready_date={st['ready_date']}")
            if st["ready_status"] not in ("no", "partial"):
                raise RuntimeError(f"物料未齐套时批次 ready_status 异常：{st['ready_status']}")

            bm = conn.execute(
                "SELECT id FROM BatchMaterials WHERE batch_id=? AND material_id=? ORDER BY id DESC LIMIT 1",
                (bid, "MAT_E2E"),
            ).fetchone()
            if not bm:
                raise RuntimeError("未生成 BatchMaterials 记录")
            bm_id = int(bm["id"])
        finally:
            conn.close()

        # 更新到料：使其齐套（available >= required），应回写批次 ready_status=yes 且 ready_date 非空
        resp = client.post(
            f"/material/requirements/{bm_id}/update",
            data={"batch_id": bid, "required_qty": "10", "available_qty": "10"},
            follow_redirects=True,
        )
        _assert_status(lines, "POST /material/requirements/<id>/update (follow redirects)", resp, 200)

        conn = get_connection(test_db)
        try:
            st2 = conn.execute("SELECT ready_status, ready_date FROM Batches WHERE batch_id=?", (bid,)).fetchone()
            lines.append(f"- 齐套后批次齐套：{st2['ready_status']} ready_date={st2['ready_date']}")
            if st2["ready_status"] != "yes":
                raise RuntimeError(f"物料齐套后批次 ready_status 异常：{st2['ready_status']}")
            if not st2["ready_date"]:
                raise RuntimeError("物料齐套后批次 ready_date 为空（期望写入）")
        finally:
            conn.close()

        # ============================================================
        # 11) 留痕抽检：关键 Excel 导入/导出 是否按文档键名写 detail
        # ============================================================
        lines.append("")
        lines.append("## 11. 留痕抽检（OperationLogs.detail 键名对齐开发文档）")
        conn = get_connection(test_db)
        try:
            checks = [
                ("equipment", "import", "machine", import_keys),
                ("equipment", "export", "machine", export_keys),
                ("personnel", "import", "operator", import_keys),
                ("personnel", "export", "operator", export_keys),
                ("personnel", "import", "operator_machine", import_keys),
                ("process", "import", "op_type", import_keys),
                ("process", "import", "supplier", import_keys),
                ("process", "import", "part_route", import_keys),
                ("scheduler", "import", "batch", import_keys),
                ("scheduler", "import", "calendar", import_keys),
                ("scheduler", "export", "calendar", export_keys),
            ]
            for module, action, target_type, keys in checks:
                row = conn.execute(
                    """
                    SELECT id, detail
                    FROM OperationLogs
                    WHERE module=? AND action=? AND target_type=?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (module, action, target_type),
                ).fetchone()
                if not row:
                    raise RuntimeError(f"缺少 OperationLogs：{module}/{action}/{target_type}")
                d = _parse_detail_json(row["detail"])
                _require_keys(d, keys, f"OperationLogs {module}/{action}/{target_type}")
            lines.append("- OperationLogs 抽检：通过（import/export/schedule 关键键名齐全）")
        finally:
            try:
                conn.close()
            except Exception:
                pass

        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Full E2E（从 Excel 导入开始→排产→甘特/周计划→系统管理）链路跑通。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    except Exception as e:
        failed = True
        lines.append("")
        lines.append("## 结论")
        lines.append(f"- 不通过：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

    report_path = os.path.join(repo_root, "evidence", "FullE2E", "excel_to_schedule_report.md")
    write_report(report_path, lines)
    if failed:
        print("FAILED")
    else:
        print("OK")
    print(report_path)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

