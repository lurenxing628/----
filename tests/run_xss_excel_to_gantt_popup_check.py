import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from html import unescape as html_unescape
from typing import Any, Dict, List, Optional

from excel_preview_confirm_helpers import build_confirm_payload

XSS = "<img src=x onerror=alert(1)>"
 
 
def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("repo root not found (need app.py + schema.sql)")
 
 
def _make_xlsx_bytes(headers, rows):
    import openpyxl
 
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None

    ws.title = "Sheet1"
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
 
 
def _extract_raw_rows_json(html: str) -> str:
    """
    Preview 页会把 raw_rows_json 放进 <textarea>。浏览器提交表单时会发送 textarea 的“实际 value”，
    因此这里必须做 HTML entity 反转义来模拟浏览器行为（避免把 &lt; 当作字面量导入）。
    """
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("raw_rows_json not found in preview html")
    return html_unescape(m.group(1)).strip()
 

def _extract_preview_baseline(html: str) -> str:
    m = re.search(r'<input[^>]+name="preview_baseline"[^>]+value="([^"]*)"', html, re.S)
    if not m:
        return ""
    return html_unescape(m.group(1)).strip()

 
def _assert_status(name: str, resp, expect_code: int = 200):
    if resp.status_code != expect_code:
        body = None
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = None
        raise RuntimeError(f"{name} -> {resp.status_code} (want {expect_code}) body={body[:800] if body else None}")
 
 
def _excel_preview_confirm(
    client,
    *,
    base: str,
    filename: str,
    mode: str,
    buf,
    preview_extra: Optional[Dict[str, Any]] = None,
    confirm_extra: Optional[Dict[str, Any]] = None,
    confirm_hidden_fields: Optional[List[str]] = None,
):
    preview_data = {"mode": mode, "file": (buf, filename)}
    if preview_extra:
        preview_data.update(preview_extra)
    r = client.post(
        f"{base}/preview",
        data=preview_data,
        content_type="multipart/form-data",
    )
    _assert_status(f"{base}/preview", r, 200)
    html = r.data.decode("utf-8", errors="ignore")
    r2 = client.post(
        f"{base}/confirm",
        data=build_confirm_payload(
            html,
            mode=mode,
            filename=filename,
            context=f"{base}/preview",
            confirm_extra=confirm_extra,
            confirm_hidden_fields=confirm_hidden_fields,
        ),
        follow_redirects=True,
    )
    _assert_status(f"{base}/confirm", r2, 200)
    html2 = r2.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" in html2:
        raise RuntimeError(f"{base}/confirm 被拒绝（页面提示“导入被拒绝”）")
 
 
