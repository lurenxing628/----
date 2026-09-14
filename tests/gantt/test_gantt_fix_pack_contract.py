"""甘特小修包契约（fusion-gantt-fix-pack）。

钉死点：①applyFilters 批次/资源筛选精确等值（equalsI——B1 不带出 B12，大小写
不敏感保留，machine/operator 两视图同语义）；②dark 块 .aps-cc-outline-outer
覆盖锁 token 值（亮色外圈 #334155 与暗色边框同色隐形）；③模拟调整死按钮整壳
零残留（gantt.html/CSS 文件/HEX_FREEZE_ALLOWANCE 反向断言）；④ZOOM_SPECS 与
vendor update_view_scale 双份真相——collectZoomSpecMismatches 纯函数红绿自证
+ boot 接线（真 vendor 静默过/漂移 fail-loud 早错）。
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


def _chain_walk_js(helpers):
    import json

    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_chain_walk.js"))


def _full_chain_setup(helpers) -> str:
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
function mkTask(id, batch, machineId, machine, operatorId, operator) {{
  return {{
    id: id, name: id, start: "2026-05-01 08:00:00", end: "2026-05-01 09:00:00",
    progress: 0, dependencies: "",
    meta: {{ batch_id: batch, machine_id: machineId, machine: machine,
             operator_id: operatorId, operator: operator, source: "internal" }},
  }};
}}
state.allTasks = [
  mkTask("T1", "B1", "MC1", "车床一号", "OP1", "张三"),
  mkTask("T2", "B12", "MC12", "车床十二号", "OP12", "李四"),
  mkTask("T3", "B100", "MC100", "车床百号", "OP100", "王五"),
];
state.cfg = {{ view: "machine" }};
"""


def _boot_stub_ui_js() -> str:
    return """
ns.initCalendarDays = ns.initCalendarDays || function () {};
ns.applyUiFromUrl = function () {};
ns.bindUi = function () {};
ns.readUi = function () {};
ns.persistUiToUrl = function () {};
document.readyState = "loading";
"""


def _run(helpers, body: str) -> dict:
    return helpers._run_node_json(_full_chain_setup(helpers) + body)


# ---------- ①筛选精确匹配 ----------

def test_apply_filters_batch_exact_match_not_substring(app_client):
    """Exact legacy filters retire explicitly; batch grouping keeps identities."""
    from tests._support.gantt_current import assert_retired, plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    query, context, payload, before = plan_fixture(app_client)
    for value in ("B1", "b1", "B12", "B100"):
        assert_retired(app_client, dict(query, gantt_batch=value))
        response = app_client.get("/api/workbench/v1/plans/" + context["plan_ref"] + "/workspace",
                                  query_string={"gantt_batch": value})
        assert response.status_code == 400
        assert response.get_json()["ok"] is False
        assert "data" not in response.get_json()
    run_current_js(r"""
const data=h.processFixture();data.tasks.forEach((task,index)=>{task.batch_id=['B1','B12','B100'][index];});const before=h.clone(data), M=h.runtime.PlanGanttModel;
const grouped=M.layout(data,'batch','',false,830,false);assert.strictEqual(grouped.groupCount,3);
for(const task of data.tasks) assert(grouped.rows.some(row=>row.items.length===1&&row.items[0].task.task_ref===task.task_ref));
// Current search is intentionally substring search, not the retired exact filter.
assert.strictEqual(M.layout(data,'batch','b1',false,830,false).tasks.length,3);h.equal(data,before);
""")
    assert payload["data"]["task_count"] == 3
    assert _business_state(app_client) == before


def test_apply_filters_resource_exact_both_views(app_client):
    """A retired exact resource filter cannot silently become fuzzy search."""
    from tests._support.gantt_current import assert_retired, plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    query, context, _, before = plan_fixture(app_client)
    for value in ("MC1", "车床一号", "OP1", "张三"):
        assert_retired(app_client, dict(query, gantt_resource=value))
        response = app_client.get("/api/workbench/v1/plans/" + context["plan_ref"] + "/workspace",
                                  query_string={"gantt_resource": value})
        assert response.status_code == 400
        assert response.get_json()["ok"] is False
        assert "data" not in response.get_json()
    run_current_js(r"""
const data=h.processFixture();data.resources=[];
data.tasks.forEach((task,index)=>{for(const kind of ['machine','operator']) {const ref=h.reference((kind==='machine'?200:300)+index);task[kind+'_ref']=ref;data.resources.push({ref,label:(kind==='machine'?'MC':'OP')+[1,12,100][index],business_code:String(index)});}});
const before=h.clone(data), M=h.runtime.PlanGanttModel;
for(const mode of ['machine','operator']) {const model=M.layout(data,mode,'',false,830,false);assert.strictEqual(model.groupCount,3);for(const task of data.tasks) assert(model.rows.some(row=>row.items.length===1&&row.items[0].task.task_ref===task.task_ref));}
h.equal(data,before);
""")
    assert _business_state(app_client) == before


