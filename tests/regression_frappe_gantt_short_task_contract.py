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

const initial = {{
  T36: snapshot("T36"),
  T51: snapshot("T51"),
  T73: snapshot("T73"),
}};

const bar36 = gantt.get_bar("T36");
bar36.update_bar_position({{ width: 0.5 }});
const resized = snapshot("T36");
bar36.update_bar_position({{ x: 0 }});
const movedToZero = snapshot("T36");

process.stdout.write(JSON.stringify({{
  initial,
  resized,
  movedToZero,
}}));
"""
    result = helpers._run_node_json(node_code)
    initial = result["initial"]

    assert abs(initial["T36"]["width"] - 0.95) < 0.001
    assert abs(initial["T51"]["width"] - 1.3616666667) < 0.001
    assert abs(initial["T73"]["width"] - 1.9316666667) < 0.001
    assert abs((initial["T51"]["x"] - initial["T36"]["x"]) - 1.3616666667) < 0.001

    for task_id in ("T36", "T51", "T73"):
        task = initial[task_id]
        assert task["width"] > 0
        assert task["hitWidth"] >= 12
        assert task["leftX"] < task["rightX"]
        assert task["startDeltaMs"] == 0
        assert task["endDeltaMs"] == 0

    assert result["resized"]["width"] == 0.5
    assert result["resized"]["hitWidth"] >= 12
    assert result["movedToZero"]["x"] == 0


def test_short_task_fix_stays_inside_vendor_time_geometry() -> None:
    vendor_js = (REPO_ROOT / "static" / "js" / "frappe-gantt.min.js").read_text(encoding="utf-8")
    render_js = (REPO_ROOT / "static" / "js" / "gantt_render.js").read_text(encoding="utf-8")

    assert "this.duration=(this.task._end-this.task._start)/36e5/this.gantt.options.step" in vendor_js
    assert "compute_start_end_date(){const t=this.$bar" in vendor_js
    assert "new Date(this.gantt.gantt_start.getTime()+e*s)" in vendor_js
    assert "draw_hitbox()" in vendor_js
    assert ".bar-hit" not in render_js
    assert "min-width" not in render_js


def main() -> None:
    test_frappe_gantt_keeps_short_tasks_visible_and_draggable()
    test_short_task_fix_stays_inside_vendor_time_geometry()
    print("OK")


if __name__ == "__main__":
    main()
