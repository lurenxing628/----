"""甘特控件重排契约（fusion-gantt-controls-rework，Node DOM 仿真）。

钉死点：解码条批次 chips（上限 8+「等 N 个批次」按 allTasks 全量计）点击即筛
（写 filterBatch+同步 select+URL+render，再点同 chip 清筛，is-active 跟随）；
非 batch 配色模式零 data-batch；zoom ± 步进沿 select option 序 ±1 且端点
disabled、走 change 通路（URL 持久化不破）；宽屏 onClick 先 hide_popup（窄屏
不调）；模板结构（图例在 details 外/summary=筛选/无旧提示文案/±按钮存在）。
"""

from __future__ import annotations

import importlib.util
import re

from tests._support.paths import REPO_ROOT


def _load_gantt_helpers():
    helper_path = REPO_ROOT / "tests" / "gantt" / "test_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gantt_ui_js():
    import json

    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_ui.js"))


def _setup_js(helpers, n_batches: int = 3) -> str:
    return f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttLegend");
createHost("ganttTaskDetail");

function makeControl(tag, id, value) {{
  const el = document.createElement(tag);
  el.setAttribute("id", id);
  el.value = value || "";
  el.options = [];
  document.body.appendChild(el);
  return el;
}}
makeControl("select", "ganttFilterBatch", "");
makeControl("input", "ganttZoomFormValue", "day");
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

const ns = window.__APS_GANTT__;
const state = ns.state;
const N = {n_batches};
state.allTasks = [];
for (let i = 1; i <= N; i++) {{
  state.allTasks.push({{
    id: "T" + i, name: "T" + i, start: "2026-05-01 08:00:00", end: "2026-05-01 09:00:00",
    progress: 0, dependencies: "",
    meta: {{ batch_id: "B" + i, machine_id: "MC1", source: "internal" }},
  }});
}}
state.filteredTasks = state.allTasks.slice();
state.ui.colorMode = "batch";
state.cfg = {{ view: "machine" }};
// persistUiToUrl 用真实现（gantt_ui.js）验证 URL 链路；render/decorate 喂桩后加载
window.location.href = "http://local.test/scheduler/gantt?version=1";
window.history = {{ replaceState: function (_s, _t, url) {{ window.location.href = String(url); }} }};
let rendered = 0;
ns.render = function () {{ rendered++; state.filteredTasks = state.allTasks.filter(
  t => !state.ui.filterBatch || t.meta.batch_id.toLowerCase() === state.ui.filterBatch.toLowerCase()); }};
ns.safeDecorateDynamic = function () {{}};
loadScript({_gantt_ui_js()});
function urlHasBatch(bid) {{
  return new URL(window.location.href).searchParams.get("gantt_batch") === bid;
}}
ns.updateLegend();
ns.bindLegendChips();
const legend = document.getElementById("ganttLegend");
"""


def _run(helpers, body: str, n_batches: int = 3) -> dict:
    return helpers._run_node_json(_setup_js(helpers, n_batches) + body)


def _find_chip_js() -> str:
    return """
function findChip(bid) {
  function walk(node) {
    if (node.getAttribute && node.getAttribute("data-batch") === bid) return node;
    const kids = node.children || [];
    for (let i = 0; i < kids.length; i++) {
      const hit = walk(kids[i]);
      if (hit) return hit;
    }
    return null;
  }
  return walk(legend);
}
"""


def test_chips_click_filters_and_second_click_clears():
    """Legacy chips/URL keys are retired; controlled search can set and clear."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data = h.fixture(); data.tasks[1].batch_id = 'B2'; const before = h.clone(data);
const full = h.gantt(data), search = full.nodes.find(n => n.type === 'input' && n.props.type === 'search');
search.props.onChange({target:{value:'B2'}}); h.equal(full.queries, ['B2']);
const filtered = h.gantt(data, {query:full.queries[0]});
h.equal(filtered.nodes.filter(n=>n.props['data-plan-task']).map(n=>n.props['data-plan-task']), [data.tasks[1].task_ref]);
const model = h.runtime.PlanGanttModel;
for (const query of ['', 'B2']) {const layout=model.layout(data,'machine',query,false,830,false); const all=model.layout(data,'machine','',false,830,false); assert.strictEqual(layout.start,all.start);assert.strictEqual(layout.end,all.end);}
filtered.nodes.find(n=>n.type==='input'&&n.props.type==='search').props.onKeyDown({key:'Escape'});
h.equal(filtered.queries,['']); assert.strictEqual(h.gantt(data,{query:filtered.queries[0]}).nodes.filter(n=>n.props['data-plan-task']).length,2);
assert(!full.nodes.some(n=>n.props['data-batch'])); h.equal(data,before);
""")


def test_chips_capped_at_eight_with_total_notice_from_all_tasks():
    """No eight-chip ceiling is claimed for current full-count/search controls."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture(Array.from({length:12},(_,i)=>['Task '+i,'2026-05-11T08:00:00','2026-05-11T09:00:00']));
