"""甘特小修包契约（fusion-gantt-fix-pack）。

钉死点：①applyFilters 批次/资源筛选精确等值（equalsI——B1 不带出 B12，大小写
不敏感保留，machine/operator 两视图同语义）；②dark 块 .aps-cc-outline-outer
覆盖锁 token 值（亮色外圈 #334155 与暗色边框同色隐形）；③模拟调整死按钮整壳
零残留（gantt.html/CSS 文件/HEX_FREEZE_ALLOWANCE 反向断言）；④ZOOM_SPECS 与
vendor update_view_scale 双份真相——collectZoomSpecMismatches 纯函数红绿自证
+ boot 接线（真 vendor 静默过/漂移 fail-loud 早错）。
"""

from __future__ import annotations

import importlib.util
import re

from tests._support.paths import REPO_ROOT


def _load_gantt_helpers():
    helper_path = REPO_ROOT / "tests" / "gantt" / "test_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _chain_walk_js(helpers):
    import json

    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_chain_walk.js"))


def _full_chain_setup(helpers) -> str:
    return f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
createHost("ganttZoomWarning");
createHost("ganttTaskDetail");

loadScript({helpers._vendor_js()});
loadScript({helpers._gantt_js()});
loadScript({helpers._gantt_zoom_js()});
loadScript({helpers._gantt_adapter_js()});
loadScript({helpers._gantt_color_js()});
loadScript({helpers._outline_js()});
loadScript({helpers._gantt_contract_js()});
loadScript({helpers._gantt_help_js()});
loadScript({helpers._gantt_popup_js()});
loadScript({helpers._gantt_legend_js()});
loadScript({helpers._gantt_holidays_js()});
loadScript({helpers._gantt_decorations_js()});
loadScript({_chain_walk_js(helpers)});
loadScript({helpers._gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
function mkTask(id, batch, machineId, machine, operatorId, operator) {{
  return {{
    id: id, name: id, start: "2026-05-01 08:00:00", end: "2026-05-01 09:00:00",
    progress: 0, dependencies: "",
    meta: {{ batch_id: batch, machine_id: machineId, machine: machine,
             operator_id: operatorId, operator: operator, source: "internal" }},
  }};
}}
state.allTasks = [
  mkTask("T1", "B1", "MC1", "车床一号", "OP1", "张三"),
  mkTask("T2", "B12", "MC12", "车床十二号", "OP12", "李四"),
  mkTask("T3", "B100", "MC100", "车床百号", "OP100", "王五"),
];
state.cfg = {{ view: "machine" }};
"""


def _boot_stub_ui_js() -> str:
    return """
ns.initCalendarDays = ns.initCalendarDays || function () {};
ns.applyUiFromUrl = function () {};
ns.bindUi = function () {};
ns.readUi = function () {};
ns.persistUiToUrl = function () {};
document.readyState = "loading";
"""


def _run(helpers, body: str) -> dict:
    return helpers._run_node_json(_full_chain_setup(helpers) + body)


# ---------- ①筛选精确匹配 ----------

def test_apply_filters_batch_exact_match_not_substring():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
state.ui.filterBatch = "B1";
const exact = ns.applyFilters(state.allTasks).map(t => t.id);
state.ui.filterBatch = "b1"; // 大小写不敏感保留（后端 id 只 strip 未统一大小写）
const ci = ns.applyFilters(state.allTasks).map(t => t.id);
state.ui.filterBatch = "";
const all = ns.applyFilters(state.allTasks).map(t => t.id);
process.stdout.write(JSON.stringify({ exact, ci, all }));
""")
    assert result["exact"] == ["T1"]  # B1 不再带出 B12/B100
    assert result["ci"] == ["T1"]
    assert result["all"] == ["T1", "T2", "T3"]


def test_apply_filters_resource_exact_both_views():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
state.ui.filterResource = "MC1";
const machineById = ns.applyFilters(state.allTasks).map(t => t.id);
state.ui.filterResource = "车床一号"; // 名称等值同样命中（id/名称双字段 or 语义保留）
const machineByName = ns.applyFilters(state.allTasks).map(t => t.id);
state.cfg = { view: "operator" };
state.ui.filterResource = "OP1";
const operatorById = ns.applyFilters(state.allTasks).map(t => t.id);
state.ui.filterResource = "张三";
const operatorByName = ns.applyFilters(state.allTasks).map(t => t.id);
process.stdout.write(JSON.stringify({ machineById, machineByName, operatorById, operatorByName }));
""")
    assert result["machineById"] == ["T1"]  # MC1 不带出 MC12/MC100
    assert result["machineByName"] == ["T1"]
    assert result["operatorById"] == ["T1"]  # OP1 不带出 OP12/OP100
    assert result["operatorByName"] == ["T1"]


# ---------- ②dark cc-outline 覆盖 ----------

def test_dark_cc_outline_override_locked():
    css = (REPO_ROOT / "static" / "css" / "aps_gantt.css").read_text(encoding="utf-8")
    # 锁选择器+token 值（不只测存在）：亮色外圈 #334155 与暗色边框/卡片底同色隐形
    pattern = re.compile(
        r'html\[data-theme="dark"\]\s+\.aps-cc-outline-outer\s*\{[^}]*stroke:\s*var\(--ui-muted\)',
    )
    assert pattern.search(css), "dark 块缺 .aps-cc-outline-outer 的 --ui-muted 覆盖"


# ---------- ③死按钮整壳零残留 ----------

def test_simulation_shell_removed_zero_references():
    html = (REPO_ROOT / "templates" / "scheduler" / "gantt.html").read_text(encoding="utf-8")
    assert "ganttSimulationEntry" not in html
    assert "aps_gantt_simulation" not in html
    assert not (REPO_ROOT / "static" / "css" / "aps_gantt_simulation.css").exists()
    hex_contract = (REPO_ROOT / "tests" / "web_pages" / "test_css_token_source_contract.py").read_text(
        encoding="utf-8"
    )
    assert "aps_gantt_simulation" not in hex_contract  # 删文件后白名单残留即漂移
    # 文字连带反向守卫：防旧口径（灰色入口/不能点击/入口仍禁用）被塞回文档或 viewmodel
    for rel in (
        ".codestable/architecture/ui-gantt.md",
        "web/viewmodels/page_manuals_scheduler_outputs.py",
        "static/docs/scheduler_manual.md",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for stale in (
            "灰色说明入口",
            "灰色禁用按钮",
            "灰色入口",
            "不能点击",
            "当前页面入口仍禁用",
            "ganttSimulationEntry",
        ):
            assert stale not in text, f"{rel} 残留旧口径文案：{stale}"


# ---------- ④双份真相断言 ----------

def test_collect_zoom_spec_mismatches_red_green():
    helpers = _load_gantt_helpers()
    result = _run(helpers, _boot_stub_ui_js() + f"""
loadScript({helpers._gantt_boot_js()});
// 绿：真 vendor 写值全配
const real = ns.collectZoomSpecMismatches(function (options, mode) {{
  Gantt.prototype.update_view_scale.call({{ options: options }}, mode);
}});
// 红：篡改任一级 step_minutes
const tampered = ns.collectZoomSpecMismatches(function (options, mode) {{
  Gantt.prototype.update_view_scale.call({{ options: options }}, mode);
  if (mode === "Hour") options.step_minutes = 999;
}});
process.stdout.write(JSON.stringify({{ real, tampered,
  bootError: document.getElementById("ganttError").textContent }}));
""")
    assert result["real"] == []
    assert len(result["tampered"]) == 1
    assert "Hour" in result["tampered"][0]
    assert "999" in result["tampered"][0]
    # 真 vendor 下 boot 启动断言静默通过
    assert result["bootError"] == ""


def test_boot_zoom_drift_fails_loud_with_early_error():
    helpers = _load_gantt_helpers()
    result = _run(helpers, _boot_stub_ui_js() + f"""
// vendor 数值表漂移仿真：换成写错值的假 Gantt 再加载 boot
window.Gantt = {{ prototype: {{ update_view_scale: function (mode) {{
  this.options.step_minutes = 1;
  this.options.column_width = 1;
}} }} }};
loadScript({helpers._gantt_boot_js()});
process.stdout.write(JSON.stringify({{
  error: document.getElementById("ganttError").textContent,
  loadAndRenderExported: typeof ns.loadAndRender === "function",
}}));
""")
    assert "时间粒度配置与渲染组件不一致" in result["error"]
    # fail-loud：失配即停整个 boot，不带着错误几何跛行渲染
    assert result["loadAndRenderExported"] is False
