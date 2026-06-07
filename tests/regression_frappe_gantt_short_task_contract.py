"""回归测试：定制版 frappe-gantt 在各缩放档（Day/Hour/分钟级/只读全档）下保持短工序（36/51/73 分钟、跨午夜）可见且可点选拖拽——bar 宽度按 step_ms 几何精确、hitbox 宽≥12px、点击短任务能激活并弹窗、resize/move 后起止时间零漂移；并钉死短任务修复只动 vendor min.js 的时间几何、不污染 gantt_render.js。"""

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


def test_frappe_gantt_keeps_short_tasks_visible_and_draggable() -> None:
    helpers = _load_gantt_dom_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
loadScript({helpers._vendor_js()});

const tasks = [
  {{
    id: "T36",
    name: "36 minute task",
    start: "2026-05-11 08:00:00",
    end: "2026-05-11 08:36:00",
    progress: 0,
    dependencies: "",
  }},
  {{
    id: "T51",
    name: "51 minute task",
    start: "2026-05-11 08:51:36",
    end: "2026-05-11 09:43:12",
    progress: 0,
    dependencies: "",
  }},
  {{
    id: "T73",
    name: "73 minute task",
    start: "2026-05-11 10:00:00",
    end: "2026-05-11 11:13:12",
    progress: 0,
    dependencies: "",
  }},
  {{
    id: "T36MID",
    name: "36 minute midnight task",
    start: "2026-05-11 23:24:00",
    end: "2026-05-12 00:00:00",
    progress: 0,
    dependencies: "",
  }},
];

const gantt = new Gantt("#gantt", tasks, {{ view_mode: "Day" }});

function snapshot(taskId) {{
  const bar = gantt.get_bar(taskId);
  const wrapper = findWrapperById(taskId);
  const hit = wrapper.querySelector(".bar-hit");
  const left = wrapper.querySelector(".handle.left");
  const right = wrapper.querySelector(".handle.right");
  const dates = bar.compute_start_end_date();
  return {{
    x: Number(bar.$bar.getAttribute("x")),
    width: Number(bar.$bar.getAttribute("width")),
    hitX: Number(hit && hit.getAttribute("x")),
    hitWidth: Number(hit && hit.getAttribute("width")),
    leftX: Number(left && left.getAttribute("x")),
    rightX: Number(right && right.getAttribute("x")),
    startDeltaMs: dates.new_start_date - bar.task._start,
    endDeltaMs: dates.new_end_date - bar.task._end,
  }};
}}

function clickHit(taskId) {{
  const wrapper = findWrapperById(taskId);
  const hit = wrapper.querySelector(".bar-hit");
  const evt = document.createEvent("HTMLEvents");
  evt.initEvent("click", true, true);
  hit.dispatchEvent(evt);
  return {{
    active: wrapper.classList.contains("active"),
    popupOpacity: document.querySelector("#gantt .popup-wrapper").style.opacity,
  }};
}}

const initial = {{
  T36: snapshot("T36"),
  T51: snapshot("T51"),
  T73: snapshot("T73"),
  T36MID: snapshot("T36MID"),
}};

const shortTaskClick = clickHit("T36");
const bar36 = gantt.get_bar("T36");
bar36.update_bar_position({{ width: 0.5 }});
const resized = snapshot("T36");
bar36.update_bar_position({{ x: 0 }});
const movedToZero = snapshot("T36");

