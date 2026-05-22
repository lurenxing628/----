from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_helpers():
    helper_path = REPO_ROOT / "tests" / "regression_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zoom_range_guard_blocks_overwide_minute_views_and_warns_soft_limit() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
loadScript({json.dumps(str(REPO_ROOT / "static" / "js" / "gantt.js"))});
loadScript({json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_zoom.js"))});

const zoom = window.__APS_GANTT__.zoom;
function check(zoomLevel, startDate, endDate, taskCount, dependencyCount) {{
  return zoom.validateZoomRange({{
    zoomLevel,
    startDate,
    endDate,
    taskCount: taskCount || 10,
    dependencyCount: dependencyCount || 0,
    holidayMarkerCount: 0,
  }});
}}

process.stdout.write(JSON.stringify({{
  oneMinuteTwoDays: check("one-minute", "2026-05-11", "2026-05-12"),
  fiveMinuteFourDays: check("five-minute", "2026-05-11", "2026-05-14"),
  fifteenMinuteEightDays: check("fifteen-minute", "2026-05-11", "2026-05-18"),
  hourFifteenDays: check("hour", "2026-05-11", "2026-05-25"),
  hardNodes: check("day", "2026-05-11", "2026-05-12", 3000, 0),
  softNodes: check("day", "2026-05-11", "2026-05-12", 1600, 0),
  okDay: check("day", "2026-05-11", "2026-05-12", 100, 20),
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["oneMinuteTwoDays"]["ok"] is False
    assert result["fiveMinuteFourDays"]["ok"] is False
    assert result["fifteenMinuteEightDays"]["ok"] is False
    assert result["hourFifteenDays"]["ok"] is False
    assert result["hardNodes"]["ok"] is False
    assert result["hardNodes"]["reason"] == "nodes"
    assert result["softNodes"]["ok"] is True
    assert result["softNodes"]["level"] == "soft"
    assert result["okDay"]["ok"] is True
    assert result["okDay"]["level"] == "ok"


def test_render_range_guard_uses_actual_task_span_and_blocks_before_new_gantt() -> None:
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
let constructorCalls = 0;
function CapturingGantt(selector, tasks, options) {{
  constructorCalls += 1;
  return new RealGantt(selector, tasks, options);
}}
CapturingGantt.prototype = RealGantt.prototype;
window.Gantt = CapturingGantt;
global.Gantt = CapturingGantt;

loadScript({helpers._gantt_js()});
loadScript({helpers._gantt_zoom_js()});
loadScript({helpers._gantt_color_js()});
loadScript({helpers._outline_js()});
loadScript({helpers._gantt_contract_js()});
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
  id: "T_CROSS",
  name: "Cross day short task",
  start: "2026-05-11 23:45:00",
  end: "2026-05-12 00:15:00",
  progress: 0,
  dependencies: "",
  meta: {{ batch_id: "B001", source: "internal", status: "pending" }},
}}];
state.critical = {{ ids: [], edges: [], available: true }};
state.ccIdSet = new Set();
state.ccPrevByTo = new Map();
state.ccEdgeMetaByTo = new Map();
state.calendarDays = [];
state.ui.zoomLevel = "one-minute";
state.ui.viewMode = "One Minute";
state.ui.colorMode = "batch";
state.ui.depsMode = "critical";
state.ui.highlightCC = true;
state.ui.onlyOverdue = false;
state.ui.onlyExternal = false;
state.ui.filterBatch = "";
state.ui.filterResource = "";

ns.render();

process.stdout.write(JSON.stringify({{
  constructorCalls,
  warning: document.getElementById("ganttZoomWarning").textContent || "",
  currentTasks: state.currentTasks.length,
  ganttIsNull: state.gantt === null,
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["constructorCalls"] == 0
    assert result["ganttIsNull"] is True
    assert result["currentTasks"] == 1
    assert "范围太宽" in result["warning"] or "时间格太多" in result["warning"]


def test_render_range_guard_treats_midnight_end_as_selected_day_boundary() -> None:
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
let constructorCalls = 0;
function CapturingGantt(selector, tasks, options) {{
  constructorCalls += 1;
  return new RealGantt(selector, tasks, options);
}}
CapturingGantt.prototype = RealGantt.prototype;
window.Gantt = CapturingGantt;
global.Gantt = CapturingGantt;

loadScript({helpers._gantt_js()});
loadScript({helpers._gantt_zoom_js()});
loadScript({helpers._gantt_color_js()});
loadScript({helpers._outline_js()});
loadScript({helpers._gantt_contract_js()});
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
  id: "T_TO_MIDNIGHT",
  name: "Ends exactly at midnight",
  start: "2026-05-11 23:45:00",
  end: "2026-05-12 00:00:00",
  progress: 0,
  dependencies: "",
  meta: {{ batch_id: "B001", source: "internal", status: "pending" }},
}}];
state.critical = {{ ids: [], edges: [], available: true }};
state.ccIdSet = new Set();
state.ccPrevByTo = new Map();
state.ccEdgeMetaByTo = new Map();
state.calendarDays = [];
state.ui.zoomLevel = "one-minute";
state.ui.viewMode = "One Minute";
state.ui.colorMode = "batch";
state.ui.depsMode = "critical";
state.ui.highlightCC = true;
state.ui.onlyOverdue = false;
state.ui.onlyExternal = false;
state.ui.filterBatch = "";
state.ui.filterResource = "";

ns.render();

process.stdout.write(JSON.stringify({{
  constructorCalls,
  warning: document.getElementById("ganttZoomWarning").textContent || "",
  currentTasks: state.currentTasks.length,
  ganttIsNull: state.gantt === null,
  dateCount: state.gantt ? state.gantt.dates.length : 0,
  barWidth: state.gantt ? state.gantt.get_bar("T_TO_MIDNIGHT").$bar.getWidth() : 0,
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["constructorCalls"] == 1
    assert result["ganttIsNull"] is False
    assert result["currentTasks"] == 1
    assert result["warning"] == ""
    assert result["dateCount"] <= 1441
    assert result["barWidth"] == 270


def main() -> None:
    test_zoom_range_guard_blocks_overwide_minute_views_and_warns_soft_limit()
    test_render_range_guard_uses_actual_task_span_and_blocks_before_new_gantt()
    test_render_range_guard_treats_midnight_end_as_selected_day_boundary()
    print("OK")


if __name__ == "__main__":
    main()
