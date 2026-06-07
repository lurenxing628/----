"""回归测试：前端甘特 adapter（buildGanttOptions/createGantt）按 zoom 契约从 zoomLevel 派生 view_mode/step_minutes/column_width 与几何，并按 mode（view 只读、simulate 可拖拽）正确设置 readonly/readonly_dates/readonly_progress、on_click/custom_popup_html/on_date_change；render() 复用 adapter 选项、保持只读点击弹窗并按 batch 聚焦，bar 宽度随分钟步长正确缩放。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from tests._support.paths import REPO_ROOT


def _load_helpers():
    helper_path = REPO_ROOT / "tests" / "gantt" / "test_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adapter_builds_view_and_simulate_options_from_zoom_contract() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
loadScript({helpers._gantt_js()});
loadScript({helpers._gantt_zoom_js()});
loadScript({helpers._gantt_adapter_js()});

const adapter = window.__APS_GANTT__.adapter;
const viewOptions = adapter.buildGanttOptions({{
  mode: "view",
  zoomLevel: "hour",
  onClick: function () {{}},
  customPopupHtml: function () {{}},
}});
const simulateChanges = [];
const simulateOptions = adapter.buildGanttOptions({{
  mode: "simulate",
  zoomLevel: "fifteen-minute",
  onDraftChange: function (evt) {{ simulateChanges.push(evt.type); }},
}});
simulateOptions.on_date_change({{ id: "T1" }}, new Date(2026, 4, 11, 8), new Date(2026, 4, 11, 9));

process.stdout.write(JSON.stringify({{
  view: {{
    viewMode: viewOptions.view_mode,
    stepMinutes: viewOptions.step_minutes,
    stepMs: viewOptions.step_ms,
    columnWidth: viewOptions.column_width,
    readonly: viewOptions.readonly,
    readonlyDates: viewOptions.readonly_dates,
    readonlyProgress: viewOptions.readonly_progress,
    popupTrigger: viewOptions.popup_trigger,
    clickType: typeof viewOptions.on_click,
    popupType: typeof viewOptions.custom_popup_html,
  }},
  simulate: {{
    viewMode: simulateOptions.view_mode,
    stepMinutes: simulateOptions.step_minutes,
    readonly: simulateOptions.readonly,
    readonlyDates: simulateOptions.readonly_dates,
    readonlyProgress: simulateOptions.readonly_progress,
    dateChangeType: typeof simulateOptions.on_date_change,
    changes: simulateChanges,
  }},
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["view"] == {
        "viewMode": "Hour",
        "stepMinutes": 60,
        "stepMs": 60 * 60 * 1000,
        "columnWidth": 48,
        "readonly": True,
        "readonlyDates": True,
        "readonlyProgress": True,
        "popupTrigger": "click",
        "clickType": "function",
        "popupType": "function",
    }
    assert result["simulate"]["viewMode"] == "Fifteen Minute"
    assert result["simulate"]["stepMinutes"] == 15
    assert result["simulate"]["readonly"] is False
    assert result["simulate"]["readonlyDates"] is False
    assert result["simulate"]["readonlyProgress"] is True
    assert result["simulate"]["dateChangeType"] == "function"
    assert result["simulate"]["changes"] == ["date_change"]


def test_adapter_create_gantt_uses_vendor_geometry_without_copying_zoom_mapping() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
loadScript({helpers._vendor_js()});
loadScript({helpers._gantt_js()});
loadScript({helpers._gantt_zoom_js()});
loadScript({helpers._gantt_adapter_js()});

const adapter = window.__APS_GANTT__.adapter;
const gantt = adapter.createGantt({{
  selector: "#gantt",
  mode: "simulate",
  zoomLevel: "one-minute",
  tasks: [{{
    id: "T36",
    name: "36 minute task",
    start: "2026-05-11 08:00:00",
    end: "2026-05-11 08:36:00",
    progress: 0,
    dependencies: "",
  }}],
}});
const bar = gantt.get_bar("T36");
process.stdout.write(JSON.stringify({{
  viewMode: gantt.options.view_mode,
  stepMinutes: gantt.options.step_minutes,
  dateDeltaMs: gantt.dates[1] - gantt.dates[0],
  width: Number(bar.$bar.getAttribute("width")),
  expectedWidth: 36 * gantt.options.column_width,
  handleCount: findWrapperById("T36").querySelectorAll(".handle").length,
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["viewMode"] == "One Minute"
    assert result["stepMinutes"] == 1
    assert result["dateDeltaMs"] == 60 * 1000
    assert abs(result["width"] - result["expectedWidth"]) < 0.001
    assert result["handleCount"] > 0


def test_render_uses_adapter_options_and_keeps_readonly_click_popup() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
createHost("ganttZoomWarning");

loadScript({helpers._vendor_js()});
const RealGantt = Gantt;
let lastOptions = null;
function CapturingGantt(selector, tasks, options) {{
  lastOptions = options || {{}};
  return new RealGantt(selector, tasks, options);
}}
CapturingGantt.prototype = RealGantt.prototype;
window.Gantt = CapturingGantt;
global.Gantt = CapturingGantt;

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
loadScript({helpers._gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
state.cfg = {{
  view: "machine",
  startDate: "2026-05-11",
  endDate: "2026-05-11",
  weekStart: "2026-05-11",
}};
state.allTasks = [{{
  id: "T1",
  name: "Adapter readonly task",
  start: "2026-05-11 08:00:00",
  end: "2026-05-11 08:36:00",
  progress: 0,
  dependencies: "",
  meta: {{ batch_id: "B001", source: "internal", status: "pending" }},
}}];
state.critical = {{ ids: [], edges: [], available: true }};
state.ccIdSet = new Set();
state.ccPrevByTo = new Map();
state.ccEdgeMetaByTo = new Map();
state.calendarDays = [];
state.ui.mode = "view";
state.ui.zoomLevel = "hour";
state.ui.viewMode = "Hour";
state.ui.colorMode = "batch";
state.ui.depsMode = "critical";
state.ui.highlightCC = true;
state.ui.onlyOverdue = false;
state.ui.onlyExternal = false;
state.ui.filterBatch = "";
state.ui.filterResource = "";

ns.render();

const bar = state.gantt.get_bar("T1");
const wrapper = findWrapperById("T1");
lastOptions.on_click(state.currentTasks[0]);

process.stdout.write(JSON.stringify({{
  viewMode: lastOptions && lastOptions.view_mode,
  stepMinutes: lastOptions && lastOptions.step_minutes,
  readonly: lastOptions && lastOptions.readonly,
  readonlyDates: lastOptions && lastOptions.readonly_dates,
  readonlyProgress: lastOptions && lastOptions.readonly_progress,
  popupTrigger: lastOptions && lastOptions.popup_trigger,
  clickType: typeof (lastOptions && lastOptions.on_click),
  popupType: typeof (lastOptions && lastOptions.custom_popup_html),
  handleCount: wrapper.querySelectorAll(".handle").length,
  focusBatch: state.focusBatch,
  popupHasPointer: lastOptions.custom_popup_html(state.currentTasks[0]).indexOf('class="pointer"') >= 0,
  barWidth: Number(bar.$bar.getAttribute("width")),
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["viewMode"] == "Hour"
    assert result["stepMinutes"] == 60
    assert result["readonly"] is True
    assert result["readonlyDates"] is True
    assert result["readonlyProgress"] is True
    assert result["popupTrigger"] == "click"
    assert result["clickType"] == "function"
    assert result["popupType"] == "function"
    assert result["handleCount"] == 0
    assert result["focusBatch"] == "B001"
    assert result["popupHasPointer"] is True
    assert result["barWidth"] > 0


def main() -> None:
    test_adapter_builds_view_and_simulate_options_from_zoom_contract()
    test_adapter_create_gantt_uses_vendor_geometry_without_copying_zoom_mapping()
    test_render_uses_adapter_options_and_keeps_readonly_click_popup()
    print("OK")


if __name__ == "__main__":
    main()
