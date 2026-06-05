"""回归测试：在 Node DOM shim 下加载 gantt.js/gantt_zoom.js，校验 zoom.ZOOM_SPECS 缩放级别顺序（month..one-minute）与各级 stepMinutes（half-day=720…one-minute=1），normalizeZoomLevel 把旧 Day/Week/Month 映射到新 key；并用 frappe-gantt vendor 验证分钟级 view_mode 生成递增日期且短任务（36 分钟）条形宽度按列宽缩放不丢失。"""

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


def test_zoom_spec_contains_first_version_levels_and_frappe_mapping() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
loadScript({json.dumps(str(REPO_ROOT / "static" / "js" / "gantt.js"))});
loadScript({json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_zoom.js"))});

const zoom = window.__APS_GANTT__.zoom;
const levels = Object.keys(zoom.ZOOM_SPECS);
const specs = levels.map((level) => zoom.getZoomSpec(level));

process.stdout.write(JSON.stringify({{
  levels,
  specs,
  legacyDay: zoom.normalizeZoomLevel("Day"),
  legacyWeek: zoom.normalizeZoomLevel("Week"),
  legacyMonth: zoom.normalizeZoomLevel("Month"),
}}));
"""
    result = helpers._run_node_json(node_code)

    assert result["levels"] == [
        "month",
        "week",
        "day",
        "half-day",
        "quarter-day",
        "hour",
        "fifteen-minute",
        "five-minute",
        "one-minute",
    ]
    step_by_level = {item["level"]: item["stepMinutes"] for item in result["specs"]}
    assert step_by_level["half-day"] == 720
    assert step_by_level["quarter-day"] == 360
    assert step_by_level["hour"] == 60
    assert step_by_level["fifteen-minute"] == 15
    assert step_by_level["five-minute"] == 5
    assert step_by_level["one-minute"] == 1
    assert result["legacyDay"] == "day"
    assert result["legacyWeek"] == "week"
    assert result["legacyMonth"] == "month"


def test_vendor_minute_modes_generate_increasing_dates_without_losing_short_task_width() -> None:
    helpers = _load_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
loadScript({helpers._vendor_js()});

const modes = ["Hour", "Fifteen Minute", "Five Minute", "One Minute"];
const out = {{}};
for (const mode of modes) {{
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
  out[mode] = {{
    dateDeltaMs: gantt.dates[1] - gantt.dates[0],
    stepMs: gantt.options.step_ms,
    width: Number(bar.$bar.getAttribute("width")),
    columnWidth: gantt.options.column_width,
    stepMinutes: gantt.options.step_minutes,
  }};
}}
process.stdout.write(JSON.stringify(out));
"""
    result = helpers._run_node_json(node_code)

    assert result["Hour"]["dateDeltaMs"] == 60 * 60 * 1000
    assert result["Fifteen Minute"]["dateDeltaMs"] == 15 * 60 * 1000
    assert result["Five Minute"]["dateDeltaMs"] == 5 * 60 * 1000
    assert result["One Minute"]["dateDeltaMs"] == 60 * 1000
    assert abs(result["One Minute"]["width"] - 36 * result["One Minute"]["columnWidth"]) < 0.001
    for item in result.values():
        assert item["width"] > 0


def main() -> None:
    test_zoom_spec_contains_first_version_levels_and_frappe_mapping()
    test_vendor_minute_modes_generate_increasing_dates_without_losing_short_task_width()
    print("OK")


if __name__ == "__main__":
    main()
