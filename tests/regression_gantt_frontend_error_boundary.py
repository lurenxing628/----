"""回归测试：甘特图前端 boot（ns.loadAndRender）的错误边界——HTTP 错误时把后端 JSON error.message 原样显示而不暴露 HTTP 状态码、坏数据形状/非数组 tasks 显示「数据格式」错误而非空状态、缺渲染器/弹窗依赖显示「脚本加载不完整」、prepare/装饰阶段内部异常统一收敛为「甘特图显示异常，请刷新后重试。」并隐藏 DOM mismatch 等内部细节，且合法空 tasks 仍走「暂无排程数据」空状态而非报错。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from tests._support.paths import REPO_ROOT


def _load_helpers():
    helper_path = REPO_ROOT / "tests" / "regression_gantt_critical_outline_sync.py"
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


def test_boot_surfaces_backend_json_error_body_for_http_error() -> None:
    result = _run_boot_case(
        {"success": False, "error": {"message": "具体业务错误"}},
        ok=False,
        status=400,
    )

    assert result["rejected"] is False
    assert result["error"] == "具体业务错误"
    assert result["errorDisplay"] == "block"
    assert result["emptyDisplay"] != "block"
    assert "HTTP 400" not in result["error"]


def test_boot_rejects_bad_payload_data_shape_instead_of_empty_state() -> None:
    for bad_payload in (
        {"success": True},
        {"success": True, "data": None},
        {"success": True, "data": []},
        {"success": True, "data": "bad"},
    ):
        result = _run_boot_case(bad_payload)
        assert result["rejected"] is False
        assert "数据格式" in result["error"]
        assert result["errorDisplay"] == "block"
        assert result["emptyDisplay"] != "block"
        assert "暂无排程数据" not in result["empty"]
        assert result["allTasks"] == 0
        assert result["currentTasks"] == 0
        assert result["ganttIsNull"] is True


def test_boot_rejects_non_array_tasks_instead_of_showing_no_schedule() -> None:
    payload = _valid_empty_payload()
    payload["data"]["tasks"] = {"id": "T1", "name": "bad object"}

    result = _run_boot_case(payload)

    assert result["rejected"] is False
    assert "数据格式" in result["error"]
    assert result["errorDisplay"] == "block"
    assert result["emptyDisplay"] != "block"
    assert "暂无排程数据" not in result["empty"]
    assert result["allTasks"] == 0


def test_boot_catches_render_adapter_missing_gantt_and_writes_visible_error() -> None:
    result = _run_boot_case(_non_empty_payload(), load_vendor=False)

    assert result["rejected"] is False
    assert "甘特图显示组件没有加载完成" in result["error"]
    assert result["errorDisplay"] == "block"
    assert result["emptyDisplay"] != "block"
    assert "暂无排程数据" not in result["empty"]
    assert result["allTasks"] == 0
    assert result["currentTasks"] == 0
    assert result["ganttIsNull"] is True


def test_boot_surfaces_missing_render_dependency_to_visible_error() -> None:
    result = _run_boot_case(_valid_empty_payload(), load_render=False)

    assert result["rejected"] is False
    assert "脚本加载不完整" in result["error"]
    assert "render" not in result["error"]
    assert "contract." not in result["error"]
    assert result["errorDisplay"] == "block"
    assert result["emptyDisplay"] != "block"


def test_boot_surfaces_missing_popup_dependency_to_visible_error() -> None:
    result = _run_boot_case(
        _valid_empty_payload(),
        setup_after_scripts="window.__APS_GANTT__.popup = {};",
    )

    assert result["rejected"] is False
    assert "脚本加载不完整" in result["error"]
    assert "popup." not in result["error"]
    assert result["errorDisplay"] == "block"
    assert result["emptyDisplay"] != "block"


def test_boot_catches_prepare_stage_errors_as_visible_generic_error() -> None:
    result = _run_boot_case(
        _valid_empty_payload(),
        setup_after_scripts="ns.contract.renderHelpList = function () { throw new Error('internal contract boom'); };",
    )

    assert result["rejected"] is False
    assert result["error"] == "甘特图显示异常，请刷新后重试。"
    assert result["errorDisplay"] == "block"
    assert result["emptyDisplay"] != "block"
    assert "internal contract boom" not in result["error"]


def test_boot_hides_internal_dom_mismatch_message_from_visible_error() -> None:
    result = _run_boot_case(
        _non_empty_payload(),
        setup_before_render="""
window.__APS_GANTT__.adapter.createGantt = function () {
  return { gantt_start: new Date("2026-01-26T00:00:00") };
};
window.__APS_GANTT__.outline.installCriticalOutlineSyncAdapter = function () {};
window.__APS_GANTT__.decorations.beginRenderPass = function () {};
window.__APS_GANTT__.decorations.buildTaskMapById = function () { return new Map(); };
window.__APS_GANTT__.decorations.decorateStaticAfterRender = function () {};
window.__APS_GANTT__.safeDecorateDynamic = function () {
  throw new Error("Gantt DOM mismatch: wrappers=0 tasks=1");
};
""",
    )

    assert result["rejected"] is False
    assert result["error"] == "甘特图显示异常，请刷新后重试。"
    assert result["errorDisplay"] == "block"
    assert result["emptyDisplay"] != "block"
    assert "Gantt DOM mismatch" not in result["error"]
    assert "wrappers" not in result["error"]


def test_boot_keeps_valid_empty_tasks_as_empty_state_not_error() -> None:
    result = _run_boot_case(_valid_empty_payload())

    assert result["rejected"] is False
    assert result["error"] == ""
    assert result["errorDisplay"] != "block"
    assert "暂无排程数据" in result["empty"]
    assert result["emptyDisplay"] == "block"
    assert result["allTasks"] == 0
    assert result["currentTasks"] == 0
    assert result["ganttIsNull"] is True