# ---------- ②dark cc-outline 覆盖 ----------

def test_dark_cc_outline_override_locked():
    """Current dark risk/selection tokens do not claim legacy critical-chain CSS."""
    from tests._support.gantt_current_js import run_current_js

    css = (REPO_ROOT / "static/workbench/prototype/ui_kits/workbench/gantt-theme.css").read_text(encoding="utf-8")
    dark = css.split('[data-theme="dark"]', 1)[1]
    assert "--wb-gantt-critical-edge:#c38796" in dark
    assert "--wb-gantt-gold:#d7ba76" in dark
    run_current_js(r"""
const css=h.styles();
assert(css.includes('var(--wb-gantt-critical-edge)'));assert(css.includes('var(--wb-gantt-gold)'));
const data=h.fixture(), before=h.clone(data);data.projections.delivery_risks.items=[{batch_id:'B1',risk:'overdue'}];
const selected=h.gantt(data,{selected:{task:data.tasks[0]}}).nodes.find(n=>n.props['data-plan-task']===data.tasks[0].task_ref);
assert(selected.props.className.includes('critical'));assert.strictEqual(selected.props['aria-pressed'],true);assert(!selected.props.className.includes('aps-cc-outline'));
h.equal(data.tasks,before.tasks);
""")


# ---------- ③死按钮整壳零残留 ----------

def test_simulation_shell_removed_zero_references():
    """Retired simulation shell stays absent; the real trial entry is separate."""
    assert not (REPO_ROOT / "templates/scheduler/gantt.html").exists()
    for rel in ("frontend/workbench/app/PlanGantt.jsx", "frontend/workbench/app/PlanWorkspace.jsx"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "ganttSimulationEntry" not in text
        assert "aps_gantt_simulation" not in text
    assert not (REPO_ROOT / "static/css/aps_gantt_simulation.css").exists()
    hex_contract = (REPO_ROOT / "tests/web_pages/test_css_token_source_contract.py").read_text(encoding="utf-8")
    assert "aps_gantt_simulation" not in hex_contract
    for rel in (".codestable/architecture/ui-gantt.md", "web/viewmodels/page_manuals_scheduler_outputs.py", "static/docs/scheduler_manual.md"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for stale in ("灰色说明入口", "灰色禁用按钮", "灰色入口", "不能点击", "当前页面入口仍禁用", "ganttSimulationEntry"):
            assert stale not in text, (rel, stale)


# ---------- ④双份真相断言 ----------

def test_collect_zoom_spec_mismatches_red_green(app_client):
    """Numeric current geometry consumes the validated local-time contract."""
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, context, payload, before = plan_fixture(app_client)
    run_current_js(r"""
const C=h.runtime.APSPlanContract, original=h.clone(sourceData), ref=sourceData.data.plan.plan_ref;
const data=C.workspace(sourceData,ref).data; assert.strictEqual(data.task_count,3);
for(const alter of [p=>p.data.tasks[0].start='2026-99-99T00:00:00',p=>p.data.task_count++,p=>p.data.tasks[0].end=p.data.tasks[0].start]) {
 const bad=h.clone(sourceData);alter(bad);assert.throws(()=>C.workspace(bad,ref),/读到的工序安排、时间范围或分析数据不完整或来源对不上/);
}
for(const width of [830,1660,849920]) {const M=h.runtime.PlanGanttModel,model=M.layout(data,'machine','',false,width,false);for(const row of model.rows) for(const item of row.items) assert.strictEqual(item.end-item.start,M.instant(item.task.end)-M.instant(item.task.start));}
h.equal(sourceData,original);
""", payload)
    assert context["plan_ref"] == payload["data"]["plan"]["plan_ref"]
    assert _business_state(app_client) == before


def test_boot_zoom_drift_fails_loud_with_early_error(app_client):
    """Reject date/scope drift before using any current rendering result."""
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, _, payload, before = plan_fixture(app_client)
    run_current_js(r"""
const C=h.runtime.APSPlanContract, ref=sourceData.data.plan.plan_ref;let renders=0;
const accept=payload=>{const result=C.workspace(payload,ref);renders++;return h.gantt(result.data);};
const valid=accept(sourceData);assert(valid.nodes.some(n=>n.props['data-plan-task']));
for(const alter of [p=>p.data.time_scope.time_basis='utc',p=>p.data.time_scope.range_end='2027-01-01T00:00:00',p=>p.data.tasks_complete=false]) {
 const bad=h.clone(sourceData);alter(bad);let failure;
 try {accept(bad);}catch(error){failure=error;}assert(failure);assert.strictEqual(renders,1);
 const error=h.render(h.runtime.ResourceControls.ErrorBox,{error:failure});assert(h.text(error).includes('没有当作完整结果使用'));
 assert(!h.walk(error).some(n=>n.props['data-plan-task']));
}
""", payload)
    assert _business_state(app_client) == before