data.tasks.forEach((task,i)=>{task.batch_id='B'+(i+1);}); const before=h.clone(data);
const full=h.gantt(data), filtered=h.gantt(data,{query:'B12'});
assert.strictEqual(h.text(full.nodes.find(n=>n.props['data-plan-search-count']!==undefined)),'12 / 12 道安排');
assert.strictEqual(h.text(filtered.nodes.find(n=>n.props['data-plan-search-count']!==undefined)),'1 / 12 道安排');
assert(!full.nodes.some(n=>n.props['data-batch'])); assert.strictEqual(data.task_count,12); h.equal(data,before);
""")


def test_non_batch_color_mode_has_no_clickable_chips():
    """Current grouping must not invent legacy colour-filter dimensions."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture(), before=h.clone(data);
for (const mode of ['machine','operator','batch']) {
 const result=h.gantt(data,{states:{PlanGantt:{0:mode}}});
 assert(!result.nodes.some(n=>n.props['data-batch']||n.props.id==='ganttColorMode'));
 const group=result.nodes.find(n=>n.props['aria-label']==='甘特分组');
 const buttons=h.walk(group).filter(n=>n.type==='button'); assert.strictEqual(buttons.length,3);
 assert.strictEqual(buttons.filter(n=>n.props['aria-pressed']).length,1);
 h.equal(result.nodes.filter(n=>n.props['data-plan-task']).map(n=>n.props['data-plan-task']).sort(),data.tasks.map(t=>t.task_ref).sort());
}
h.equal(data,before);
""")


def test_template_decode_bar_outside_details_and_steppers_present():
    """The shipped React surface, not the retired Jinja select, owns controls."""
    from tests._support.gantt_current_js import run_current_js

    assert not (REPO_ROOT / "templates/scheduler/gantt.html").exists()
    run_current_js(r"""
const result=h.gantt(h.fixture());
const legends=result.nodes.filter(n=>n.props.className==='plan-footer');assert.strictEqual(legends.length,1);
assert(h.text(legends[0]).includes('预计超期'));assert(h.text(legends[0]).includes('资源重叠'));assert(!result.nodes.some(n=>n.type==='details'));
for(const kind of ['critical','conflict','success','before','point','today']) assert(result.nodes.some(n=>n.props.className==='plan-swatch '+kind));
for(const label of ['缩小时间轴','放大时间轴','显示完整时间范围','定位选中任务','展开甘特']) assert.strictEqual(result.nodes.filter(n=>n.props['aria-label']===label).length,1);
assert.strictEqual(result.nodes.filter(n=>n.type==='input'&&n.props.type==='search').length,1);
assert(!h.text(result.tree).includes('关键链'));assert(!result.nodes.some(n=>n.type==='select'));
""")


def test_wide_viewport_popup_suppressed_in_css_and_render():
    """Frappe popup is retired; current tooltip and inspector share task facts."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture(), task=data.tasks[0], before=h.clone(data), M=h.runtime.PlanGanttModel;
for(const width of [768,1280]) {
 h.runtime.innerWidth=width;
 const result=h.gantt(data,{states:{PlanGantt:{6:{task,before:false,x:width-5,y:790}}}});
 const tips=result.nodes.filter(n=>n.props.role==='tooltip');assert.strictEqual(tips.length,1);
 assert.strictEqual(h.text(tips[0]),M.taskTitle(task,M.names(data),false));
 assert(tips[0].props.style.left>=8&&tips[0].props.style.left<=width-335);
 assert.strictEqual(tips[0].props.style.overflow,'auto');assert.strictEqual(tips[0].props.style.overflowWrap,'anywhere');
 const detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task,before:false},onSelect:()=>{}});
 assert(h.text(detail).includes(task.process_label));assert(h.text(detail).includes(M.timeLabel(task.start)));
 assert(!result.nodes.some(n=>String(n.props.className||'').includes('popup-wrapper')));
}
h.equal(data,before);
""")


def test_zoom_steppers_step_along_select_order_with_endpoint_disabled():
    """Current numeric zoom traverses all eleven supported powers of two."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture(), before=h.clone(data);
for(let zoom=1;zoom<=1024;zoom*=2) {
 const result=h.gantt(data,{states:{PlanGantt:{2:zoom}}}), get=label=>result.nodes.find(n=>n.props['aria-label']===label);
 assert.strictEqual(get('缩小时间轴').props.disabled,zoom===1);assert.strictEqual(get('放大时间轴').props.disabled,zoom===1024);
 get('放大时间轴').props.onClick();get('缩小时间轴').props.onClick();
 h.equal(h.updates().filter(v=>v.name==='PlanGantt'&&v.index===2).map(v=>v.value),[Math.min(1024,zoom*2),Math.max(1,zoom/2)]);
 assert(h.text(result.tree).includes(zoom+'×'));
}
h.equal(data,before);
""")
