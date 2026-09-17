"""保留关键链后端事实，检查当前甘特的只读选择、公开字段和降级边界。

旧 Frappe 描边、HTML 预览与关键链 tooltip 已退役，不把当前超期/重叠配色
当作关键链等价实现。旧 DOM 辅助仍留给原有引用者；本文件使用实际当前资产。
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tests._support.paths import REPO_ROOT


def _run_node_json(code: str) -> dict:
    completed = subprocess.run(
        ["node", "-"],
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"node execution failed rc={completed.returncode}\nstdout={completed.stdout[:1000]!r}\nstderr={completed.stderr[:1000]!r}"
        )
    return json.loads(completed.stdout or "{}")


def _outline_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_outline.js"))


def _vendor_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "frappe-gantt.min.js"))


def _gantt_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt.js"))


def _gantt_color_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_color.js"))


def _gantt_zoom_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_zoom.js"))


def _gantt_adapter_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_adapter.js"))


def _gantt_render_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_render.js"))


def _gantt_popup_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_popup.js"))


def _gantt_legend_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_legend.js"))


def _gantt_holidays_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_holidays.js"))


def _gantt_decorations_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_decorations.js"))


def _gantt_contract_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_contract.js"))


def _gantt_help_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_help.js"))


def test_outline_helper_contract_and_adapter_binding() -> None:
    """Current selection is geometry-neutral; no retired SVG adapter is loaded."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture(),before=h.clone(data),task=data.tasks[0];
for(const zoom of [1,2,64,1024]) {
 const plain=h.gantt(data,{states:{PlanGantt:{2:zoom}}}), selected=h.gantt(data,{selected:{task},states:{PlanGantt:{2:zoom}}});
 const a=plain.nodes.find(n=>n.props['data-plan-task']===task.task_ref),b=selected.nodes.find(n=>n.props['data-plan-task']===task.task_ref);
 assert(a&&b);h.equal(a.props.style,b.props.style);assert.strictEqual(b.props['aria-pressed'],true);assert(!a.props['aria-pressed']);
 assert(a.props.style.width>0&&Number.isFinite(a.props.style.left));b.props.onClick();h.equal(selected.selections.map(row=>row.task.task_ref),[task.task_ref]);
 for(const handler of ['onDrag','onMouseDown','onPointerDown','onDateChange'])assert.strictEqual(b.props[handler],undefined);
}
assert.strictEqual(h.runtime.__APS_GANTT_OUTLINE__,undefined);assert.strictEqual(h.runtime.__APS_GANTT__,undefined);h.equal(data,before);
""")


def test_live_render_syncs_outline_with_real_vendor_and_no_runtime_sweeps(app_client, db_env) -> None:
    from contextlib import closing

    from core.infrastructure.database import get_connection
    from core.models.workbench_plan_reference import WorkbenchPlanLocator
    from core.services.scheduler.config.config_service import ConfigService
    from core.services.system.system_config_service import SystemConfigService
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
    from tests._support.gantt_retirement import _business_state, _canonical_workspace
    from tests._support.gantt_scenario import VERSION, _seed_base

    with closing(get_connection(db_env)) as conn:
        _seed_base(conn)
        ConfigService(conn).ensure_defaults()
        SystemConfigService(conn).ensure_defaults(app_client.application.config["BACKUP_KEEP_DAYS"])
        conn.commit()
        reference = WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(VERSION, "adopted"))
    before = _business_state(app_client)
    # Old critical-chain double outlines, edit/resize hooks and named zoom modes
    # are retired, not reinterpreted as the new overdue/resource-conflict tones.
    for controls in ({"gantt_hcc": "1"}, {"gantt_hcc": "0"}, {"gantt_deps": "critical"},
                     {"gantt_vm": "Day"}, {"gantt_vm": "Week"}, {"gantt_vm": "Month"}):
        response = app_client.get("/scheduler/gantt", query_string=dict(version=str(VERSION), **controls))
        assert response.status_code == 410 and "Location" not in response.headers
        html = response.get_data(as_text=True)
        assert "旧入口已退役" in html and "没有跳转，也没有丢掉任何条件" in html
        assert "aps-cc-outline" not in html and "/static/js/" not in html and "/static/css/" not in html
        response.close()
    for helper in (_vendor_js, _gantt_js, _gantt_zoom_js, _gantt_adapter_js, _gantt_color_js,
                   _outline_js, _gantt_contract_js, _gantt_help_js, _gantt_popup_js, _gantt_legend_js,
                   _gantt_holidays_js, _gantt_decorations_js, _gantt_render_js):
        retired = Path(json.loads(helper()))
        assert not retired.exists()
        response = app_client.get("/" + retired.relative_to(REPO_ROOT).as_posix())
        assert response.status_code == 404
        response.close()
    context, payload = _canonical_workspace(app_client, {"version": str(VERSION)})
    assert context == {"plan_ref": reference}
    assert len(payload["data"]["tasks"]) == 3
    assert all(task["plan_ref"] == reference for task in payload["data"]["tasks"])

    node_code = "const root = " + json.dumps(str(REPO_ROOT)) + ";\n"
    node_code += "const sourceData = " + json.dumps(payload["data"]) + ";\n" + r"""
