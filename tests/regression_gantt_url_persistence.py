"""回归测试：甘特图前端 gantt_ui.js 的 applyUiFromUrl/persistUiToUrl 契约——gantt_zoom/color/batch/resource/overdue/external/deps/hcc 等 URL 参数应正确读入 state.ui、映射 Frappe view mode 并回写控件与查询表单；持久化时清理默认值与旧 gantt_vm，且按当前/跨视角同步范围链接；同时校验 /scheduler/gantt 页面 HTML 含必要控件标记。"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _load_gantt_dom_helpers(repo_root: str):
    helper_path = os.path.join(repo_root, "tests", "regression_gantt_critical_outline_sync.py")
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _assert_js_url_contract(repo_root: str) -> None:
    helpers = _load_gantt_dom_helpers(repo_root)
    node_code = f"""
{helpers.DOM_SHIM_JS}

function makeControl(tag, id, value) {{
  const el = document.createElement(tag);
  el.setAttribute("id", id);
  el.value = value || "";
  el.options = [];
  document.body.appendChild(el);
  return el;
}}

function makeHidden(form, name, value) {{
  const el = document.createElement("input");
  el.setAttribute("type", "hidden");
  el.setAttribute("name", name);
  el.value = value || "";
  form.appendChild(el);
  return el;
}}

function formValue(form, name) {{
  const inputs = form.querySelectorAll("input");
  for (let index = 0; index < inputs.length; index += 1) {{
    if (inputs[index].getAttribute("name") === name) return inputs[index].value;
  }}
  return null;
}}

function queryValue(href, name) {{
  return new URL(href, window.location.origin).searchParams.get(name);
}}

makeControl("select", "ganttZoomLevel", "day");
makeControl("select", "ganttColorMode", "batch");
makeControl("select", "ganttFilterBatch", "");
makeControl("select", "ganttFilterResource", "");
makeControl("input", "ganttOnlyOverdue", "");
makeControl("input", "ganttOnlyExternal", "");
makeControl("select", "ganttDepsMode", "critical");
makeControl("input", "ganttHighlightCC", "").checked = true;
makeControl("input", "ganttZoomFormValue", "day");
createHost("ganttZoomWarning");
const rangeForm = document.createElement("form");
rangeForm.setAttribute("class", "aps-gantt-range-form");
makeHidden(rangeForm, "gantt_batch", "OLD");
makeHidden(rangeForm, "gantt_resource", "OLD-M");
document.body.appendChild(rangeForm);
const link = document.createElement("a");
link.setAttribute("href", "/scheduler/gantt?view=operator&version=1");
document.body.appendChild(link);
const machineLink = document.createElement("a");
machineLink.setAttribute("href", "/scheduler/gantt?view=machine&version=1&gantt_batch=OLD&gantt_resource=OLD-M");
document.body.appendChild(machineLink);
const operatorLink = document.createElement("a");
operatorLink.setAttribute("href", "/scheduler/gantt?view=operator&version=1&gantt_batch=OLD&gantt_resource=OLD-M");
document.body.appendChild(operatorLink);
const operatorSameLink = document.createElement("a");
operatorSameLink.setAttribute("href", "/scheduler/gantt?view=operator&version=1&gantt_batch=OLD&gantt_resource=OLD-O");
document.body.appendChild(operatorSameLink);
const machineOtherLink = document.createElement("a");
machineOtherLink.setAttribute("href", "/scheduler/gantt?view=machine&version=1&gantt_batch=OLD&gantt_resource=OLD-O");
document.body.appendChild(machineOtherLink);

window.location.href = "http://local.test/scheduler/gantt?gantt_zoom=fifteen-minute&gantt_color=status&gantt_batch=B001&gantt_resource=MC01&gantt_overdue=1&gantt_external=1&gantt_deps=process&gantt_hcc=0";
window.history = {{
  replaceState: function (_state, _title, url) {{
    window.location.href = String(url);
  }},
}};

loadScript({json.dumps(os.path.join(repo_root, "static", "js", "gantt.js"))});
window.__APS_GANTT__.safeDecorateDynamic = function () {{}};
window.__APS_GANTT__.render = function () {{}};
loadScript({json.dumps(os.path.join(repo_root, "static", "js", "gantt_zoom.js"))});
loadScript({json.dumps(os.path.join(repo_root, "static", "js", "gantt_ui.js"))});

const ns = window.__APS_GANTT__;
ns.state.cfg = {{ view: "machine" }};
ns.applyUiFromUrl();
ns.readUi();
const fromNewUrl = {{
  zoomControl: document.getElementById("ganttZoomLevel").value,
  zoomLevel: ns.state.ui.zoomLevel,
  viewMode: ns.state.ui.viewMode,
  color: ns.state.ui.colorMode,
  batch: ns.state.ui.filterBatch,
  resource: ns.state.ui.filterResource,
  hiddenZoom: document.getElementById("ganttZoomFormValue").value,
  linkHref: link.getAttribute("href"),
  overdue: ns.state.ui.onlyOverdue,
  external: ns.state.ui.onlyExternal,
  deps: ns.state.ui.depsMode,
  hcc: ns.state.ui.highlightCC,
}};

