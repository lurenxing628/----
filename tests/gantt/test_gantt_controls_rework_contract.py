"""甘特控件重排契约（fusion-gantt-controls-rework，Node DOM 仿真）。

钉死点：解码条批次 chips（上限 8+「等 N 个批次」按 allTasks 全量计）点击即筛
（写 filterBatch+同步 select+URL+render，再点同 chip 清筛，is-active 跟随）；
非 batch 配色模式零 data-batch；zoom ± 步进沿 select option 序 ±1 且端点
disabled、走 change 通路（URL 持久化不破）；宽屏 onClick 先 hide_popup（窄屏
不调）；模板结构（图例在 details 外/summary=筛选/无旧提示文案/±按钮存在）。
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


def _gantt_ui_js():
    import json

    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_ui.js"))


def _setup_js(helpers, n_batches: int = 3) -> str:
    return f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttLegend");
createHost("ganttTaskDetail");

function makeControl(tag, id, value) {{
  const el = document.createElement(tag);
  el.setAttribute("id", id);
  el.value = value || "";
  el.options = [];
  document.body.appendChild(el);
  return el;
}}
makeControl("select", "ganttFilterBatch", "");
makeControl("input", "ganttZoomFormValue", "day");
createHost("ganttZoomWarning");

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

const ns = window.__APS_GANTT__;
const state = ns.state;
const N = {n_batches};
state.allTasks = [];
for (let i = 1; i <= N; i++) {{
  state.allTasks.push({{
    id: "T" + i, name: "T" + i, start: "2026-05-01 08:00:00", end: "2026-05-01 09:00:00",
    progress: 0, dependencies: "",
    meta: {{ batch_id: "B" + i, machine_id: "MC1", source: "internal" }},
  }});
}}
state.filteredTasks = state.allTasks.slice();
state.ui.colorMode = "batch";
state.cfg = {{ view: "machine" }};
// persistUiToUrl 用真实现（gantt_ui.js）验证 URL 链路；render/decorate 喂桩后加载
window.location.href = "http://local.test/scheduler/gantt?version=1";
window.history = {{ replaceState: function (_s, _t, url) {{ window.location.href = String(url); }} }};
let rendered = 0;
ns.render = function () {{ rendered++; state.filteredTasks = state.allTasks.filter(
  t => !state.ui.filterBatch || t.meta.batch_id.toLowerCase() === state.ui.filterBatch.toLowerCase()); }};
ns.safeDecorateDynamic = function () {{}};
loadScript({_gantt_ui_js()});
function urlHasBatch(bid) {{
  return new URL(window.location.href).searchParams.get("gantt_batch") === bid;
}}
ns.updateLegend();
ns.bindLegendChips();
const legend = document.getElementById("ganttLegend");
"""


def _run(helpers, body: str, n_batches: int = 3) -> dict:
    return helpers._run_node_json(_setup_js(helpers, n_batches) + body)


def _find_chip_js() -> str:
    return """
function findChip(bid) {
  function walk(node) {
    if (node.getAttribute && node.getAttribute("data-batch") === bid) return node;
    const kids = node.children || [];
    for (let i = 0; i < kids.length; i++) {
      const hit = walk(kids[i]);
      if (hit) return hit;
    }
    return null;
  }
  return walk(legend);
}
"""


def test_chips_click_filters_and_second_click_clears():
    helpers = _load_gantt_helpers()
    result = _run(helpers, _find_chip_js() + """
const chip = findChip("B2");
chip.dispatchEvent(new FakeEvent("click"));
const afterSet = { filter: state.ui.filterBatch, rendered, urlBatch: urlHasBatch("B2") };
ns.updateLegend();
const activeAfterSet = findChip("B2").className.indexOf("is-active") >= 0;
findChip("B2").dispatchEvent(new FakeEvent("click"));
const afterClear = { filter: state.ui.filterBatch, rendered,
  urlCleared: new URL(window.location.href).searchParams.get("gantt_batch") === null };
process.stdout.write(JSON.stringify({ afterSet, activeAfterSet, afterClear }));
""")
    # 真实 persistUiToUrl：URL gantt_batch 写入与清除是真链路断言（非桩调用计数）
    assert result["afterSet"] == {"filter": "B2", "rendered": 1, "urlBatch": True}
    assert result["activeAfterSet"] is True
    assert result["afterClear"] == {"filter": "", "rendered": 2, "urlCleared": True}


def test_chips_capped_at_eight_with_total_notice_from_all_tasks():
    helpers = _load_gantt_helpers()
    result = _run(helpers, _find_chip_js() + """
let chipCount = 0;
(function walk(node) {
  if (node.getAttribute && node.getAttribute("data-batch")) chipCount++;
  const kids = node.children || [];
  for (let i = 0; i < kids.length; i++) walk(kids[i]);
})(legend);
// 筛中单批次后 filteredTasks 只剩 1 批，但「等 N 个」按 allTasks 全量
state.ui.filterBatch = "B1";
state.filteredTasks = state.allTasks.filter(t => t.meta.batch_id === "B1");
ns.updateLegend();
process.stdout.write(JSON.stringify({ chipCount,
  more: legend.textContent.indexOf("等 12 个批次") >= 0 }));
""", n_batches=12)
    assert result["chipCount"] == 8  # 上限 8
    assert result["more"] is True  # 全量 12 不被 filtered 吞