const fs = require('fs'), path = require('path'), vm = require('vm');
const original = JSON.stringify(sourceData), effects = [], observations = [];
let fills = [], strokes = [], theme = '', dash = [];
const ctx = {
  setTransform() {}, setLineDash(value) { dash = value.slice(); },
  fillRect(x,y,width,height) { fills.push({x,y,width,height,color:this.fillStyle}); },
  strokeRect(x,y,width,height) { strokes.push({x,y,width,height,color:this.strokeStyle,lineWidth:this.lineWidth,dash:dash.slice()}); },
  save() {}, restore() {}, beginPath() {}, rect() {}, clip() {}, fillText() {}
};
const canvas = { getBoundingClientRect: () => ({ width:720,height:56,left:0,top:0 }), getContext: () => ctx };
const forbidden = () => { throw new Error('No timer or DOM sweep is allowed for outline synchronization'); };
const runtime = vm.createContext({ console,
  document: { documentElement: {}, querySelectorAll: forbidden },
  setInterval: forbidden, setTimeout: forbidden,
  React: { useRef: () => ({current:canvas}), useLayoutEffect: fn => effects.push(fn()),
    createElement: (tag,props) => ({tag,props}) },
  getComputedStyle: () => ({getPropertyValue: key => theme + key}),
  MutationObserver: class { observe(node,options) { observations.push(options); } disconnect() {} },
  ResizeObserver: class { observe() {} disconnect() {} }
});
runtime.window = runtime;
for (const name of ['PointContract.js','PointGanttModel.js','PlanGanttModel.js','PlanGanttCanvas.js']) {
  vm.runInContext(fs.readFileSync(path.join(root,'static/workbench/app',name),'utf8'),runtime,{filename:name});
}
const M = runtime.PlanGanttModel, taskRef = sourceData.tasks[0].task_ref;
function draw({width=720,left=0,critical=true,selected=false,startShift=0,endShift=0,dark=false}={}) {
  const data = JSON.parse(original), task = data.tasks[0];
  task.start = M.wire(M.instant(task.start) + startShift);
  task.end = M.wire(M.instant(task.end) + endShift);
  // Supply an explicit occupancy fact to exercise the CURRENT conflict rule.
  data.projections.occupancy.resources = critical ? [{kind:'machine',resource_ref:task.machine_ref,
    segments:[{start:task.start,end:task.end,concurrent_operations:2}]}] : [];
  const input = JSON.stringify(data), model = M.layout(data,'machine',task.process_label,false,width), row = model.rows[0];
  fills = []; strokes = []; theme = dark ? 'dark:' : '';
  let selectedTask = null;
  const view = runtime.PlanGanttCanvas.DenseRow({row,model,width,viewport:720,left,
    selectedRef:selected ? taskRef : '',risks:new Map(),
    onSelect: task => { selectedTask = task.task_ref; },onHover: () => {}});
  view.props.onKeyDown({key:'Home',preventDefault(){}});
  const result = {fills:fills.slice(),strokes:strokes.slice(),isCritical:model.conflicts.has(taskRef),
    onDateChangeType:typeof view.props.onDateChange,onProgressChangeType:typeof view.props.onProgressChange,
    onMouseDownType:typeof view.props.onMouseDown,selectedTask,unchanged:JSON.stringify(data)===input};
  effects.splice(0).forEach(dispose => dispose());
  return result;
}
const start = draw(), pan = draw({left:38}), shorter = draw({endShift:-900000}), later = draw({startShift:900000});
const week = draw({width:360}), weekPan = draw({width:360,left:20}), weekResize = draw({width:360,endShift:-900000});
const month = draw({width:180}), monthPan = draw({width:180,left:14}), monthResize = draw({width:180,endShift:-900000});
const nonCritical = draw({critical:false}), selected = draw({selected:true}), dark = draw({dark:true});
const legacyPriorityOnly = M.tone({...sourceData.tasks[0],priority:'critical'},new Set(),new Map());
const overdue = M.tone(sourceData.tasks[0],new Set(),new Map([[sourceData.tasks[0].batch_id,'overdue']]));
process.stdout.write(JSON.stringify({start,pan,shorter,later,week,weekPan,weekResize,month,monthPan,monthResize,
  nonCritical,selected,dark,legacyPriorityOnly,overdue,observations,unchanged:JSON.stringify(sourceData)===original}));
