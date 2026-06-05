"""回归测试：甘特图各缩放级别下装饰层与真实条对齐——细缩放（hour/15/5/1 分钟）时 bar 宽度按 stepMinutes 精确换算、命中区不小于 12px、临界链外框紧贴真实条、今天高亮与节假日矩形覆盖整天且 x=0、箭头路径无 NaN、overdue/external 样式保留；week/month 缩放时节假日矩形宽度只占一天而非整列。"""

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


def test_fine_zoom_keeps_holiday_today_arrow_and_critical_outline_aligned_to_real_bar() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
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
loadScript({helpers._gantt_holidays_js()});
loadScript({helpers._gantt_decorations_js()});
loadScript({helpers._gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;

function pad(value) {{
  return value < 10 ? "0" + value : String(value);
}}
function localDateText(date) {{
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
}}

const todayText = localDateText(new Date());
const levels = ["hour", "fifteen-minute", "five-minute", "one-minute"];
const out = [];

for (const level of levels) {{
const spec = ns.zoom.getZoomSpec(level);
state.cfg = {{
  view: "machine",
  startDate: todayText,
  endDate: todayText,
  weekStart: todayText,
}};
state.allTasks = [
  {{
    id: "T10",
    name: "Short critical",
    start: todayText + " 08:00:00",
    end: todayText + " 08:10:00",
    progress: 0,
    dependencies: "",
    meta: {{
      batch_id: "B001",
      source: "external",
      priority: "critical",
      status: "pending",
      is_overdue: true,
    }},
  }},
  {{
    id: "T11",
    name: "Short dependent",
    start: todayText + " 08:20:00",
    end: todayText + " 08:30:00",
    progress: 0,
    dependencies: "T10",
    meta: {{
      batch_id: "B001",
      source: "internal",
      priority: "normal",
      status: "pending",
    }},
  }},
];
state.critical = {{ ids: ["T10"], edges: [], makespan_end: todayText + " 08:30:00", available: true }};
state.ccIdSet = new Set(["T10"]);
state.ccPrevByTo = new Map();
state.ccEdgeMetaByTo = new Map();
state.calendarDays = [{{ date: todayText, day_type: "holiday", shift_hours: 0, is_holiday: true, is_nonworking: true }}];
state.ui.zoomLevel = level;
state.ui.viewMode = spec.frappeViewMode;
state.ui.colorMode = "batch";
state.ui.depsMode = "process";
state.ui.highlightCC = true;
state.ui.onlyOverdue = false;
state.ui.onlyExternal = false;
state.ui.filterBatch = "";
state.ui.filterResource = "";

ns.render();

const wrapper = findWrapperById("T10");
const bar = wrapper.querySelector(".bar");
const hit = wrapper.querySelector(".bar-hit");
const holiday = document.querySelector(".aps-holiday-rect");
const today = document.querySelector(".today-highlight");
const outline = wrapper.querySelector(".aps-cc-outline-outer");
const arrow = document.querySelector("#gantt .arrow path");
out.push({{
  level,
  barWidth: Number(bar.getAttribute("width")),
  hitWidth: Number(hit.getAttribute("width")),
  holidayX: Number(holiday.getAttribute("x")),
  holidayWidth: Number(holiday.getAttribute("width")),
  todayX: Number(today.getAttribute("x")),
  todayWidth: Number(today.getAttribute("width")),
  outlineWidth: Number(outline.getAttribute("width")),
  expectedBarWidth: 10 / spec.stepMinutes * spec.columnWidthPx,
  expectedDayWidth: 1440 / spec.stepMinutes * spec.columnWidthPx,
  scrollLeft: document.querySelector("#gantt .gantt-container").scrollLeft,
  arrowPath: arrow ? String(arrow.getAttribute("d") || "") : "",
  overdue: wrapper.classList.contains("overdue"),
  external: wrapper.classList.contains("aps-external"),
}});
}}

process.stdout.write(JSON.stringify({{ out }}));
"""
    result = helpers._run_node_json(node_code)

    assert [item["level"] for item in result["out"]] == ["hour", "fifteen-minute", "five-minute", "one-minute"]
    for item in result["out"]:
        assert abs(item["barWidth"] - item["expectedBarWidth"]) < 0.001, item
        assert item["hitWidth"] >= 12
        assert item["holidayX"] == 0
        assert item["holidayWidth"] == item["expectedDayWidth"]
        assert item["todayX"] == 0
        assert item["todayWidth"] == item["expectedDayWidth"]
        assert abs(item["outlineWidth"] - (item["barWidth"] + 4)) < 0.001
        if item["hitWidth"] > item["barWidth"]:
            assert item["outlineWidth"] < item["hitWidth"] + 4
        assert item["scrollLeft"] == 0
        assert item["arrowPath"]
        assert "NaN" not in item["arrowPath"]
        assert item["overdue"] is True
        assert item["external"] is True




def test_week_month_zoom_holiday_width_is_one_day_not_whole_column() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
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
loadScript({helpers._gantt_holidays_js()});
loadScript({helpers._gantt_decorations_js()});
loadScript({helpers._gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
const anchor = "2026-06-01";
const out = [];

for (const level of ["week", "month"]) {{
  const spec = ns.zoom.getZoomSpec(level);
  state.cfg = {{
    view: "machine",
    startDate: anchor,
    endDate: anchor,
    weekStart: anchor,
  }};
  state.allTasks = [{{
    id: "T10",
    name: "Holiday width task",
    start: anchor + " 08:00:00",
    end: anchor + " 10:00:00",
    progress: 0,
    dependencies: "",
    meta: {{ batch_id: "B001", source: "internal" }},
  }}];
  state.critical = {{ ids: [], edges: [], available: true }};
  state.ccIdSet = new Set();
  state.ccPrevByTo = new Map();
  state.ccEdgeMetaByTo = new Map();
  state.calendarDays = [{{ date: anchor, day_type: "holiday", shift_hours: 0, is_holiday: true, is_nonworking: true }}];
  state.ui.zoomLevel = level;
  state.ui.viewMode = spec.frappeViewMode;
  state.ui.colorMode = "batch";
  state.ui.depsMode = "none";
  state.ui.highlightCC = true;
  state.ui.onlyOverdue = false;
  state.ui.onlyExternal = false;
  state.ui.filterBatch = "";
  state.ui.filterResource = "";

  ns.render();

  const holiday = document.querySelector(".aps-holiday-rect");
  out.push({{
    level,
    holidayX: Number(holiday.getAttribute("x")),
    holidayWidth: Number(holiday.getAttribute("width")),
    expectedDayWidth: 1440 / spec.stepMinutes * spec.columnWidthPx,
    columnWidth: spec.columnWidthPx,
  }});
}}

process.stdout.write(JSON.stringify({{ out }}));
"""
    result = helpers._run_node_json(node_code)

    assert [item["level"] for item in result["out"]] == ["week", "month"]
    for item in result["out"]:
        assert abs(item["holidayWidth"] - item["expectedDayWidth"]) < 0.001, item
        assert item["holidayWidth"] < item["columnWidth"], item


def main() -> None:
    test_fine_zoom_keeps_holiday_today_arrow_and_critical_outline_aligned_to_real_bar()
    test_week_month_zoom_holiday_width_is_one_day_not_whole_column()
    print("OK")


if __name__ == "__main__":
    main()