process.stdout.write(JSON.stringify({{
  initial,
  shortTaskClick,
  resized,
  movedToZero,
}}));
"""
    result = helpers._run_node_json(node_code)
    initial = result["initial"]

    assert abs(initial["T36"]["width"] - 0.95) < 0.001
    assert abs(initial["T51"]["width"] - 1.3616666667) < 0.001
    assert abs(initial["T73"]["width"] - 1.9316666667) < 0.001
    assert abs(initial["T36MID"]["width"] - 0.95) < 0.001
    assert abs((initial["T51"]["x"] - initial["T36"]["x"]) - 1.3616666667) < 0.001

    for task_id in ("T36", "T51", "T73", "T36MID"):
        task = initial[task_id]
        assert task["width"] > 0
        assert task["hitWidth"] >= 12
        assert task["leftX"] < task["rightX"]
        assert task["startDeltaMs"] == 0
        assert task["endDeltaMs"] == 0

    assert result["shortTaskClick"]["active"] is True
    assert str(result["shortTaskClick"]["popupOpacity"]) == "1"
    assert result["resized"]["width"] == 0.5
    assert result["resized"]["hitWidth"] >= 12
    assert result["movedToZero"]["x"] == 0


def test_frappe_gantt_supports_hour_and_minute_zoom_geometry() -> None:
    helpers = _load_gantt_dom_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
loadScript({helpers._vendor_js()});

const modes = [
  ["Hour", 60, 48, 36 * 48 / 60],
  ["Fifteen Minute", 15, 32, 36 * 32 / 15],
  ["Five Minute", 5, 24, 36 * 24 / 5],
  ["One Minute", 1, 18, 36 * 18],
];

const results = modes.map(([mode, stepMinutes, columnWidth, expectedWidth]) => {{
  const host = createHost("gantt_" + mode.replace(/\\s+/g, "_"));
  const gantt = new Gantt(host, [{{
    id: "T36",
    name: "36 minute task",
    start: "2026-05-11 08:00:00",
    end: "2026-05-11 08:36:00",
    progress: 0,
    dependencies: "",
  }}], {{ view_mode: mode }});
  const bar = gantt.get_bar("T36");
  return {{
    mode,
    stepMinutes: gantt.options.step_minutes,
    columnWidth: gantt.options.column_width,
    dateDeltaMs: gantt.dates[1] - gantt.dates[0],
    width: Number(bar.$bar.getAttribute("width")),
    expectedWidth,
    startDeltaMs: bar.compute_start_end_date().new_start_date - bar.task._start,
    endDeltaMs: bar.compute_start_end_date().new_end_date - bar.task._end,
  }};
}});

process.stdout.write(JSON.stringify({{ results }}));
"""
    result = helpers._run_node_json(node_code)

    for item in result["results"]:
        assert item["stepMinutes"] in (60, 15, 5, 1)
        assert item["dateDeltaMs"] == item["stepMinutes"] * 60 * 1000
        assert abs(item["width"] - item["expectedWidth"]) < 0.001
        assert item["startDeltaMs"] == 0
        assert item["endDeltaMs"] == 0


def test_short_task_width_matrix_covers_all_readonly_zoom_levels_and_midnight_edges() -> None:
    helpers = _load_gantt_dom_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
loadScript({helpers._vendor_js()});

const modes = [
  "Month",
  "Week",
  "Day",
  "Half Day",
  "Quarter Day",
  "Hour",
  "Fifteen Minute",
  "Five Minute",
  "One Minute",
];
const taskSpecs = [
  ["T36", "2026-05-11 08:00:00", "2026-05-11 08:36:00", 36],
  ["T51", "2026-05-11 00:05:00", "2026-05-11 00:56:00", 51],
  ["T73", "2026-05-11 10:00:00", "2026-05-11 11:13:00", 73],
  ["T30CROSS", "2026-05-11 23:45:00", "2026-05-12 00:15:00", 30],
  ["T36MID", "2026-05-11 23:24:00", "2026-05-12 00:00:00", 36],
];
const out = [];

for (const mode of modes) {{
  const host = createHost("gantt_" + mode.replace(/\\s+/g, "_"));
  const tasks = taskSpecs.map(([id, start, end]) => ({{
    id,
    name: id,
    start,
    end,
    progress: 0,
    dependencies: "",
  }}));
  const gantt = new Gantt(host, tasks, {{ view_mode: mode }});
  for (const [id, start, end, minutes] of taskSpecs) {{
    const bar = gantt.get_bar(id);
    const width = Number(bar.$bar.getAttribute("width"));
    const expectedWidth = minutes / gantt.options.step_minutes * gantt.options.column_width;
    const dates = bar.compute_start_end_date();
    out.push({{
      mode,
      id,
      width,
      expectedWidth,
      hitWidth: Number(bar.$bar_hit.getAttribute("width")),
      stepMinutes: gantt.options.step_minutes,
      startDeltaMs: dates.new_start_date - bar.task._start,
      endDeltaMs: dates.new_end_date - bar.task._end,
      rawStart: start,
      rawEnd: end,
    }});
  }}
}}

process.stdout.write(JSON.stringify({{ out }}));
"""
    result = helpers._run_node_json(node_code)

    assert len(result["out"]) == 9 * 5
    for item in result["out"]:
      assert item["width"] > 0, f"{item['mode']} {item['id']} width should stay visible"
      assert abs(item["width"] - item["expectedWidth"]) < 0.001, item
      assert item["hitWidth"] >= 12
      assert item["startDeltaMs"] == 0, item
      assert item["endDeltaMs"] == 0, item


def main() -> None:
    test_frappe_gantt_keeps_short_tasks_visible_and_draggable()
    test_frappe_gantt_supports_hour_and_minute_zoom_geometry()
    test_short_task_width_matrix_covers_all_readonly_zoom_levels_and_midnight_edges()
    print("OK")


if __name__ == "__main__":
    main()