"""
    result = _run_node_json(node_code)
    stages = ("start", "pan", "shorter", "later", "week", "weekPan", "weekResize", "month", "monthPan", "monthResize")
    for name in stages + ("nonCritical", "selected", "dark"):
        stage = result[name]
        assert stage["onDateChangeType"] == "undefined"
        assert stage["onProgressChangeType"] == "undefined"
        assert stage["onMouseDownType"] == "undefined"
        assert stage["unchanged"] and stage["selectedTask"] == payload["data"]["tasks"][0]["task_ref"]
        assert len(stage["fills"]) == len(stage["strokes"]) == 1
        fill, stroke = stage["fills"][0], stage["strokes"][0]
        assert fill["width"] > 0 and stroke["width"] > 0
        assert abs(stroke["x"] - fill["x"] - stroke["lineWidth"] / 2) < 0.001
        assert abs(stroke["width"] + stroke["lineWidth"] - fill["width"]) < 0.001

    assert result["nonCritical"]["isCritical"] is False
    assert result["nonCritical"]["strokes"][0]["color"] == "--wb-gantt-primary-edge"
    assert result["nonCritical"]["strokes"][0]["dash"] == []
    assert result["legacyPriorityOnly"] == "primary" and result["overdue"] == "critical"
    for name in stages:
        assert result[name]["isCritical"] is True
        assert result[name]["strokes"][0]["color"] == "--wb-gantt-critical-edge"
        assert result[name]["strokes"][0]["dash"] == [3, 2]
    assert result["pan"]["strokes"][0]["x"] != result["start"]["strokes"][0]["x"]
    assert result["shorter"]["strokes"][0]["width"] != result["start"]["strokes"][0]["width"]
    assert result["later"]["strokes"][0]["x"] != result["start"]["strokes"][0]["x"]
    assert result["week"]["strokes"][0]["width"] != result["start"]["strokes"][0]["width"]
    assert result["weekPan"]["strokes"][0]["x"] != result["week"]["strokes"][0]["x"]
    assert result["weekResize"]["strokes"][0]["width"] != result["week"]["strokes"][0]["width"]
    assert result["month"]["strokes"][0]["width"] != result["week"]["strokes"][0]["width"]
    assert result["monthPan"]["strokes"][0]["x"] != result["month"]["strokes"][0]["x"]
    assert result["monthResize"]["strokes"][0]["width"] != result["month"]["strokes"][0]["width"]
    assert result["selected"]["strokes"][0]["color"] == "--wb-gantt-gold"
    assert result["selected"]["strokes"][0]["lineWidth"] == 2
    assert result["dark"]["strokes"][0]["color"] == "dark:--wb-gantt-critical-edge"
    assert result["observations"] and all(options == {"attributes": True, "attributeFilter": ["data-theme", "class"]}
                                          for options in result["observations"])
    assert result["unchanged"] and _business_state(app_client) == before


def test_preview_bootstrap_syncs_outline_with_real_vendor(app_client) -> None:
    """Saved-scenario preview uses current read-only bars and real exports."""
    from tests._support.gantt_current import assert_plan_exports, plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, context, payload, before = plan_fixture(app_client, scenario=True)
    assert payload["data"]["plan"]["kind"] == "scenario"
    run_current_js(r"""
