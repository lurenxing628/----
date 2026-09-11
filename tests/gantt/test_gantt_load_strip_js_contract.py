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
    """The retired Top-5 strip is replaced by an ordered, paged resource table."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture();data.projections.occupancy.resources=Array.from({length:25},(_,i)=>({resource_ref:h.reference(500+i),kind:'machine',label:'MC'+(i+1)+' 车床',arranged_hours:2,occupied_hours:2,available_hours:8,overlap_hours:0,has_overlap:false,utilization:0.25,issues:[]}));
const before=h.clone(data), seen=[];
for(const page of [0,1]) {
 const tree=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data,onResource:()=>{}},{ProjectionTables:{0:'load',1:page}});
 const rows=h.walk(tree).filter(n=>n.type==='tbody').flatMap(n=>h.walk(n).filter(row=>row.type==='tr'));
 assert.strictEqual(rows.length,page===0?20:5);seen.push(...rows.map(row=>h.text(h.walk(row).find(n=>n.type==='button'))));
 assert(h.text(tree).includes('25 项'));assert(h.text(tree).includes('只统计所选计划在此时间范围内的安排'));
 const next=h.walk(tree).find(n=>n.props['aria-label']==='分析下一页');assert.strictEqual(next.props.disabled,page===1);
 if(!page){next.props.onClick();assert(h.updates().some(row=>row.name==='ProjectionTables'&&row.index===1&&row.value===1));}
}
h.equal(seen,data.projections.occupancy.resources.map(row=>row.label));h.equal(data,before);
""")


def test_empty_rows_or_missing_geometry_hide_strip():
    """Unknown and genuinely empty occupancy must not collapse to one state."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture();
for(const state of ['available','unavailable','partial']) {
 data.projections.occupancy={state,resources:[],issues:[]};const before=h.clone(data);
 const tree=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data},{ProjectionTables:{0:'load'}}),text=h.text(tree);
 assert(text.includes(state==='available'?'所选时间范围内没有记录。':'资料未记录或无法核实。'));
 assert(!text.includes(state==='available'?'资料未记录或无法核实。':'所选时间范围内没有记录。'));
 assert(!h.walk(tree).some(n=>n.props.id==='ganttLoadStrip'));assert(!text.includes('0%'));h.equal(data,before);
}
""")


def test_unknown_ratio_cell_shows_question_mark_not_zero():
    """Current null capacity remains unknown, never zero percent or a meter."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture();data.projections.occupancy={state:'partial',issues:[],resources:[{resource_ref:h.reference(200),kind:'machine',label:'MC1',arranged_hours:2,occupied_hours:2,available_hours:null,overlap_hours:0,has_overlap:false,utilization:null,issues:[{code:'calendar_unavailable',message:'日历资料无法核实。'}]}]};
const before=h.clone(data), tree=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data},{ProjectionTables:{0:'load'}}), text=h.text(tree);
assert(text.includes('无法核实'));assert(!text.includes('0%'));assert(!h.walk(tree).some(n=>n.props.className==='plan-meter'));
const cells=h.walk(tree).filter(n=>n.type==='tbody').flatMap(n=>h.walk(n).filter(row=>row.type==='td'));assert.strictEqual(h.text(cells[3]),'无法核实');assert(h.text(cells[5]).includes('无法核实'));
h.equal(data,before);
""")


def test_cell_geometry_uses_holiday_layer_pixel_formula():
    """No Frappe day strip; current calendar retains exact half-open windows."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture(), windows=[{start:'2026-06-15T00:00:00',end:'2026-06-16T00:00:00',allow_normal:true,allow_urgent:true,efficiency:1},{start:'2026-06-17T00:00:00',end:'2026-06-18T00:00:00',allow_normal:false,allow_urgent:true,efficiency:0.5}];
data.projections.calendar={state:'available',issues:[],resources:[{resource_ref:h.reference(200),kind:'machine',label:'MC1',available_hours:48,normal_effective_hours:24,urgent_effective_hours:36,windows,issues:[]}]};
const before=h.clone(data), M=h.runtime.PlanGanttModel;
const tree=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data},{ProjectionTables:{0:'calendar'},CalendarWindows:{0:true}}), text=h.text(tree);
for(const window of windows) {assert(text.includes(M.timeLabel(window.start)));assert(text.includes(M.timeLabel(window.end)));assert.strictEqual(M.instant(window.end)-M.instant(window.start),86400000);}
assert.strictEqual(M.instant(windows[1].start)-M.instant(windows[0].start),2*86400000);assert(text.includes('普通禁止'));assert(text.includes('急件允许'));assert(text.includes('效率 0.5'));
assert(!h.walk(tree).some(n=>String(n.props.className||'').includes('aps-load-cell')));h.equal(data,before);
""")


def test_popup_filters_day_tasks_and_renders_links(app_client):
    """Current exact read scope drives occupancy and resource selection."""
    from tests._support.gantt_current import plan_fixture, read_workspace
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, context, full, before = plan_fixture(app_client)
    context = dict(context, range_start="2026-05-04T10:00:00", range_end="2026-05-04T11:00:00")
    payload = read_workspace(app_client, context)
    assert payload["data"]["task_count"] == 1
    assert payload["data"]["tasks"][0]["process_label"] == "钻孔"
    assert payload["data"]["plan_span"] == full["data"]["plan_span"]
    assert all(row["label"] not in ("设备二", "人员二") for row in payload["data"]["projections"]["occupancy"]["resources"])
    run_current_js(r"""
const data=sourceData.data, picked=[], before=h.clone(data);
const tree=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data,onResource:label=>picked.push(label)},{ProjectionTables:{0:'load'}});
const table=h.walk(tree).find(n=>n.type==='tbody'), buttons=h.walk(table).filter(n=>n.type==='button');
assert.strictEqual(buttons.length,2);buttons.forEach(button=>button.props.onClick());h.equal(picked,['设备一','人员一']);
assert(!h.walk(tree).some(n=>n.type==='a'&&n.props.href===''));assert(!h.text(tree).includes('设备二'));h.equal(data,before);
""", payload)
    assert _business_state(app_client) == before