ns.persistUiToUrl();
const persisted = window.location.href;

document.getElementById("ganttFilterBatch").value = "B002";
document.getElementById("ganttFilterResource").value = "MC02";
ns.readUi();
ns.persistUiToUrl();
const scopeLinks = {{
  machineBatch: queryValue(machineLink.getAttribute("href"), "gantt_batch"),
  machineResource: queryValue(machineLink.getAttribute("href"), "gantt_resource"),
  operatorBatch: queryValue(operatorLink.getAttribute("href"), "gantt_batch"),
  operatorResource: queryValue(operatorLink.getAttribute("href"), "gantt_resource"),
  formBatch: formValue(rangeForm, "gantt_batch"),
  formResource: formValue(rangeForm, "gantt_resource"),
}};

ns.state.cfg = {{ view: "operator" }};
document.getElementById("ganttFilterBatch").value = "B003";
document.getElementById("ganttFilterResource").value = "OP02";
ns.readUi();
ns.persistUiToUrl();
const operatorScopeLinks = {{
  operatorBatch: queryValue(operatorSameLink.getAttribute("href"), "gantt_batch"),
  operatorResource: queryValue(operatorSameLink.getAttribute("href"), "gantt_resource"),
  machineBatch: queryValue(machineOtherLink.getAttribute("href"), "gantt_batch"),
  machineResource: queryValue(machineOtherLink.getAttribute("href"), "gantt_resource"),
}};

window.location.href = "http://local.test/scheduler/gantt?gantt_vm=Week";
document.getElementById("ganttZoomLevel").value = "day";
ns.applyUiFromUrl();
ns.readUi();
const legacyWeek = {{ zoomLevel: ns.state.ui.zoomLevel, viewMode: ns.state.ui.viewMode }};

window.location.href = "http://local.test/scheduler/gantt?gantt_zoom=bad-value";
document.getElementById("ganttZoomLevel").value = "one-minute";
ns.applyUiFromUrl();
ns.readUi();
ns.persistUiToUrl();
ns.render();
const invalid = {{
  zoomLevel: ns.state.ui.zoomLevel,
  warning: document.getElementById("ganttZoomWarning").textContent || "",
}};

window.location.href = "http://local.test/scheduler/gantt";
ns.state.ui.zoomLevel = "five-minute";
document.getElementById("ganttZoomLevel").value = "day";
ns.applyUiFromUrl();
ns.readUi();
const fromDataState = {{
  zoomControl: document.getElementById("ganttZoomLevel").value,
  zoomLevel: ns.state.ui.zoomLevel,
  viewMode: ns.state.ui.viewMode,
}};