const data=h.runtime.APSPlanContract.workspace(sourceData,sourceData.data.plan.plan_ref).data,before=h.clone(data),M=h.runtime.PlanGanttModel;
for(const zoom of [1,2,4,8]) {
 const model=M.layout(data,'machine','',false,830*zoom,false),task=data.tasks[0],where=(M.instant(task.start)-model.start)/(model.end-model.start)*830*zoom;
 const result=h.gantt(data,{selected:{task},states:{PlanGantt:{2:zoom,5:{left:Math.max(0,where-100),top:0,width:1000,height:440}}}});
 const bar=result.nodes.find(n=>n.props['data-plan-task']===task.task_ref);assert(bar);assert.strictEqual(bar.props['aria-pressed'],true);
 assert(Math.abs(bar.props.style.width-(M.instant(task.end)-M.instant(task.start))/(model.end-model.start)*830*zoom)<1e-7);
 assert(!bar.props.onMouseDown&&!bar.props.onDrag);bar.props.onClick();h.equal(result.selections[0].task,task);
}
assert.strictEqual(h.runtime.Gantt,undefined);h.equal(data,before);
""", payload)
    assert_plan_exports(app_client, context, payload)
    assert _business_state(app_client) == before


def test_boot_hides_missing_outline_dependency_names_from_visible_error(app_client, monkeypatch) -> None:
    from tests._support.gantt_current_failure import assert_missing_asset

    assert_missing_asset(app_client, monkeypatch, "workbench/app/PlanGanttCanvas.js")


def test_formal_page_and_preview_share_critical_edge_tooltip_and_help_semantics(app_client) -> None:
    """Official/scenario share public task facts, not retired critical edges."""
    from contextlib import closing

    from core.infrastructure.database import get_connection
    from tests._support.gantt_current import navigation, plan_fixture, prepare_read_state, read_workspace
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state
    from tests._support.gantt_scenario import _saved_scenario

    query, official, _, _ = plan_fixture(app_client)
    with closing(get_connection(app_client.application.config["DATABASE_PATH"])) as conn:
        scenario = _saved_scenario(conn)
        conn.commit()
    before = prepare_read_state(app_client)
    preview = navigation(app_client, dict(query, scenario_id=scenario.scenario_id))
    assert preview["plan_ref"] != official["plan_ref"]
    for context, kind in ((official, "official"), (preview, "scenario")):
        payload = read_workspace(app_client, context)
        assert payload["data"]["plan"]["kind"] == kind
        run_current_js(r"""
const data=h.runtime.APSPlanContract.workspace(sourceData,sourceData.data.plan.plan_ref).data,M=h.runtime.PlanGanttModel,before=h.clone(data);
for(const task of data.tasks) {
 const tree=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task,before:false}}),text=h.text(tree);
 for(const value of [task.batch_id,task.process_label,M.timeLabel(task.start),M.timeLabel(task.end)])assert(text.includes(value));
 const result=h.gantt(data,{states:{PlanGantt:{6:{task,before:false,x:100,y:100}}}}),tip=result.nodes.find(n=>n.props.role==='tooltip');
 assert(tip);assert(h.text(tip).includes(task.process_label));assert(h.text(tip).includes(M.timeLabel(task.start)));
 for(const raw of ['repo_exception','控制前驱','关键链前驱'])assert(!h.text(tip).includes(raw));
 assert(h.text(result.tree).includes('预计超期'));assert(h.text(result.tree).includes('资源重叠'));assert(!h.text(result.tree).includes('关键工序关系线'));
}
h.equal(data,before);
""", payload)
    assert _business_state(app_client) == before


def test_critical_chain_unavailable_semantics_match_formal_preview_and_export_html(tmp_path: Path, app_client) -> None:
    """Backend critical metadata remains honest; current relations/export are separate."""
    from tests._support.gantt_current import assert_plan_exports, legacy_payload, plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    data = legacy_payload(critical_chain={"available": False, "ids": ["T1", "T2"],
        "edges": [{"from": "T1", "to": "T2", "edge_type": "machine"}], "reason": "repo_exception"})
    assert data["critical_chain"]["ids"] == []
    assert data["critical_chain"]["edges"] == []
    assert data["critical_chain"]["reason"] == "关键工序关系计算异常"
    _, context, payload, before = plan_fixture(app_client)
    assert payload["data"]["projections"]["process_order"]["state"] == "unavailable"
    run_current_js(r"""
