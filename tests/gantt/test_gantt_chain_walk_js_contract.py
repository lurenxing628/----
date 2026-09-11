"""沿链巡检 JS 契约（fusion-chain-walk-navigation，Node DOM 仿真）。

钉死点：工艺链索引建在 allTasks 原始 dependencies 上（depsMode=critical 改写
currentTasks 不影响反查——反例）；walkProcess 沿边走链头尾停；walkCritical 沿
critical.ids 正序、范围外 id 跳过+「已跳过 N 道」提示、该方向无可达停原地提示；
视图外目标详情照渲+提示；keydown ←/→ 走关键链且 INPUT 聚焦跳过；focusBatch
幂等赋值（连续巡检同批次不清聚焦）；按钮态/徽标断言走 buildTaskDetailHtml
返回字符串（DOM shim innerHTML 剥标签不可点）。
"""

from __future__ import annotations

import importlib.util

from tests._support.paths import REPO_ROOT


def _load_gantt_helpers():
    helper_path = REPO_ROOT / "tests" / "gantt" / "test_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _chain_walk_js(helpers):
    import json

    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_chain_walk.js"))


def _setup_js(helpers) -> str:
    return f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
createHost("ganttZoomWarning");
createHost("ganttTaskDetail");

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
loadScript({_chain_walk_js(helpers)});
loadScript({helpers._gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
function mkTask(id, prev, batch, start, end) {{
  return {{
    id: id, name: id, start: start, end: end, progress: 0,
    dependencies: prev || "",
    meta: {{ batch_id: batch, part_label: "P-" + id, operation_label: id,
             planned_time_label: start + " ～ " + end, detail_links: [] }},
  }};
}}
// 工艺链：A1→A2→A3（批次 BA）；独立任务 C1（批次 BC）
state.allTasks = [
  mkTask("A1", "", "BA", "2026-05-01 08:00:00", "2026-05-01 09:00:00"),
  mkTask("A2", "A1", "BA", "2026-05-01 09:00:00", "2026-05-01 10:00:00"),
  mkTask("A3", "A2", "BA", "2026-05-01 10:00:00", "2026-05-01 11:00:00"),
  mkTask("C1", "", "BC", "2026-05-01 08:00:00", "2026-05-01 09:00:00"),
];
state.currentTasks = state.allTasks.slice();
// 关键链含范围外 id X9（不在 allTasks——按整版回溯 vs 窗口截取）
state.critical = {{ ids: ["A1", "X9", "C1"], edges: [], available: true }};
state.ui.depsMode = "critical";
ns.chainWalk.rebuildChainIndex();
ns.chainWalk.bindChainWalk();
"""


def _run(helpers, body: str) -> dict:
    return helpers._run_node_json(_setup_js(helpers) + body)


def test_process_walk_follows_original_dependencies_not_rewritten():
    """Walk the frozen process order, never legacy rewritten dependencies."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(), tasks=data.tasks, P=h.runtime.PlanProcessOrder;
tasks.forEach(task=>task.dependencies='X9'); const before=h.clone(data);
const middle=P.relationships(data,{task:tasks[1],before:false});
h.equal(middle.previous.map(row=>row.task_ref),[tasks[0].task_ref]);h.equal(middle.next.map(row=>row.task_ref),[tasks[2].task_ref]);
const picked=[]; const tree=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task:tasks[1],before:false},onRelated:ref=>picked.push(ref)});
h.walk(tree).find(n=>n.type==='button'&&String(n.props['aria-label']).startsWith('后序 ')).props.onClick();
h.walk(tree).find(n=>n.type==='button'&&String(n.props['aria-label']).startsWith('前序 ')).props.onClick();
h.equal(picked,[tasks[2].task_ref,tasks[0].task_ref]);assert.strictEqual(P.relationships(data,{task:tasks[0]}).previous.length,0);h.equal(data,before);
""")


def test_critical_walk_skips_out_of_range_ids_with_notice():
    """Critical walk retired; an out-of-scope frozen successor is not skipped."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(), original=data.tasks.slice();data.tasks=[original[0],original[2]];data.task_count=2;data.scope.range_start=original[0].start;
const P=h.runtime.PlanProcessOrder;assert(P.validate(data.projections.process_order,data));const before=h.clone(data),picked=[];
const relations=P.relationships(data,{task:original[0]});h.equal(relations.next,[{task_ref:original[1].task_ref,task:null}]);
const tree=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task:original[0]},onRelated:ref=>picked.push(ref)});
const button=h.walk(tree).find(n=>n.type==='button'&&n.props['aria-label']==='后序安排在当前读取范围外');
assert(button);assert.strictEqual(h.text(button),'读取完整计划并定位后序');button.props.onClick();h.equal(picked,[original[1].task_ref]);h.equal(data,before);
""")


def test_critical_walk_dead_end_stays_with_honest_notice():
    """Unavailable/unplanned process relations never invent a next task."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(), task=data.tasks[2], before=h.clone(data),picked=[];