process.stdout.write(JSON.stringify({{ fromNewUrl, persisted, scopeLinks, operatorScopeLinks, legacyWeek, invalid, fromDataState }}));
"""
    result = helpers._run_node_json(node_code)
    _assert_true(result["fromNewUrl"]["zoomControl"] == "fifteen-minute", "gantt_zoom 没有写入缩放控件")
    _assert_true(result["fromNewUrl"]["zoomLevel"] == "fifteen-minute", "gantt_zoom 没有进入 state.ui.zoomLevel")
    _assert_true(result["fromNewUrl"]["viewMode"] == "Fifteen Minute", "gantt_zoom 没有映射到 Frappe view mode")
    _assert_true(result["fromNewUrl"]["color"] == "status", "gantt_color 没有进入 state")
    _assert_true(result["fromNewUrl"]["batch"] == "B001", "gantt_batch 没有进入 state")
    _assert_true(result["fromNewUrl"]["resource"] == "MC01", "gantt_resource 没有进入 state")
    _assert_true(result["fromNewUrl"]["hiddenZoom"] == "fifteen-minute", "查询表单没有同步 gantt_zoom")
    _assert_true(
        "gantt_zoom=fifteen-minute" in result["fromNewUrl"]["linkHref"],
        "设备/人员视图链接没有同步 gantt_zoom",
    )
    _assert_true(result["fromNewUrl"]["overdue"] is True, "gantt_overdue 没有进入 state")
    _assert_true(result["fromNewUrl"]["external"] is True, "gantt_external 没有进入 state")
    _assert_true(result["fromNewUrl"]["deps"] == "process", "gantt_deps 没有进入 state")
    _assert_true(result["fromNewUrl"]["hcc"] is False, "gantt_hcc 没有进入 state")
    _assert_true("gantt_zoom=fifteen-minute" in result["persisted"], "persistUiToUrl 没有保留新 zoom")
    _assert_true("gantt_vm=" not in result["persisted"], "persistUiToUrl 没有清理旧 gantt_vm")
    _assert_true(result["scopeLinks"]["machineBatch"] == "B002", "同视角链接没有同步新 gantt_batch")
    _assert_true(result["scopeLinks"]["machineResource"] == "MC02", "同视角链接没有同步新 gantt_resource")
    _assert_true(result["scopeLinks"]["operatorBatch"] == "B002", "跨视角链接没有同步新 gantt_batch")
    _assert_true(result["scopeLinks"]["operatorResource"] is None, "跨视角链接没有删除旧 gantt_resource")
    _assert_true(result["scopeLinks"]["formBatch"] == "B002", "加载表单没有同步新 gantt_batch")
    _assert_true(result["scopeLinks"]["formResource"] == "MC02", "加载表单没有同步新 gantt_resource")
    _assert_true(result["operatorScopeLinks"]["operatorBatch"] == "B003", "人员同视角链接没有同步新 gantt_batch")
    _assert_true(result["operatorScopeLinks"]["operatorResource"] == "OP02", "人员同视角链接没有同步新 gantt_resource")
    _assert_true(result["operatorScopeLinks"]["machineBatch"] == "B003", "人员跨设备视角链接没有同步新 gantt_batch")
    _assert_true(result["operatorScopeLinks"]["machineResource"] is None, "人员跨设备视角链接没有删除旧 gantt_resource")
    _assert_true(result["legacyWeek"]["zoomLevel"] == "week", "旧 gantt_vm=Week 没有兼容到 week")
    _assert_true(result["legacyWeek"]["viewMode"] == "Week", "旧 gantt_vm=Week 没有兼容到 Frappe Week")
    _assert_true(result["invalid"]["zoomLevel"] == "day", "非法 gantt_zoom 没有回到 day")
    _assert_true("无法识别" in result["invalid"]["warning"], "非法 gantt_zoom 真实启动后没有保留提示")
    _assert_true(result["fromDataState"]["zoomControl"] == "five-minute", "无 URL 参数时没有把 data/state zoom 写回控件")
    _assert_true(result["fromDataState"]["zoomLevel"] == "five-minute", "无 URL 参数时 state zoom 被控件默认值覆盖")


def test_gantt_url_persistence_contract(tmp_path, monkeypatch) -> None:
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH))
    with sqlite3.connect(str(test_db)) as conn:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "regression", 0, 0, "success", "{}", "regression"),
        )
        conn.commit()

    sys.modules.pop("app", None)
    app = importlib.import_module("app").create_app()
    client = app.test_client()
    # 页面 HTML 只校验前端契约（URL 参数回显由 JS 实现）
    resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=1")
    _assert_true(resp.status_code == 200, f"GET /scheduler/gantt 返回 {resp.status_code}")
    html = resp.data.decode("utf-8", errors="ignore")
    _assert_true('id="ganttZoomLevel"' in html, "缺少 ganttZoomLevel 控件")
    _assert_true('id="ganttZoomFormValue"' in html, "缺少用于加载表单延续 gantt_zoom 的隐藏字段")
    _assert_true('id="ganttZoomWarning"' in html, "缺少 ganttZoomWarning 提示")
    _assert_true('data-gantt-mode="view"' in html, "缺少甘特图查看模式标记")
    _assert_true('data-zoom-level="' in html, "缺少甘特图缩放等级标记")
    _assert_true('id="ganttColorMode"' in html, "缺少 ganttColorMode 控件")
    _assert_true('id="ganttFilterBatch"' in html, "缺少 ganttFilterBatch 控件")

    ui_js_path = os.path.join(repo_root, "static", "js", "gantt_ui.js")
    with open(ui_js_path, "r", encoding="utf-8") as f:
        src = f.read()

    for needle in (
        "function applyUiFromUrl()",
        "function persistUiToUrl()",
        "gantt_zoom",
        "gantt_color",
        "gantt_batch",
        "gantt_resource",
        "gantt_overdue",
        "gantt_external",
        "gantt_deps",
        "gantt_hcc",
    ):
        _assert_true(needle in src, f"gantt_ui.js 缺少 URL 持久化关键片段: {needle}")

    # 轻量级语义检查：确保默认值会被删除，不污染 URL
    # 这里不执行浏览器，仅验证 key 设计与默认值逻辑存在
    _assert_true('level === "day"' in src, "gantt_zoom 默认值清理逻辑缺失")
    _assert_true('url.searchParams.delete("gantt_vm")' in src, "旧 gantt_vm 清理逻辑缺失")
    _assert_true('ui.colorMode === "batch"' in src, "colorMode 默认值清理逻辑缺失")
    _assert_true('ui.depsMode === "critical"' in src, "depsMode 默认值清理逻辑缺失")

    _assert_js_url_contract(repo_root)