def test_non_batch_color_mode_has_no_clickable_chips():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
state.ui.colorMode = "priority";
ns.updateLegend();
let chipCount = 0;
(function walk(node) {
  if (node.getAttribute && node.getAttribute("data-batch")) chipCount++;
  const kids = node.children || [];
  for (let i = 0; i < kids.length; i++) walk(kids[i]);
})(legend);
process.stdout.write(JSON.stringify({ chipCount }));
""")
    assert result["chipCount"] == 0  # 不新增筛选维度


def test_template_decode_bar_outside_details_and_steppers_present():
    html = (REPO_ROOT / "templates" / "scheduler" / "gantt.html").read_text(encoding="utf-8")
    # 图例宿主在 details 之前（常显），details 内无第二个 ganttLegend
    legend_pos = html.index('id="ganttLegend"')
    details_pos = html.index('<details class="details-panel">')
    assert legend_pos < details_pos, "解码条必须在 details 折叠面板之外常显"
    assert html.count('id="ganttLegend"') == 1
    assert "<summary class=\"details-summary\">筛选</summary>" in html
    assert "默认按“批次”配色" not in html  # 旧提示文案删除（解码条即答案）
    assert 'id="ganttZoomOut"' in html and 'id="ganttZoomIn"' in html
    assert 'id="ganttZoomLevel"' in html  # select 保留（url_persistence 契约）
    assert "aps-gantt-version-line" in html  # 摘要四卡压缩单行
    assert "aps-version-summary aps-gantt-version-summary" not in html


def test_wide_viewport_popup_suppressed_in_css_and_render():
    css = (REPO_ROOT / "static" / "css" / "aps_gantt.css").read_text(encoding="utf-8")
    pattern = re.compile(
        r"@media \(min-width: 1180px\)\s*\{[^}]*#gantt \.gantt-container \.popup-wrapper\s*\{\s*display:\s*none",
    )
    assert pattern.search(css), "宽屏 CSS 兜底缺失"
    render_js = (REPO_ROOT / "static" / "js" / "gantt_render.js").read_text(encoding="utf-8")
    assert "isWideViewport()" in render_js
    assert "hide_popup" in render_js
    assert 'matchMedia("(min-width: 1180px)")' in render_js  # 断点与 CSS 同值


def test_zoom_steppers_step_along_select_order_with_endpoint_disabled():
    helpers = _load_gantt_helpers()
    import json as _json
    import os as _os

    repo_root = str(REPO_ROOT)
    result = helpers._run_node_json(f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttZoomWarning");

function makeControl(tag, id, value) {{
  const el = document.createElement(tag);
  el.setAttribute("id", id);
  el.value = value || "";
  el.options = [];
  document.body.appendChild(el);
  return el;
}}
const select = makeControl("select", "ganttZoomLevel", "day");
const levels = ["month", "week", "day", "half-day", "quarter-day", "hour", "fifteen-minute", "five-minute", "one-minute"];
select.options = levels.map(v => ({{ value: v }}));
// change 事件由 shim dispatchEvent 派发；select 桩需 addEventListener 能力（FakeElement 已有）
makeControl("select", "ganttColorMode", "batch");
makeControl("select", "ganttFilterBatch", "");
makeControl("select", "ganttFilterResource", "");
makeControl("input", "ganttOnlyOverdue", "");
makeControl("input", "ganttOnlyExternal", "");
makeControl("select", "ganttDepsMode", "critical");
makeControl("input", "ganttHighlightCC", "").checked = true;
makeControl("input", "ganttZoomFormValue", "day");
const minus = makeControl("button", "ganttZoomOut", "");
const plus = makeControl("button", "ganttZoomIn", "");

window.history = {{ replaceState: function () {{}} }};

loadScript({_json.dumps(_os.path.join(repo_root, "static", "js", "gantt.js"))});
window.__APS_GANTT__.safeDecorateDynamic = function () {{}};
let renders = 0;
window.__APS_GANTT__.render = function () {{ renders++; }};
loadScript({_json.dumps(_os.path.join(repo_root, "static", "js", "gantt_zoom.js"))});
loadScript({_json.dumps(_os.path.join(repo_root, "static", "js", "gantt_ui.js"))});

const ns = window.__APS_GANTT__;
ns.state.cfg = {{ view: "machine" }};
ns.bindUi();
const initial = {{ minusDisabled: !!minus.disabled, plusDisabled: !!plus.disabled }};
plus.dispatchEvent(new FakeEvent("click"));
const afterPlus = {{ value: select.value }};
select.value = "one-minute";
select.dispatchEvent(new FakeEvent("change"));
const atFinest = {{ plusDisabled: !!plus.disabled, minusDisabled: !!minus.disabled }};
select.value = "month";
select.dispatchEvent(new FakeEvent("change"));
const atCoarsest = {{ minusDisabled: !!minus.disabled, plusDisabled: !!plus.disabled }};
// scheduleFullRender 有 240ms debounce——等 timer 跑完再断言 render 被触发
setTimeout(function () {{
  process.stdout.write(JSON.stringify({{ initial, afterPlus, atFinest, atCoarsest, renders: renders > 0 }}));
}}, 400);
""")
    assert result["initial"] == {"minusDisabled": False, "plusDisabled": False}  # day 居中两端可用
    assert result["afterPlus"]["value"] == "half-day"  # day → 下一档
    assert result["atFinest"] == {"plusDisabled": True, "minusDisabled": False}
    assert result["atCoarsest"] == {"minusDisabled": True, "plusDisabled": False}
    assert result["renders"] is True  # 步进走 change 通路触发 render
