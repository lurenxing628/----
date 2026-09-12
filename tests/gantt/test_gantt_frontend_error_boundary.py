"""回归测试：甘特图前端 boot（ns.loadAndRender）的错误边界——HTTP 错误时把后端 JSON error.message 原样显示而不暴露 HTTP 状态码、坏数据形状/非数组 tasks 显示「数据格式」错误而非空状态、缺渲染器/弹窗依赖显示「脚本加载不完整」、prepare/装饰阶段内部异常统一收敛为「甘特图显示异常，请刷新后重试。」并隐藏 DOM mismatch 等内部细节，且合法空 tasks 仍走「暂无排程数据」空状态而非报错。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from tests._support.paths import REPO_ROOT


def _load_helpers():
    helper_path = REPO_ROOT / "tests" / "gantt" / "test_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_boot_case(
    payload: Any,
    *,
    ok: bool = True,
    status: int = 200,
    load_vendor: bool = False,
    load_render: bool = True,
    setup_before_render: str = "",
    setup_after_scripts: str = "",
) -> dict:
    helpers = _load_helpers()
    vendor_load = f"loadScript({helpers._vendor_js()});" if load_vendor else ""
    render_load = f"loadScript({helpers._gantt_render_js()});" if load_render else ""
    node_code = f"""
{helpers.DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
createHost("ganttDegradationWarning");
createHost("ganttOverdueWarning");
createHost("ganttZoomWarning");
const helpList = document.createElement("ul");
helpList.setAttribute("id", "ganttHelpList");
document.body.appendChild(helpList);
document.readyState = "loading";

{vendor_load}
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
{setup_before_render}
{render_load}
const ns = window.__APS_GANTT__;
ns.applyUiFromUrl = function () {{}};
ns.bindUi = function () {{}};
ns.readUi = function () {{}};
ns.persistUiToUrl = function () {{}};
{setup_after_scripts}
const host = document.getElementById("gantt");
host.setAttribute("data-url", "/api/mock-gantt");
host.setAttribute("data-view", "machine");
host.setAttribute("data-week-start", "2026-01-26");
host.setAttribute("data-start-date", "2026-01-26");
host.setAttribute("data-end-date", "2026-02-02");
host.setAttribute("data-version", "7");
host.setAttribute("data-has-history", "1");

const responsePayload = {json.dumps(payload, ensure_ascii=False)};
global.fetch = function () {{
  return Promise.resolve({{
    ok: {str(ok).lower()},
    status: {int(status)},
    json() {{
      return Promise.resolve(responsePayload);
    }},
  }});
}};

loadScript({helpers._gantt_boot_js()});
(async function () {{
  let rejected = false;
  let rejectionMessage = "";
  if (typeof ns.loadAndRender === "function") {{
    try {{
      await ns.loadAndRender();
    }} catch (error) {{
      rejected = true;
      rejectionMessage = String(error && error.message ? error.message : error);
    }}
  }}
  const errEl = document.getElementById("ganttError");
  const emptyEl = document.getElementById("ganttEmpty");
  process.stdout.write(JSON.stringify({{
    error: errEl ? errEl.textContent || "" : "",
    errorDisplay: errEl && errEl.style ? String(errEl.style.display || "") : "",
    empty: emptyEl ? emptyEl.textContent || "" : "",
    emptyDisplay: emptyEl && emptyEl.style ? String(emptyEl.style.display || "") : "",
    allTasks: ns.state && Array.isArray(ns.state.allTasks) ? ns.state.allTasks.length : -1,
    currentTasks: ns.state && Array.isArray(ns.state.currentTasks) ? ns.state.currentTasks.length : -1,
    ganttIsNull: ns.state ? ns.state.gantt === null : null,
    rejected,
    rejectionMessage,
  }}));
}})().catch((error) => {{
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
}});
"""
    return helpers._run_node_json(node_code)


def _valid_empty_payload() -> dict:
    return {
        "success": True,
        "data": {
            "tasks": [],
            "calendar_days": [],
            "critical_chain": {"ids": [], "edges": [], "available": True},
            "degradation_events": [],
            "degradation_counters": {},
        },
    }


def _non_empty_payload() -> dict:
    payload = _valid_empty_payload()
    payload["data"]["tasks"] = [
        {
            "id": "T1",
            "name": "Needs adapter",
            "start": "2026-01-26 08:00:00",
            "end": "2026-01-26 09:00:00",
            "progress": 0,
            "dependencies": "",
            "meta": {"batch_id": "B001", "source": "internal", "status": "pending"},
        }
    ]
    return payload


def test_boot_surfaces_backend_json_error_body_for_http_error(app_client) -> None:
    """The actual current HTTP error body survives transport and visible output."""
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, context, _, before = plan_fixture(app_client)
    response = app_client.get("/api/workbench/v1/plans/" + context["plan_ref"] + "/workspace",
                              query_string={"gantt_batch": "RAW_SECRET"})
    assert response.status_code == 400
    failure = response.get_json()
    assert failure["ok"] is False
    assert "RAW_SECRET" not in response.get_data(as_text=True)
    run_current_js(r"""
h.runtime.location={origin:'http://127.0.0.1',href:'http://127.0.0.1/workbench?view=gantt'};h.load('static/workbench/app/PlanAPI.js');
const calls=[];h.runtime.fetch=async(url,options)=>{calls.push({url,options});return {ok:false,headers:{get:()=> 'application/json'},json:async()=>sourceData.failure};};
return (async()=>{let error;try{await h.runtime.APSPlanAPI.create().workspace(sourceData.ref);}catch(value){error=value;}
assert(error);assert.strictEqual(error.message,sourceData.failure.error.message);assert.strictEqual(error.committed,false);
const tree=h.render(h.runtime.ResourceControls.ErrorBox,{error});assert(h.text(tree).includes(sourceData.failure.error.message));assert(!h.text(tree).includes('RAW_SECRET'));
assert.strictEqual(calls.length,1);assert.strictEqual(calls[0].options.method,'GET');assert.strictEqual(calls[0].options.redirect,'error');assert.strictEqual(calls[0].options.cache,'no-store');assert(!h.walk(tree).some(n=>n.props['data-plan-task']));})();
""", {"ref": context["plan_ref"], "failure": failure})
    assert _business_state(app_client) == before


def test_boot_rejects_bad_payload_data_shape_instead_of_empty_state(app_client) -> None:
    """A malformed envelope is not a legitimate empty plan."""
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, _, payload, before = plan_fixture(app_client)
    run_current_js(r"""
const C=h.runtime.APSPlanContract,ref=sourceData.data.plan.plan_ref;C.workspace(sourceData,ref);
for(const data of [null,[],{},'RAW_SECRET /tmp/private.db']) {
 const bad=h.clone(sourceData);bad.data=data;let error;try{C.workspace(bad,ref);}catch(value){error=value;}assert(error);
 const tree=h.render(h.runtime.ResourceControls.ErrorBox,{error});assert(h.text(tree).length>0);assert(!h.text(tree).includes('RAW_SECRET'));assert(!h.text(tree).includes('/tmp/private.db'));
 assert(!h.text(tree).includes('该读取范围没有安排。'));assert(!h.walk(tree).some(n=>n.props['data-plan-task']));
}
""", payload)
    assert _business_state(app_client) == before


def test_current_error_disclosure_retains_diagnostics_outside_visible_message() -> None:
    """Fixture text follows closed native details without deleting diagnostic data."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const secret='RuntimeError RAW_SECRET /tmp/private.db';
const tree=h.render(h.runtime.ResourceControls.ErrorBox,{error:new Error(secret)}), visible=h.text(tree);
assert(visible.length>0);assert(!visible.includes('RAW_SECRET'));assert(!visible.includes('/tmp/private.db'));
const disclosure=h.walk(tree).find(node=>node.type==='details'&&node.props.className==='wb-ref');assert(disclosure);
assert(h.text({...disclosure,props:{...disclosure.props,open:true}}).includes(secret));
assert(h.walk(disclosure).some(node=>node.type==='code'&&h.text(node)===secret));
""")


def test_boot_rejects_non_array_tasks_instead_of_showing_no_schedule(app_client) -> None:
    """A non-array task container is rejected with a visible public error."""
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, _, payload, before = plan_fixture(app_client)
    run_current_js(r"""
const C=h.runtime.APSPlanContract,ref=sourceData.data.plan.plan_ref;C.workspace(sourceData,ref);
for(const tasks of [null,{},'RAW_SECRET',3]) {
 const bad=h.clone(sourceData);bad.data.tasks=tasks;let error;try{C.workspace(bad,ref);}catch(value){error=value;}assert(error);
 const text=h.text(h.render(h.runtime.ResourceControls.ErrorBox,{error}));assert(text.includes('计划任务、范围或投影协议不完整或串源'));assert(!text.includes('RAW_SECRET'));assert(!text.includes('该读取范围没有安排。'));
}
""", payload)
    assert _business_state(app_client) == before


def test_boot_catches_render_adapter_missing_gantt_and_writes_visible_error(app_client, monkeypatch) -> None:
    from tests._support.gantt_current_failure import assert_missing_asset

    assert_missing_asset(app_client, monkeypatch, "workbench/app/PlanGantt.js")


def test_boot_surfaces_missing_render_dependency_to_visible_error(app_client, monkeypatch) -> None:
    from tests._support.gantt_current_failure import assert_missing_asset

    assert_missing_asset(app_client, monkeypatch, "workbench/app/PlanGanttModel.js")


def test_boot_surfaces_missing_popup_dependency_to_visible_error(app_client, monkeypatch) -> None:
    from tests._support.gantt_current_failure import assert_missing_asset

    assert_missing_asset(app_client, monkeypatch, "workbench/app/PlanDetailsUI.js")


def test_boot_catches_prepare_stage_errors_as_visible_generic_error(app_client, monkeypatch) -> None:
    """A genuine manifest I/O failure stops the host without exposing its cause."""
    from tests._support.gantt_current import prepare_read_state
    from tests._support.gantt_retirement import _business_state

    before = prepare_read_state(app_client)
    target = (Path(app_client.application.static_folder) / "workbench/asset-manifest.json").resolve()
    original = Path.read_text
    hits = []

    def read(path, *args, **kwargs):
        if path.resolve() == target:
            hits.append(str(path))
            raise OSError("RAW_SECRET sqlite /tmp/private.db")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "read_text", read)
        response = app_client.get("/workbench?view=gantt")
    text = response.get_data(as_text=True)
    assert hits
    assert response.status_code == 503
    assert "工作台资源清单尚未生成或无法读取。" in text
    assert "workbench-boot" not in text
    assert all(value not in text for value in ("RAW_SECRET", "sqlite", "/tmp/private.db", str(target)))
    assert app_client.get("/workbench?view=gantt").status_code == 200
    assert _business_state(app_client) == before


def test_boot_hides_internal_dom_mismatch_message_from_visible_error(app_client) -> None:
    """Current contract failures never echo a poisoned internal DTO field."""
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, _, payload, before = plan_fixture(app_client)
    run_current_js(r"""
const C=h.runtime.APSPlanContract,ref=sourceData.data.plan.plan_ref,secret='outline.installCriticalOutlineSyncAdapter RAW_SECRET /tmp/private.db';
for(const change of [p=>p.data.tasks[0].start=secret,p=>p.data.tasks[0].raw_dom_error=secret,p=>p.data.scope.plan_ref=secret]) {
 const bad=h.clone(sourceData);change(bad);let error;try{C.workspace(bad,ref);}catch(value){error=value;}assert(error);
 const text=h.text(h.render(h.runtime.ResourceControls.ErrorBox,{error}));assert(text.includes('未作为完整结果使用'));
 for(const raw of ['outline','RAW_SECRET','/tmp/private.db'])assert(!text.includes(raw));
}
""", payload)
    assert _business_state(app_client) == before


def test_boot_keeps_valid_empty_tasks_as_empty_state_not_error(app_client) -> None:
    """A real empty selected interval still retains its plan identity and span."""
    from tests._support.gantt_current import plan_fixture, read_workspace
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, context, full, before = plan_fixture(app_client)
    scope = {"range_start": "2026-05-05T00:00:00", "range_end": "2026-05-06T00:00:00"}
    payload = read_workspace(app_client, dict(context, **scope))
    assert payload["data"]["tasks"] == []
    assert payload["data"]["plan"] == full["data"]["plan"]
    assert payload["data"]["plan_span"] == full["data"]["plan_span"]
    run_current_js(r"""
const data=h.runtime.APSPlanContract.workspace(sourceData.payload,sourceData.ref,sourceData.scope).data;
const result=h.gantt(data);assert(h.text(result.tree).includes('该读取范围没有安排。'));assert(!result.nodes.some(n=>n.props['data-plan-task']));
assert.strictEqual(data.task_count,0);assert.strictEqual(data.tasks_complete,true);assert(!h.text(result.tree).includes('串源'));
""", {"payload": payload, "ref": context["plan_ref"], "scope": scope})
    assert _business_state(app_client) == before