const data=sourceData.data,task=data.tasks[0],order=data.projections.process_order;
const tree=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task},onRelated:()=>{throw new Error('unknown relation must not be invoked');}}),text=h.text(tree);
assert(order.issues.length>0);order.issues.forEach(issue=>assert(text.includes(issue.message)));
assert(!h.walk(tree).some(n=>n.type==='button'&&/^(前序|后序)/.test(n.props['aria-label']||'')));assert(!text.includes('repo_exception'));
assert(!h.text(h.gantt(data).tree).includes('关键工序关系线'));
""", payload)
    assert_plan_exports(app_client, context, payload)
    assert not (REPO_ROOT / "templates/scheduler/gantt.html").exists()
    assert not list(tmp_path.glob("preview_unavailable*.html"))
    assert _business_state(app_client) == before


def test_gantt_templates_use_contract_rendered_help_list() -> None:
    """Current controls carry explicit basis and labels, not a stale help host."""
    from tests._support.gantt_current_js import run_current_js

    assert not (REPO_ROOT / "templates/scheduler/gantt.html").exists()
    run_current_js(r"""
const data=h.fixture(),result=h.gantt(data);
assert(h.text(result.tree).includes(data.projections.baseline.reason));
const baseline=result.nodes.find(n=>n.props['aria-label']==='显示初始计划'),changes=result.nodes.find(n=>n.props['aria-label']==='仅变更');assert(baseline.props.disabled&&changes.props.disabled);
assert(!h.text(result.tree).includes('工厂本地时间'));assert(h.text(result.tree).includes('预计超期'));assert(h.text(result.tree).includes('资源重叠'));
assert(!result.nodes.some(n=>n.props.id==='ganttHelpList'));assert(!h.text(result.tree).includes('当前版本关键链'));
""")


def test_gantt_contract_sanitizes_render_task_names_and_preserves_raw_name() -> None:
    """Real React text children preserve names without creating raw markup."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const raw='<img src=x onerror=alert(1)>',data=h.fixture([[raw,'2026-05-11T08:00:00','2026-05-11T09:00:00']]),before=h.clone(data),task=data.tasks[0];
const gantt=h.gantt(data,{states:{PlanGantt:{6:{task,before:false,x:100,y:100}}}}),detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task}});
assert.strictEqual(data.tasks[0].process_label,raw);assert(h.text(gantt.tree).includes(raw));assert(h.text(detail).includes(raw));
for(const tree of [gantt.tree,detail]) for(const node of h.walk(tree)) {assert.notStrictEqual(node.type,'img');assert.notStrictEqual(node.type,'script');assert(!Object.hasOwn(node.props,'dangerouslySetInnerHTML'));assert(!Object.hasOwn(node.props,'onError'));}
const bar=gantt.nodes.find(n=>n.props['data-plan-task']);assert(bar.props.title.includes(raw));h.equal(data,before);
""")


def test_gantt_contract_disables_calendar_fallback_when_calendar_load_failed(app_client) -> None:
    """Damaged explicit calendar rows never become weekend/default capacity."""
    from tests._support.gantt_current import invalid_calendar_fixture
    from tests._support.gantt_current_js import run_current_js

    _, payload, _ = invalid_calendar_fixture(app_client)
    run_current_js(r"""
