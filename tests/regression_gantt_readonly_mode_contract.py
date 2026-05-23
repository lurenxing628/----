from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_gantt_dom_helpers():
    helper_path = REPO_ROOT / "tests" / "regression_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readonly_gantt_blocks_drag_resize_and_progress_events_but_keeps_click() -> None:
    helpers = _load_gantt_dom_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
loadScript({helpers._vendor_js()});

let dateChanges = 0;
let progressChanges = 0;
let clicks = 0;

const gantt = new Gantt("#gantt", [{{
  id: "T1",
  name: "Readonly Task",
  start: "2026-05-11 08:00:00",
  end: "2026-05-11 09:00:00",
  progress: 50,
  dependencies: "",
}}], {{
  view_mode: "Hour",
  readonly: true,
  readonly_dates: true,
  readonly_progress: true,
  popup_trigger: "click",
  on_date_change: function () {{ dateChanges += 1; }},
  on_progress_change: function () {{ progressChanges += 1; }},
  on_click: function () {{ clicks += 1; }},
}});

const bar = gantt.get_bar("T1");
const wrapper = findWrapperById("T1");
const svg = document.querySelector("#gantt svg.gantt");
const before = {{
  x: Number(bar.$bar.getAttribute("x")),
  width: Number(bar.$bar.getAttribute("width")),
  progressWidth: Number(bar.$bar_progress.getAttribute("width")),
  handles: wrapper.querySelectorAll(".handle").length,
}};

function event(type, target, offsetX, offsetY) {{
  const evt = document.createEvent("HTMLEvents");
  evt.initEvent(type, true, true);
  evt.offsetX = offsetX;
  evt.offsetY = offsetY;
  target.dispatchEvent(evt);
}}

event("mousedown", wrapper, before.x, 0);
event("mousemove", svg, before.x + 200, 0);
event("mouseup", svg, before.x + 200, 0);
event("click", wrapper.querySelector(".bar-hit"), before.x, 0);

const after = {{
  x: Number(bar.$bar.getAttribute("x")),
  width: Number(bar.$bar.getAttribute("width")),
  progressWidth: Number(bar.$bar_progress.getAttribute("width")),
  handles: wrapper.querySelectorAll(".handle").length,
  popupVisible: document.querySelector("#gantt .popup-wrapper").style.opacity,
  dateChanges,
  progressChanges,
  clicks,
}};

process.stdout.write(JSON.stringify({{ before, after }}));
"""
    result = helpers._run_node_json(node_code)

    assert result["before"]["handles"] == 0
    assert result["after"]["handles"] == 0
    assert result["after"]["x"] == result["before"]["x"]
    assert result["after"]["width"] == result["before"]["width"]
    assert result["after"]["progressWidth"] == result["before"]["progressWidth"]
    assert result["after"]["dateChanges"] == 0
    assert result["after"]["progressChanges"] == 0
    assert result["after"]["clicks"] == 1
    assert str(result["after"]["popupVisible"]) == "1"


def test_formal_render_passes_readonly_options_and_blocks_drag() -> None:
    helpers = _load_gantt_dom_helpers()
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
  name: "Formal readonly task",
  start: "2026-05-11 08:00:00",
  end: "2026-05-11 09:00:00",
  progress: 40,
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
const svg = document.querySelector("#gantt svg.gantt");
const beforeX = Number(bar.$bar.getAttribute("x"));

function event(type, target, offsetX, offsetY) {{
  const evt = document.createEvent("HTMLEvents");
  evt.initEvent(type, true, true);
  evt.offsetX = offsetX;
  evt.offsetY = offsetY;
  target.dispatchEvent(evt);
}}

event("mousedown", wrapper, beforeX, 0);
event("mousemove", svg, beforeX + 200, 0);
event("mouseup", svg, beforeX + 200, 0);

process.stdout.write(JSON.stringify({{
  readonly: lastOptions && lastOptions.readonly,
  readonlyDates: lastOptions && lastOptions.readonly_dates,
  readonlyProgress: lastOptions && lastOptions.readonly_progress,
  viewMode: lastOptions && lastOptions.view_mode,
  handleCount: wrapper.querySelectorAll(".handle").length,
  beforeX,
  afterX: Number(bar.$bar.getAttribute("x")),
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["readonly"] is True
    assert result["readonlyDates"] is True
    assert result["readonlyProgress"] is True
    assert result["viewMode"] == "Hour"
    assert result["handleCount"] == 0
    assert result["afterX"] == result["beforeX"]


def test_templates_show_readonly_mode_and_zoom_contract() -> None:
    for rel in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        html = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "当前为查看模式" in html
        assert 'id="ganttZoomLevel"' in html
        assert 'id="ganttZoomWarning"' in html
        assert 'data-gantt-mode="view"' in html
        assert 'data-zoom-level="{{ gantt_zoom or' in html


def main() -> None:
    test_readonly_gantt_blocks_drag_resize_and_progress_events_but_keeps_click()
    test_formal_render_passes_readonly_options_and_blocks_drag()
    test_templates_show_readonly_mode_and_zoom_contract()
    print("OK")


if __name__ == "__main__":
    main()