const tree=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task},onRelated:ref=>picked.push(ref)});
assert(h.text(tree).includes('无后序工序'));assert(!h.walk(tree).some(n=>n.type==='button'&&String(n.props['aria-label']).startsWith('后序')));
h.equal(picked,[]);h.equal(data,before);
data.projections.process_order={state:'unavailable',basis:null,items:[],issues:[{code:'process_order_unavailable',message:'冻结工艺关系无法核实。'}]};
const unavailable=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task},onRelated:ref=>picked.push(ref)});
assert(h.text(unavailable).includes('冻结工艺关系无法核实。'));assert(!h.text(unavailable).includes('无后序工序'));h.equal(picked,[]);
""")


def test_critical_walk_backward_dead_end_notice_says_previous():
    """An unknown predecessor is labelled previous, never next or zero."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(), task=data.tasks[0], picked=[];
data.projections.process_order.items[0].predecessor_operation_refs=[h.reference(999)];
assert(h.runtime.PlanProcessOrder.validate(data.projections.process_order,data));const before=h.clone(data);
const tree=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task},onRelated:ref=>picked.push(ref)});
assert(h.text(tree).includes('前序未在本计划安排'));assert(!h.text(tree).includes('无前序工序'));
assert(!h.walk(tree).some(n=>n.type==='button'&&String(n.props['aria-label']).startsWith('前序')));h.equal(picked,[]);h.equal(data,before);
""")


def test_filtered_out_target_renders_detail_with_view_notice():
    """Selection remains inspectable without clearing the current search."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(), selected={task:data.tasks[1]}, before=h.clone(data);
const gantt=h.gantt(data,{query:'A1',selected});
assert(!gantt.nodes.some(n=>n.props['data-plan-task']===selected.task.task_ref));
const locate=gantt.nodes.find(n=>n.props['aria-label']==='定位选中任务');assert.strictEqual(locate.props.disabled,true);
assert.strictEqual(gantt.nodes.find(n=>n.type==='input'&&n.props.type==='search').props.value,'A1');
const detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected,query:'A1'});
assert(h.text(detail).includes('A2'));assert(h.text(detail).includes(h.runtime.PlanGanttModel.timeLabel(selected.task.start)));
h.equal(gantt.queries,[]);h.equal(gantt.selections,[]);h.equal(data,before);
""")


def test_keydown_arrows_walk_critical_and_input_focus_skipped():
    """Global critical arrows retired; current shortcuts respect input focus."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(), selected={task:data.tasks[0]}, result=h.gantt(data,{selected}), root=result.tree;
const event=(key,input=false)=>({key,target:{closest:()=>input ? {}:null},preventDefault(){this.prevented=true;}});
root.props.onKeyDown(event('ArrowRight'));root.props.onKeyDown(event('ArrowLeft'));h.equal(result.selections,[]);
const inputZoom=event('+',true);root.props.onKeyDown(inputZoom);assert(!inputZoom.prevented);h.equal(h.updates(),[]);
const plus=event('+');root.props.onKeyDown(plus);assert(plus.prevented);assert(h.updates().some(row=>row.index===2&&row.value===2));
const search=result.nodes.find(n=>n.type==='input'&&n.props.type==='search'),next=event('Enter');
search.props.onKeyDown(next);assert(next.prevented);h.equal(result.selections.map(row=>row.task.task_ref),[data.tasks[1].task_ref]);
const backward=h.gantt(data,{selected:{task:data.tasks[1]}}),shift=event('Enter');shift.shiftKey=true;
backward.nodes.find(n=>n.type==='input'&&n.props.type==='search').props.onKeyDown(shift);
h.equal(backward.selections.map(row=>row.task.task_ref),[data.tasks[0].task_ref]);
""")


def test_focus_batch_idempotent_and_walk_buttons_in_html():
    """Current selected-task identity is idempotent; relations use real buttons."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(), task=data.tasks[1], before=h.clone(data), result=h.gantt(data,{query:'A2'});
const bar=result.nodes.find(n=>n.props['data-plan-task']===task.task_ref);bar.props.onClick();bar.props.onClick();
h.equal(result.selections.map(row=>[row.task.task_ref,row.before]),[[task.task_ref,false],[task.task_ref,false]]);h.equal(result.queries,[]);
for(const callback of [undefined,()=>{}]) {
 const middle=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task},onRelated:callback});
 const buttons=h.walk(middle).filter(n=>n.type==='button'&&/^(前序|后序) /.test(n.props['aria-label']||''));assert.strictEqual(buttons.length,2);
 assert(buttons.every(button=>button.props.disabled===!callback));
}
const head=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task:data.tasks[0]},onRelated:()=>{}});
assert(h.text(head).includes('无前序工序'));assert(!h.text(head).includes('关键链'));h.equal(data,before);
""")
