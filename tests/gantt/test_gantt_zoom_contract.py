"""LEG-035..041: legacy zoom is unreachable; the shipped new model/canvas retains minute precision."""

from __future__ import annotations

import json
import subprocess

from core.infrastructure.database import get_connection
from tests._support.paths import REPO_ROOT
from tests.gantt.test_gantt_url_persistence import _assert_retired, _business_state, _canonical_workspace, _seed


def _run_model(code):
    setup = """
const fs = require('fs'), path = require('path'), vm = require('vm');
const fills = [], canvas = { getBoundingClientRect: () => ({ width: 720, height: 56 }),
  getContext: () => new Proxy({ fillRect: (x,y,w,h) => fills.push({x,y,w,h}) }, { get: (o,k) => o[k] || (() => {}) }) };
const runtime = vm.createContext({ window: {}, console, document: { documentElement: {} },
  React: { useRef: () => ({ current: canvas }), useLayoutEffect: fn => fn(), createElement: () => ({}) },
  MutationObserver: class { observe() {} disconnect() {} },
  ResizeObserver: class { observe() {} disconnect() {} },
  getComputedStyle: () => ({ getPropertyValue: () => '#000' }) });
runtime.window = runtime;
"""
    setup += "const root = " + json.dumps(str(REPO_ROOT)) + ";\n"
    setup += """
for (const name of ['PointContract.js', 'PointGanttModel.js', 'PlanGanttModel.js', 'PlanGanttCanvas.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'static/workbench/app', name), 'utf8'), runtime, { filename: name });
}
const M = runtime.PlanGanttModel;
"""
    result = subprocess.run(["node", "-"], input=setup + code, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_zoom_spec_contains_first_version_levels_and_frappe_mapping(app_client, db_env) -> None:
    _seed(db_env)
    before = _business_state(app_client)
    levels = ["month", "week", "day", "half-day", "quarter-day", "hour", "fifteen-minute", "five-minute", "one-minute"]
    for level in levels:
        _assert_retired(app_client, {"version": "3", "gantt_zoom": level})
    for level in ("Day", "Week", "Month"):
        _assert_retired(app_client, {"version": "3", "gantt_vm": level})
    result = _run_model("""
const steps = [720, 360, 60, 15, 5, 1], start = M.instant('2026-05-11T00:00:00');
const actual = steps.map(minutes => {
  const ticks = M.ticks(start, start + minutes * 60000 * 8, 1000, 0, 1000);
  return { minutes, delta: ticks[1].at - ticks[0].at, increasing: ticks.every((v,i) => !i || v.at > ticks[i-1].at) };
});
process.stdout.write(JSON.stringify(actual));
""")
    assert [row["minutes"] for row in result] == [720, 360, 60, 15, 5, 1]
    for row in result:
        assert row["delta"] == row["minutes"] * 60000 and row["increasing"]
    assert _business_state(app_client) == before


def test_vendor_minute_modes_generate_increasing_dates_without_losing_short_task_width(app_client, db_env) -> None:
    _seed(db_env)
    with get_connection(db_env) as conn:
        conn.execute("UPDATE Schedule SET start_time='2026-05-11 08:00:00',end_time='2026-05-11 08:36:00' WHERE version=3")
    before = _business_state(app_client)
    _, payload = _canonical_workspace(app_client, {"version": "3", "start_date": "2026-05-11", "end_date": "2026-05-11"})
    data = payload["data"]
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["start"] == "2026-05-11T08:00:00" and data["tasks"][0]["end"] == "2026-05-11T08:36:00"
    result = _run_model("const data = " + json.dumps(data, ensure_ascii=False) + ";\n" + """
const original = JSON.stringify(data), out = {};
for (const minutes of [60, 15, 5, 1]) {
  const model = M.layout(data, 'machine', '', false, 720), row = model.rows[0];
  const item = row.items[0], ticks = M.ticks(model.start, model.start + minutes * 60000 * 8, 1000, 0, 1000);
  const startCount = fills.length;
  runtime.PlanGanttCanvas.DenseRow({ row, model, width: 720, viewport: 720, left: 0,
    selectedRef: '', risks: new Map(), onSelect: () => {}, onHover: () => {} });
  const painted = fills.slice(startCount);
  out[minutes] = { delta: ticks[1].at - ticks[0].at, duration: item.end - item.start,
    columnWidth: 60000 / (model.end - model.start) * 720, painted, taskRef: item.task.task_ref };
}
process.stdout.write(JSON.stringify({ out, unchanged: JSON.stringify(data) === original }));
""")
    assert result["unchanged"]
    for minutes in (60, 15, 5, 1):
        row = result["out"][str(minutes)]
        assert row["delta"] == minutes * 60000 and row["duration"] == 36 * 60000
        assert row["taskRef"] == data["tasks"][0]["task_ref"]
        assert len(row["painted"]) == 1
        assert abs(row["painted"][0]["w"] - (36 * row["columnWidth"] - 4)) < 0.001
        assert row["painted"][0]["w"] > 0
    assert _business_state(app_client) == before
