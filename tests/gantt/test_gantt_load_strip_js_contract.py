"""负荷条带前端契约（fusion-gantt-load-strip，Node DOM 仿真）。

钉死点：Top 5 截断 +「另有 N 个资源」提示；空数组/无甘特几何条带整体隐藏；
unknown 格显示 ?（ratio None 不伪装 0%）；弹层从 allTasks 过滤该资源当天
任务、links 渲染（disabled 不出 a 标签带原因 title）；列 x 坐标与假期层同
像素公式（dayWidth 列宽）；按后端输出顺序保序（负荷降序由后端钉）。
HTML 断言走 buildLoadStripHtml/buildLoadPopupHtml 返回字符串（DOM shim
innerHTML 剥标签不可 querySelector——沿 buildTaskDetailHtml 模式）。
"""

from __future__ import annotations

import importlib.util
import json

from tests._support.paths import REPO_ROOT


def _load_gantt_helpers():
    helper_path = REPO_ROOT / "tests" / "gantt" / "test_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strip_js():
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_load_strip.js"))


def _rows_js(n_resources: int) -> str:
    rows = []
    for i in range(n_resources):
        rid = f"MC{i + 1}"
        rows.append(
            {
                "date": "2026-06-15",
                "resource_id": rid,
                "resource_label": f"{rid} 车床",
                "hours": float(n_resources - i),
                "capacity_hours": 8.0,
                "ratio": round((n_resources - i) / 8.0, 4),
                "severity": "normal",
                "links": [
                    {"label": "查看资源排班", "url": f"/scheduler/resource-dispatch?machine_id={rid}",
                     "target_page": "resource_dispatch", "disabled": False, "disabled_reason": ""},
                    {"label": "查看资源负荷报表", "url": "", "target_page": "utilization_report",
                     "disabled": True, "disabled_reason": "模拟预览不能直接跳转到正式工作台，请回到排产分析查看。"},
                ],
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def _setup_js(helpers, rows_js: str) -> str:
    return f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttLoadStrip");

loadScript({helpers._gantt_js()});
loadScript({helpers._gantt_zoom_js()});
loadScript({_strip_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
state.cfg = {{ view: "machine" }};
state.allTasks = [
  {{ id: "T1", name: "T1", start: "2026-06-15 08:00:00", end: "2026-06-15 10:00:00", progress: 0, dependencies: "",
     meta: {{ batch_id: "B1", machine_id: "MC1", operation_label: "铣面", planned_time_label: "06-15 08:00 ～ 10:00" }} }},
  {{ id: "T2", name: "T2", start: "2026-06-16 08:00:00", end: "2026-06-16 10:00:00", progress: 0, dependencies: "",
     meta: {{ batch_id: "B2", machine_id: "MC1", operation_label: "钻孔", planned_time_label: "06-16 08:00 ～ 10:00" }} }},
];
// 甘特实例桩：只要 gantt_start + options（getGanttScale 消费面）
state.gantt = {{ gantt_start: new Date("2026-06-15 00:00:00"), options: {{ step_minutes: 1440, column_width: 38 }} }};
const rows = {rows_js};
const geo = {{ start: state.gantt.gantt_start, stepMinutes: 1440, columnWidth: 38, dayWidth: 38 }};
ns.initResourceLoad(rows);
"""


def _run(helpers, rows_js: str, body: str) -> dict:
    return helpers._run_node_json(_setup_js(helpers, rows_js) + body)


def test_top5_truncation_with_more_notice_and_order_preserved():
    helpers = _load_gantt_helpers()
    result = _run(helpers, _rows_js(7), """
const html = ns.buildLoadStripHtml(rows, geo);
const labels = [];
const labelRe = /aps-load-strip-label[^>]*>([^<]+)</g;
let m;
while ((m = labelRe.exec(html)) !== null) labels.push(m[1]);
process.stdout.write(JSON.stringify({
  labels, more: html.indexOf("另有 2 个资源有排程") >= 0,
  source: html.indexOf("按全局工作日历估算，未按单台设备/单人细分") >= 0,
}));
""")
    assert result["labels"] == ["MC1 车床", "MC2 车床", "MC3 车床", "MC4 车床", "MC5 车床"]  # 保序 Top 5
    assert result["more"] is True
    assert result["source"] is True  # 容量来源文案（4.6 明示）


def test_empty_rows_or_missing_geometry_hide_strip():
    helpers = _load_gantt_helpers()
    result = _run(helpers, "[]", """
ns.renderLoadStrip();
const host = document.getElementById("ganttLoadStrip");
const emptyHidden = host.classList.contains("is-hidden");
// 无甘特几何（gantt 未渲染）同样隐藏
state.gantt = null;
ns.initResourceLoad([{ date: "2026-06-15", resource_id: "MC1", resource_label: "MC1",
  hours: 1, capacity_hours: 8, ratio: 0.125, severity: "normal", links: [] }]);
ns.renderLoadStrip();
process.stdout.write(JSON.stringify({
  emptyHidden, noGeoHidden: host.classList.contains("is-hidden"),
}));
""")
    assert result["emptyHidden"] is True
    assert result["noGeoHidden"] is True


def test_unknown_ratio_cell_shows_question_mark_not_zero():
    helpers = _load_gantt_helpers()
    rows = json.dumps([{
        "date": "2026-06-15", "resource_id": "MC1", "resource_label": "MC1",
        "hours": 2.0, "capacity_hours": None, "ratio": None,
        "severity": "unknown", "links": [],
    }], ensure_ascii=False)
    result = _run(helpers, rows, """
const html = ns.buildLoadStripHtml(rows, geo);
process.stdout.write(JSON.stringify({ html }));
""")
    assert "aps-load-cell-unknown" in result["html"]
    assert ">?</button>" in result["html"]
    assert "利用率暂时算不了" in result["html"]
    assert "0%" not in result["html"]


def test_cell_geometry_uses_holiday_layer_pixel_formula():
    helpers = _load_gantt_helpers()
    rows = json.dumps([
        {"date": "2026-06-15", "resource_id": "MC1", "resource_label": "MC1", "hours": 1.0,
         "capacity_hours": 8.0, "ratio": 0.125, "severity": "normal", "links": []},
        {"date": "2026-06-17", "resource_id": "MC1", "resource_label": "MC1", "hours": 1.0,
         "capacity_hours": 8.0, "ratio": 0.125, "severity": "normal", "links": []},
    ], ensure_ascii=False)
    result = _run(helpers, rows, """
const html = ns.buildLoadStripHtml(rows, geo);
const xs = [];
const re = /left:(\\d+)px;width:(\\d+)px/g;
let m;
while ((m = re.exec(html)) !== null) xs.push([Number(m[1]), Number(m[2])]);
process.stdout.write(JSON.stringify({ xs }));
""")
    # day 视图 step_minutes=1440/column_width=38：6-15 是 gantt_start 当天 x=0，6-17 偏移 2 天 = 76px；宽 = dayWidth-2 = 36
    assert result["xs"] == [[0, 36], [76, 36]]


def test_popup_filters_day_tasks_and_renders_links():
    helpers = _load_gantt_helpers()
    result = _run(helpers, _rows_js(1), """
const html = ns.buildLoadPopupHtml({ id: "MC1", label: "MC1 车床" }, rows[0]);
process.stdout.write(JSON.stringify({ html }));
""")
    assert "B1" in result["html"] and "铣面" in result["html"]  # 当天任务在列
    assert "B2" not in result["html"]  # 6-16 的任务不混入 6-15 弹层
    assert 'href="/scheduler/resource-dispatch?machine_id=MC1"' in result["html"]
    assert "模拟预览" in result["html"]  # disabled 链接出原因 title
    assert 'href=""' not in result["html"]  # disabled 不渲染 a 标签