def _run_node_check(*, repo_root: str, hit_task_path: str) -> Dict[str, Any]:
    gantt_core_js = os.path.join(repo_root, "static", "js", "gantt.js")
    gantt_render_js = os.path.join(repo_root, "static", "js", "gantt_render.js")
    if not os.path.exists(gantt_core_js):
        raise RuntimeError(f"missing {gantt_core_js}")
    if not os.path.exists(gantt_render_js):
        raise RuntimeError(f"missing {gantt_render_js}")
 
    node_code = r"""
const fs = require("fs");
 
const corePath = String(process.env.APS_GANTT_JS || "");
const renderPath = String(process.env.APS_GANTT_RENDER_JS || "");
const taskPath = String(process.env.APS_HIT_TASK_JSON || "");
const xss = String(process.env.APS_XSS || "");
 
if (!corePath || !renderPath || !taskPath) {
  console.error("missing env APS_GANTT_JS/APS_GANTT_RENDER_JS/APS_HIT_TASK_JSON");
  process.exit(2);
}
 
const code = fs.readFileSync(corePath, "utf8") + "\n" + fs.readFileSync(renderPath, "utf8");
const task = JSON.parse(fs.readFileSync(taskPath, "utf8"));
 
function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractNamedFunction(fnName) {
  // We only need small helpers (str/escapeHtml). Regex literals like /[&<>"']/ contain
  // quotes that break a naive brace scanner, so here we use a simpler regex extraction.
  const name = escapeRe(fnName);
  const re = new RegExp(
    "function\\s+" + name + "\\s*\\([^)]*\\)\\s*\\{[\\s\\S]*?\\n\\s*\\}",
    "m"
  );
  const m = re.exec(code);
  if (!m) throw new Error(`cannot extract function ${fnName}`);
  return m[0];
}
 
function extractCustomPopupFunction() {
  const re = /custom_popup_html\s*:\s*function\s*\(\s*task\s*\)\s*\{/m;
  const m = re.exec(code);
  if (!m) throw new Error("cannot find custom_popup_html function");
  const start = m.index + m[0].indexOf("function");
  const braceStart = code.indexOf("{", start);
  if (braceStart < 0) throw new Error("cannot find { for custom_popup_html");
 
  let depth = 0;
  let inS = false, inD = false, inT = false, inLine = false, inBlock = false, esc = false;
  for (let i = braceStart; i < code.length; i++) {
    const ch = code[i];
    const nx = code[i + 1];
 
    if (inLine) {
      if (ch === "\n") inLine = false;
      continue;
    }
    if (inBlock) {
      if (ch === "*" && nx === "/") { inBlock = false; i++; }
      continue;
    }
    if (inS) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === "'") { inS = false; continue; }
      continue;
    }
    if (inD) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === "\"") { inD = false; continue; }
      continue;
    }
    if (inT) {
      // Treat entire template string as opaque; braces inside do not affect outer function braces.
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === "`") { inT = false; continue; }
      continue;
    }
 
    // enter comment/string
    if (ch === "/" && nx === "/") { inLine = true; i++; continue; }
    if (ch === "/" && nx === "*") { inBlock = true; i++; continue; }
    if (ch === "'") { inS = true; continue; }
    if (ch === "\"") { inD = true; continue; }
    if (ch === "`") { inT = true; continue; }
 
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        return code.slice(start, i + 1);
      }
    }
  }
  throw new Error("cannot extract custom_popup_html function");
}
 
// Extract + eval functions from gantt modules (to ensure we test the real implementation)
const strSrc = extractNamedFunction("str");
const escapeSrc = extractNamedFunction("escapeHtml");
const popupSrc = extractCustomPopupFunction(); // function(task){...}
 
eval(strSrc);
eval(escapeSrc);
 
function norm(v) { return str(v).trim(); }
function statusKeyForTask(_task) { return "pending"; }
const state = { ccIdSet: new Set() };
 
const customPopup = (eval("(" + popupSrc + ")"));
 
// Simulate buildRenderTasks behavior
const t2 = JSON.parse(JSON.stringify(task));
if (!t2.meta) t2.meta = {};
const rawName = str(t2.name || "");
t2.meta._raw_name = rawName;
t2.name = escapeHtml(rawName);
 
const htmlOut = String(customPopup(t2) || "");
 
const hasRawImg = /<\s*img\b/i.test(htmlOut);
const hasEscapedImg = /&lt;\s*img\b/i.test(htmlOut);
 
const result = {
  ok: (!hasRawImg) && hasEscapedImg,
  hasRawImg,
  hasEscapedImg,
  escapeHtml_xss: escapeHtml(xss),
  popupSample: htmlOut.slice(0, 600),
};
 
process.stdout.write(JSON.stringify(result));
"""
 
    env = dict(os.environ)
    env["APS_GANTT_JS"] = gantt_core_js
    env["APS_GANTT_RENDER_JS"] = gantt_render_js
    env["APS_HIT_TASK_JSON"] = hit_task_path
    env["APS_XSS"] = XSS
 
    p = subprocess.run(
        ["node", "-"],
        input=node_code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if p.returncode != 0:
        raise RuntimeError(f"node check failed: rc={p.returncode} stderr={p.stderr[:800]!r}")
    try:
        return json.loads(p.stdout or "{}")
    except Exception as e:
        raise RuntimeError(f"node output not json: {e} stdout={p.stdout[:800]!r}")
 
 
def main():
    repo_root = find_repo_root()
 
    tmpdir = tempfile.mkdtemp(prefix="aps_xss_popup_")
    test_db = os.path.join(tmpdir, "aps_xss.db")
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
 
    sys.path.insert(0, repo_root)
 
    from core.infrastructure.database import ensure_schema, get_connection
 
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
 
    import importlib
 
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()
 
    # 1) Machines: machine name injection (设备名)
    _excel_preview_confirm(
        client,
        base="/equipment/excel/machines",
        filename="machines.xlsx",
        mode="overwrite",
        buf=_make_xlsx_bytes(
            ["设备编号", "设备名称", "工种", "状态"],
            [{"设备编号": "MC001", "设备名称": XSS, "工种": None, "状态": "active"}],
        ),
    )
 
    # 2) Operators + links
    _excel_preview_confirm(
        client,
        base="/personnel/excel/operators",
        filename="operators.xlsx",
        mode="overwrite",
        buf=_make_xlsx_bytes(["工号", "姓名", "状态", "备注"], [{"工号": "OP001", "姓名": "张三", "状态": "active", "备注": "xss"}]),
    )
    _excel_preview_confirm(
        client,
        base="/personnel/excel/links",
        filename="links.xlsx",
        mode="overwrite",
        buf=_make_xlsx_bytes(["工号", "设备编号"], [{"工号": "OP001", "设备编号": "MC001"}]),
    )
 
    # 3) Op types + routes: part_no injection (图号)
    _excel_preview_confirm(
        client,
        base="/process/excel/op-types",
        filename="op_types.xlsx",
        mode="overwrite",
        buf=_make_xlsx_bytes(["工种ID", "工种名称", "归属"], [{"工种ID": "OT_IN", "工种名称": "数铣", "归属": "internal"}]),
    )
    _excel_preview_confirm(
        client,
        base="/process/excel/routes",
        filename="routes.xlsx",
        mode="overwrite",
        buf=_make_xlsx_bytes(["图号", "名称", "工艺路线字符串"], [{"图号": XSS, "名称": "XSS_PART", "工艺路线字符串": "5数铣"}]),
    )
 
    # 4) Batches: batch_id injection (批次号) + auto generate ops
    _excel_preview_confirm(
        client,
        base="/scheduler/excel/batches",
        filename="batches.xlsx",
        mode="overwrite",
        buf=_make_xlsx_bytes(
            ["批次号", "图号", "数量", "交期", "优先级", "齐套", "备注"],
            [{"批次号": XSS, "图号": XSS, "数量": 1, "交期": "2099-12-31", "优先级": "urgent", "齐套": "yes", "备注": "xss"}],
        ),
        preview_extra={"auto_generate_ops": "1"},
        confirm_hidden_fields=["auto_generate_ops"],
    )
 
    # 5) Ensure at least one internal op has positive duration and assigned machine/operator
    conn = get_connection(test_db)
    try:
        internal = conn.execute(
            """
            SELECT id, setup_hours, unit_hours
            FROM BatchOperations
            WHERE batch_id=? AND source='internal'
            ORDER BY seq
            LIMIT 1
            """,
            (XSS,),
        ).fetchone()
        if not internal:
            raise RuntimeError("no internal op created for XSS batch")
        op_id = int(internal["id"])
        sh = float(internal["setup_hours"] or 0.0)
        uh = float(internal["unit_hours"] or 0.0)
        if (sh + uh) <= 0:
            uh = 1.0
    finally:
        conn.close()
 
    r = client.post(
        f"/scheduler/ops/{op_id}/update",
        data={"machine_id": "MC001", "operator_id": "OP001", "setup_hours": str(sh), "unit_hours": str(uh)},
        follow_redirects=True,
    )
    _assert_status("ops update", r, 200)
 
    # 6) Run schedule
    r = client.post("/scheduler/run", data={"batch_ids": [XSS]}, follow_redirects=True)
    _assert_status("scheduler run", r, 200)
 
    # 7) Read version + week_start
    conn = get_connection(test_db)
    try:
        hist = conn.execute("SELECT version FROM ScheduleHistory ORDER BY id DESC LIMIT 1").fetchone()
        if not hist:
            raise RuntimeError("missing ScheduleHistory")
        version = int(hist["version"])
        min_start = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (version,)).fetchone()["st"]
        week_start = str(min_start)[:10] if min_start else date.today().isoformat()
    finally:
        conn.close()
 
    # 8) Fetch gantt tasks (machine view)
    r = client.get(f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={version}")
    _assert_status("gantt data", r, 200)
    payload = json.loads(r.data.decode("utf-8", errors="ignore") or "{}")
    if not payload.get("success"):
        raise RuntimeError(f"gantt data success=false: {payload}")
    tasks = (payload.get("data") or {}).get("tasks") or []
    if not tasks:
        raise RuntimeError("gantt tasks empty")
 
    hit = None
    for t in tasks:
        meta = (t or {}).get("meta") or {}
        if meta.get("batch_id") == XSS or meta.get("part_no") == XSS or meta.get("machine") == XSS:
            hit = t
            break
    if not hit:
        for t in tasks:
            if XSS in str((t or {}).get("name") or ""):
                hit = t
                break
    if not hit:
        raise RuntimeError("no task contains XSS fields (unexpected)")
 
    hit_path = os.path.join(tmpdir, "hit_task.json")
    with open(hit_path, "w", encoding="utf-8") as f:
        json.dump(hit, f, ensure_ascii=False, indent=2, default=str)
 
    js_check = _run_node_check(repo_root=repo_root, hit_task_path=hit_path)
 
    ok = bool(js_check.get("ok"))
    if not ok:
        raise RuntimeError(f"XSS check failed: {js_check}")
 
    # Print evidence for humans
    out_path = os.path.join(tmpdir, "gantt_tasks_xss_machine.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"meta": {"tmpdir": tmpdir, "db": test_db, "version": version, "week_start": week_start, "xss": XSS}, "hit": hit, "tasks": tasks},
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
 
    print("PASS")
    print(f"tmpdir={tmpdir}")
    print(f"tasks_json={out_path}")
    print(f"node_check={json.dumps(js_check, ensure_ascii=False)}")
 
 
if __name__ == "__main__":
    main()