const data=h.runtime.APSPlanContract.workspace(sourceData,sourceData.data.plan.plan_ref).data;
for(const tab of ['calendar','load']) {
 const tree=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data},{ProjectionTables:{0:tab}}),text=h.text(tree);
 assert(text.includes('暂无数据'));assert(!text.includes('0%'));assert(!text.includes('周末默认'));assert(!text.includes('BROKEN_CALENDAR_CANARY'));
 assert(!h.walk(tree).some(node=>node.props.className==='plan-meter'));
}
""", payload)


def test_gantt_contract_calendar_load_failed_message_does_not_echo_raw_event() -> None:
    """The retained producer sanitizes raw calendar errors before public rendering."""
    from tests._support.gantt_current import legacy_payload
    from tests._support.gantt_current_js import run_current_js

    data = legacy_payload(degraded=True, degradation_counters={"calendar_load_failed": 1}, degradation_events=[{
        "code": "calendar_load_failed", "message": "sqlite OperationalError: /tmp/private.db locked", "sample": "RAW_SECRET"}])
    events = data["degradation_events"]
    assert len(events) == 1
    assert events[0]["message"] == "工作日历加载失败，当前不显示假期/停工背景标注。"
    assert "sample" not in events[0]
    assert all(raw not in str(events) for raw in ("sqlite", "RAW_SECRET", "/tmp/private.db"))
    run_current_js(r"""
const tree=h.render(h.runtime.ResourceControls.Issues,{issues:sourceData});assert(h.text(tree).includes(sourceData[0].message));
for(const raw of ['sqlite','RAW_SECRET','/tmp/private.db'])assert(!h.text(tree).includes(raw));
""", events)


def test_gantt_contract_critical_unavailable_message_maps_reason_code() -> None:
    """Public critical metadata preserves partial counts without raw-code prose."""
    from tests._support.gantt_current import legacy_payload
    from tests._support.gantt_current_js import run_current_js

    data = legacy_payload(critical_chain={"ids": ["T1"], "edges": [], "available": False,
        "reason": "关键工序关系计算异常", "reason_code": "repo_exception", "dropped_count": 2, "critical_chain_partial": True},
        degradation_counters={"critical_chain_unavailable": 1})
    chain = data["critical_chain"]
    assert chain["ids"] == [] and chain["edges"] == []
    assert (chain["reason_code"], chain["dropped_count"], chain["critical_chain_partial"]) == ("repo_exception", 2, True)
    assert chain["reason"] == "关键工序关系计算异常"
    run_current_js(r"""
const data=h.processFixture(),before=h.clone(data);data.projections.process_order={state:'unavailable',basis:null,items:[],issues:[{code:'process_order_unavailable',message:'冻结工艺关系无法核实。'}]};
const tree=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task:data.tasks[0]}});assert(h.text(tree).includes('冻结工艺关系无法核实。'));
assert(!h.text(tree).includes('repo_exception'));assert(!h.text(tree).includes('无前序工序'));h.equal(data.tasks,before.tasks);
""")


def test_formal_preview_and_export_html_share_degradation_and_overdue_warnings(tmp_path: Path, app_client) -> None:
    """Legacy warning facts survive; current calendar/export never invent capacity."""
    from tests._support.gantt_current import assert_plan_exports, invalid_calendar_fixture, legacy_payload
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    message = "部分超期标记可能不完整，当前仍按已识别条目标记。"
    data = legacy_payload(degradation_events=[{"code": "calendar_load_failed", "message": "RAW_SECRET"}],
        degradation_counters={"calendar_load_failed": 1, "bad_time_row_skipped": 2},
        overdue_markers_partial=True, overdue_markers_message=message)
    assert data["degradation_counters"] == {"calendar_load_failed": 1, "bad_time_row_skipped": 2}
    assert data["overdue_markers_partial"] is True
    assert data["overdue_markers_degraded"] is False
    assert data["overdue_markers_message"] == message
    assert "RAW_SECRET" not in str(data)
    context, payload, before = invalid_calendar_fixture(app_client)
    run_current_js(r"""
const data=sourceData.data,task=data.tasks[0],detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task}}),text=h.text(detail);
assert(text.includes('暂无数据'));assert(!text.includes('0%'));assert(!text.includes('周末默认'));assert(!text.includes('BROKEN_CALENDAR_CANARY'));
const calendar=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data},{ProjectionTables:{0:'calendar'}});assert(h.text(calendar).includes('暂无数据'));
""", payload)
    assert_plan_exports(app_client, context, payload)
    assert not list(tmp_path.glob("preview_degraded*.html"))
    assert _business_state(app_client) == before
