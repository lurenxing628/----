import io
import json
import os
import re
import tempfile
import time
from datetime import date

from excel_preview_confirm_helpers import build_confirm_payload


def find_repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


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
    raw = raw.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return raw.strip()


def _extract_preview_baseline(html: str) -> str:
    m = re.search(r'<input[^>]*name=["\']preview_baseline["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
    if not m:
        raise RuntimeError("未能从预览页面提取 preview_baseline（确认导入需要该字段）")
    return m.group(1).strip()


def _assert_status(name: str, resp, expect_code: int = 200):
    if resp.status_code != expect_code:
        body = None
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = None
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500] if body else None}")


def main():
    repo_root = find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_gantt_one_job_")
    test_db = os.path.join(tmpdir, "aps_one_job.db")
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

    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    # 1) 设备/人员/人机
    machines_rows = [{"设备编号": "MC001", "设备名称": "CNC-01", "工种": None, "状态": "active"}]
    buf = _make_xlsx_bytes(["设备编号", "设备名称", "工种", "状态"], machines_rows)
    r = client.post("/equipment/excel/machines/preview", data={"mode": "overwrite", "file": (buf, "machines.xlsx")}, content_type="multipart/form-data")
    _assert_status("machines preview", r, 200)
    html_preview = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(html_preview)
    preview_baseline = _extract_preview_baseline(html_preview)
    r = client.post(
        "/equipment/excel/machines/confirm",
        data={"mode": "overwrite", "filename": "machines.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("machines confirm", r, 200)

    operators_rows = [{"工号": "OP001", "姓名": "张三", "状态": "active", "备注": "one_job"}]
    buf = _make_xlsx_bytes(["工号", "姓名", "状态", "备注"], operators_rows)
    r = client.post("/personnel/excel/operators/preview", data={"mode": "overwrite", "file": (buf, "operators.xlsx")}, content_type="multipart/form-data")
    _assert_status("operators preview", r, 200)
    html_preview = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(html_preview)
    preview_baseline = _extract_preview_baseline(html_preview)
    r = client.post(
        "/personnel/excel/operators/confirm",
        data={"mode": "overwrite", "filename": "operators.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("operators confirm", r, 200)

    links_rows = [{"工号": "OP001", "设备编号": "MC001"}]
    buf = _make_xlsx_bytes(["工号", "设备编号"], links_rows)
    r = client.post("/personnel/excel/links/preview", data={"mode": "overwrite", "file": (buf, "links.xlsx")}, content_type="multipart/form-data")
    _assert_status("links preview", r, 200)
    html_preview = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(html_preview)
    preview_baseline = _extract_preview_baseline(html_preview)
    r = client.post(
        "/personnel/excel/links/confirm",
        data={"mode": "overwrite", "filename": "links.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("links confirm", r, 200)

    # 2) 工艺：工种/供应商/路线（内部+外协）
    op_types_rows = [
        {"工种ID": "OT_IN", "工种名称": "数铣", "归属": "internal"},
        {"工种ID": "OT_EX", "工种名称": "标印", "归属": "external"},
    ]
    buf = _make_xlsx_bytes(["工种ID", "工种名称", "归属"], op_types_rows)
    r = client.post("/process/excel/op-types/preview", data={"mode": "overwrite", "file": (buf, "op_types.xlsx")}, content_type="multipart/form-data")
    _assert_status("op_types preview", r, 200)
    html_preview = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(html_preview)
    preview_baseline = _extract_preview_baseline(html_preview)
    r = client.post(
        "/process/excel/op-types/confirm",
        data={"mode": "overwrite", "filename": "op_types.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("op_types confirm", r, 200)

    suppliers_rows = [{"供应商ID": "S001", "名称": "外协-标印厂", "对应工种": "标印", "默认周期": 2, "状态": "active"}]
    buf = _make_xlsx_bytes(["供应商ID", "名称", "对应工种", "默认周期", "状态"], suppliers_rows)
    r = client.post("/process/excel/suppliers/preview", data={"mode": "overwrite", "file": (buf, "suppliers.xlsx")}, content_type="multipart/form-data")
    _assert_status("suppliers preview", r, 200)
    html_preview = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(html_preview)
    preview_baseline = _extract_preview_baseline(html_preview)
    r = client.post(
        "/process/excel/suppliers/confirm",
        data={"mode": "overwrite", "filename": "suppliers.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("suppliers confirm", r, 200)

    routes_rows = [{"图号": "A1234", "名称": "壳体-大", "工艺路线字符串": "5数铣35标印"}]
    buf = _make_xlsx_bytes(["图号", "名称", "工艺路线字符串"], routes_rows)
    r = client.post("/process/excel/routes/preview", data={"mode": "overwrite", "file": (buf, "routes.xlsx")}, content_type="multipart/form-data")
    _assert_status("routes preview", r, 200)
    html_preview = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(html_preview)
    preview_baseline = _extract_preview_baseline(html_preview)
    r = client.post(
        "/process/excel/routes/confirm",
        data={"mode": "overwrite", "filename": "routes.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("routes confirm", r, 200)

    # 3) 批次导入并自动生成工序
    batches_rows = [{"批次号": "B001", "图号": "A1234", "数量": 2, "交期": "2099-12-31", "优先级": "urgent", "齐套": "yes", "备注": "one_job"}]
    buf = _make_xlsx_bytes(["批次号", "图号", "数量", "交期", "优先级", "齐套", "备注"], batches_rows)
    r = client.post(
        "/scheduler/excel/batches/preview",
        data={"mode": "overwrite", "file": (buf, "batches.xlsx"), "auto_generate_ops": "1"},
        content_type="multipart/form-data",
    )
    _assert_status("batches preview", r, 200)
    html_batches_preview = r.data.decode("utf-8", errors="ignore")
    r = client.post(
        "/scheduler/excel/batches/confirm",
        data=build_confirm_payload(
            html_batches_preview,
            mode="overwrite",
            filename="batches.xlsx",
            context="/scheduler/excel/batches/preview",
            confirm_hidden_fields=["auto_generate_ops"],
        ),
        follow_redirects=True,
    )
    _assert_status("batches confirm", r, 200)
    if "导入被拒绝" in r.data.decode("utf-8", errors="ignore"):
        raise RuntimeError("batches confirm 被拒绝（页面提示“导入被拒绝”）")

    # 4) 补齐内部工序：确保有正工时（避免甘特过滤掉零时长任务）
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
            raise RuntimeError("未生成内部工序（B001/internal）")
        op_id = int(internal["id"])
        sh = float(internal["setup_hours"] or 0.0)
        uh = float(internal["unit_hours"] or 0.0)
        if (sh + uh * 2) <= 0:
            uh = 1.0
    finally:
        conn.close()
    r = client.post(f"/scheduler/ops/{op_id}/update", data={"machine_id": "MC001", "operator_id": "OP001", "setup_hours": str(sh), "unit_hours": str(uh)}, follow_redirects=True)
    _assert_status("update internal op", r, 200)

    # 5) 执行排产
    r = client.post("/scheduler/run", data={"batch_ids": ["B001"]}, follow_redirects=True)
    _assert_status("scheduler run", r, 200)

    # 6) 找到版本与排程起点
    conn = get_connection(test_db)
    conn.row_factory = None  # sqlite3.Row 由 get_connection 内部设置，这里只用 fetchone 索引也可
    conn = get_connection(test_db)
    try:
        hist = conn.execute("SELECT version FROM ScheduleHistory ORDER BY id DESC LIMIT 1").fetchone()
        if not hist:
            raise RuntimeError("未写入 ScheduleHistory")
        version = int(hist["version"])
        min_start = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (version,)).fetchone()["st"]
        max_end = conn.execute("SELECT MAX(end_time) AS et FROM Schedule WHERE version=?", (version,)).fetchone()["et"]
        week_start = str(min_start)[:10] if min_start else date.today().isoformat()
        week_end = str(max_end)[:10] if max_end else week_start
    finally:
        conn.close()

    # 7) 拉取甘特 tasks（machine 视图）
    r = client.get(f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={version}")
    _assert_status("gantt data", r, 200)
    payload = json.loads(r.data.decode("utf-8", errors="ignore") or "{}")
    if not payload.get("success"):
        raise RuntimeError(f"gantt data success=false: {payload}")
    data = payload.get("data") or {}
    tasks = data.get("tasks") or []
    if not isinstance(tasks, list) or not tasks:
        raise RuntimeError("甘特 tasks 为空")

    # 8) 报表断言（避免只校验页面 200）
    r = client.get(f"/reports/overdue?version={version}")
    _assert_status("reports overdue", r, 200)
    overdue_html = r.data.decode("utf-8", errors="ignore")
    if "当前无超期批次" not in overdue_html:
        raise RuntimeError("超期清单文案异常（期望“当前无超期批次”）")

    r = client.get(f"/reports/utilization?version={version}")
    _assert_status("reports utilization", r, 200)
    util_html = r.data.decode("utf-8", errors="ignore")
    if f'name="start_date" value="{week_start}"' not in util_html:
        raise RuntimeError("utilization 默认开始日期未按版本排程范围带入")
    if f'name="end_date" value="{week_end}"' not in util_html:
        raise RuntimeError("utilization 默认结束日期未按版本排程范围带入")
    if "已按所选版本的排程范围自动带入日期" not in util_html:
        raise RuntimeError("utilization 缺少“按版本排程范围”提示文案")
    if "MC001" not in util_html and "OP001" not in util_html:
        raise RuntimeError("utilization 未展示任何排程资源行（期望至少包含 MC001 或 OP001）")

    r = client.get(f"/reports/downtime?version={version}")
    _assert_status("reports downtime", r, 200)
    dt_html = r.data.decode("utf-8", errors="ignore")
    if f'name="start_date" value="{week_start}"' not in dt_html:
        raise RuntimeError("downtime 默认开始日期未按版本排程范围带入")
    if f'name="end_date" value="{week_end}"' not in dt_html:
        raise RuntimeError("downtime 默认结束日期未按版本排程范围带入")
    if "已按所选版本的排程范围自动带入日期" not in dt_html:
        raise RuntimeError("downtime 缺少“按版本排程范围”提示文案")

    out_dir = os.path.join(repo_root, "evidence", "FullE2E")
    os.makedirs(out_dir, exist_ok=True)
    tasks_path = os.path.join(out_dir, "gantt_tasks.json")
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump({"meta": {"version": version, "week_start": week_start}, "tasks": tasks}, f, ensure_ascii=False, indent=2)

    html_path = os.path.join(out_dir, "gantt_preview.html")
    # 注意：此 HTML 设计为“直接双击打开（file://）”即可看到图。
    # 相对路径：evidence/FullE2E/ -> ../../static/...
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>甘特图预览（version {version}）</title>
  <link rel="stylesheet" href="../../static/css/frappe-gantt.css"/>
  <style>
    body {{ font-family: -apple-system, Segoe UI, Arial, "Microsoft YaHei", sans-serif; margin: 16px; }}
    .meta {{ color: #666; margin: 8px 0 16px; }}
    .wrap {{ border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px; }}
    #gantt {{ overflow-x: auto; }}
    .hint {{ color: #999; font-size: 12px; margin-top: 8px; }}
  </style>
</head>
<body>
  <h2>甘特图预览（machine 视图）</h2>
  <div class="meta">
    <div>version：<b>{version}</b></div>
    <div>week_start：<b>{week_start}</b></div>
    <div>tasks：<b>{len(tasks)}</b></div>
  </div>
  <div class="wrap">
    <div id="gantt"></div>
  </div>
  <div class="hint">提示：这是从本次排产结果生成的 tasks；样式来自仓库内置 Frappe Gantt 0.6.1 资源。</div>

  <script src="../../static/js/frappe-gantt.min.js"></script>
  <script>
    const tasks = {json.dumps(tasks, ensure_ascii=False)};
    // Frappe Gantt 期望 start/end 为可被 Date.parse 的字符串（我们给的是 YYYY-MM-DD HH:MM:SS）
    const gantt = new Gantt("#gantt", tasks, {{
      view_mode: "Day",
      language: "zh",
    }});
  </script>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("OK")
    print(f"html={html_path}")
    print(f"tasks_json={tasks_path}")


if __name__ == "__main__":
    main()

