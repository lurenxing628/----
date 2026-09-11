"""回归测试：资源派工页工作台执行契约——执行脚本按职责顺序加载；前端 renderExecutionCards 对缺图号/工序渲染中文兜底文案；任务卡输出 part_label、
开完工时间差(晚 N 分钟/早 N 分钟)与现场记录来源标签；非正式方案页面不暴露任何 actual 写入地址。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from tests._support.legacy_report_contract import IDENTITY_UNAVAILABLE, RETIRED_SCOPE, assert_retired, get_unchanged
from tests._support.paths import REPO_ROOT
from tests.operation_execution.operation_execution_feedback_test_support import (
    RESOURCE_DISPATCH_TEMPLATE,
    _base_payload,
    _build_app,
    _current_query,
    _events_url,
    _json,
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_node_json(node_code: str) -> Dict[str, Any]:
    proc = subprocess.run(
        ["node", "-"],
        cwd=str(REPO_ROOT),
        input=node_code,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"node 执行失败：rc={proc.returncode} stderr={proc.stderr[:500]!r}")
    return json.loads(proc.stdout)


def _field_fallbacks():
    return _run_node_json(r"""
const fs = require("fs");
global.window = { APSResourceContract: {} };
eval(fs.readFileSync("frontend/workbench/app/FieldContract.js", "utf8"));
const C = window.FieldContract;
process.stdout.write(JSON.stringify({
  absent: C.display(null), empty: C.display(""), zero: C.display(0),
  start: C.date(null), end: C.date(""), readonly: C.blocked(null, "create")
}));
""")


def test_resource_dispatch_execution_scripts_are_loaded_by_responsibility() -> None:
    assert not RESOURCE_DISPATCH_TEMPLATE.exists()
    legacy = ["resource_dispatch_shared.js", "resource_dispatch_core.js", "resource_execution_context.js",
              "resource_execution_cards.js", "resource_execution_actual.js", "resource_execution_import.js",
              "resource_execution.js", "resource_dispatch_boot.js"]
    assert all(not (REPO_ROOT / "static/js" / name).exists() for name in legacy)
    order = json.loads(_source(REPO_ROOT / "scripts/workbench/build-order.json"))["live"]
    expected = ["FieldContract.js", "FieldAPI.js", "FieldControls.jsx", "FieldFilters.jsx",
                "FieldEditor.jsx", "FieldDetail.jsx", "FieldTable.jsx", "FieldFiles.jsx", "FieldWorkspace.jsx"]
    positions = [order.index(name) for name in expected]
    assert positions == sorted(positions)
    assert all((REPO_ROOT / "frontend/workbench/app" / name).is_file() for name in expected)


def test_task_card_uses_plain_fallback_when_part_is_missing() -> None:
    from web.viewmodels.scheduler_resource_dispatch_execution import build_task_card

    card = build_task_card(
        {
            "op_id": 10,
            "schedule_id": 100,
            "batch_id": "B1",
            "start_time": "2026-05-01 08:00:00",
            "end_time": "2026-05-01 09:00:00",
        },
        None,
        can_write_feedback=False,
        feedback_write_enabled=False,
    )

    assert card["part_label"] == "未填写图号或物料"
    assert card["actual_time_label"] == "暂未记录现场实际"
    assert card["actual_delta_summary"] == "暂未记录现场实际"


def test_execution_cards_render_dom_fallbacks_for_missing_part_and_operation() -> None:
    from web.viewmodels.scheduler_resource_dispatch_execution import build_task_card

    assert not (REPO_ROOT / "static/js/resource_execution_cards.js").exists()
    card = build_task_card({}, None, can_write_feedback=False, feedback_write_enabled=False)
    assert card["op_name"] == "工序"
    assert card["part_label"] == "未填写图号或物料"
    assert card["actual_start_time"] is None and card["actual_end_time"] is None
    assert card["actual_delta_summary"] == "暂未记录现场实际"
    assert card["task_key"] == "" and card["state_key"] == ""
    values = _field_fallbacks()
    assert values["absent"] == values["empty"] == values["start"] == values["end"] == "待补"
    assert values["zero"] == "0"
    assert values["readonly"] == "当前上下文不可写，请刷新并核对正式计划。"


def test_resource_dispatch_keeps_execution_inside_existing_page() -> None:
    from web.routes.workbench.legacy_page_contract import PAGE_POLICIES

    assert PAGE_POLICIES["scheduler.resource_dispatch_page"] == "retired"
    assert not RESOURCE_DISPATCH_TEMPLATE.exists()
    for relative in ("web/routes/domains/scheduler/scheduler_resource_dispatch.py",
                     "web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py",
                     "frontend/workbench/app/FieldWorkspace.jsx"):
        assert "/scheduler/resource-execution" not in _source(REPO_ROOT / relative)
    workspace = _source(REPO_ROOT / "frontend/workbench/app/FieldWorkspace.jsx")
    assert "<window.FieldTable " in workspace and "<window.FieldDetail " in workspace
    assert "<window.FieldFiles " in workspace


def test_execution_data_contains_part_time_delta_and_record_labels(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(
        f"/scheduler/resource-dispatch/execution/data?{_current_query()}"
    )
    payload = _json(resp)
    card = payload["data"]["tasks"][0]

    assert resp.status_code == 200
    assert card["part_no"] == "P001"
    assert card["part_name"] == "零件一"
    assert card["part_label"] == "P001 零件一"
    assert card["planned_time_label"] == "2026-05-01 08:00:00 ～ 2026-05-01 09:00:00"
    assert card["actual_time_label"] == "暂未记录现场实际"
    assert card["actual_start_delta_label"] == "暂未记录现场实际"
    assert card["actual_end_delta_label"] == "暂未记录现场实际"
    actions = {item["action"]: item for item in card["available_actions"]}
    assert actions["view_records"]["label"] == "查看现场记录"

    write_resp = client.post(
        f"/scheduler/resource-dispatch/execution/tasks/{card['task_key']}/actual?{_current_query()}",
        json=_base_payload(
            card,
            actual_start_time="2026-05-01 08:12:00",
            actual_finish_time="2026-05-01 08:58:00",
            quantity_done=9,
            idempotency_key="lane-contract-actual",
            remark="补录实际",
        ),
    )
    write_payload = _json(write_resp)
    updated = write_payload["data"]["task_card"]

    assert write_resp.status_code == 200
    assert updated["actual_time_label"] == "2026-05-01 08:12:00 ～ 2026-05-01 08:58:00"
    assert updated["actual_start_delta_label"] == "晚 12 分钟"
    assert updated["actual_end_delta_label"] == "早 2 分钟"
    assert updated["actual_delta_summary"] == "开工晚 12 分钟；完工早 2 分钟"

    events_resp = client.get(_events_url(card))
    events_payload = _json(events_resp)
    events = events_payload["data"]["events"]

    assert events_resp.status_code == 200
    assert len(events) == 2
    assert events[0]["record_source_label"] == "正式排程现场记录"
    assert events[0]["record_time"]
    assert events[0]["record_time_label"] == events[0]["record_time"]
    assert events[0]["record_time_label"] != "暂未记录落库时间"
    assert "source_table" not in events[0]


def test_nonformal_resource_dispatch_pages_do_not_emit_write_addresses(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    queries = [
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&date_from=2026-04-30&date_to=2026-05-06&version=1&plan_role=adopted",
        "scope_type=operator&operator_id=O2&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=baseline_best",
        _current_query() + "&scenario_id=scenario-plain",
    ]
    for query in queries:
        response = get_unchanged(client, "/scheduler/resource-dispatch?" + query, db_path)
        assert_retired(response, message=IDENTITY_UNAVAILABLE if "scenario_id=" in query else RETIRED_SCOPE)
        payload = _json(get_unchanged(client, "/scheduler/resource-dispatch/execution/data?" + query, db_path))
        assert payload["success"] is True
        assert payload["data"]["can_write_feedback"] is False
        assert "不能填写现场记录" in payload["data"]["disabled_reason"]
        assert all(action["action"] != "fill_actual"
                   for task in payload["data"]["tasks"] for action in task["available_actions"])
        blocked = get_unchanged(client, "/scheduler/resource-dispatch/execution/actual-template?" + query, db_path)
        assert blocked.status_code == 409 and blocked.get_json()["success"] is False
        assert blocked.get_json()["error"]["message"] == "当前不是最新正式采用方案，不能填写现场记录。"


def test_available_actions_reachable_write_gate_combos_stay_stable() -> None:
    # R08 收口护栏:写闸可达组合 (can_write, feedback_write_enabled) = (T,T)/(F,T)/(F,F)
    # 的动作清单与禁用文案必须零漂移;(T,F) 组合因 N1 同源不变式
    # (get_execution_context 两键同源、task_card 路由侧硬传 (True,True)) 生产不可达,不锁。
    from core.models.operation_execution_labels import (
        EXECUTION_ACTION_FILL_ACTUAL,
        EXECUTION_ACTION_VIEW_RECORDS,
    )
    from web.viewmodels.scheduler_resource_dispatch_execution import (
        build_available_actions,
        build_execution_payload,
    )

    tt = build_available_actions(
        can_write=True, feedback_write_enabled=True, status="in_progress", status_label="进行中"
    )
    assert [a["action"] for a in tt] == [EXECUTION_ACTION_FILL_ACTUAL, EXECUTION_ACTION_VIEW_RECORDS]
    assert tt[0]["enabled"] is True and tt[0]["disabled_reason"] == ""
    assert tt[1]["enabled"] is True

    tt_done = build_available_actions(
        can_write=True, feedback_write_enabled=True, status="completed", status_label="已完成"
    )
    assert tt_done[0]["enabled"] is False
    assert tt_done[0]["disabled_reason"] == "当前状态是已完成，不能填写实际情况。"

    for write_enabled in (True, False):
        readonly = build_available_actions(
            can_write=False, feedback_write_enabled=write_enabled, status="in_progress", status_label="进行中"
        )
        assert [a["action"] for a in readonly] == [EXECUTION_ACTION_VIEW_RECORDS]
        payload = build_execution_payload(
            {
                "plan_identity": {"label": "历史方案"},
                "can_write_feedback": False,
                "feedback_write_enabled": write_enabled,
                "rows": [],
                "states": {},
            }
        )
        assert payload["disabled_reason"] == "当前不是最新正式采用方案，不能填写现场记录。"
        assert payload["plan_identity"]["guardrail_text"] == "当前不是最新正式采用方案，不能填写现场记录。"

    payload_tt = build_execution_payload(
        {
            "plan_identity": {"label": "正式采用方案"},
            "can_write_feedback": True,
            "feedback_write_enabled": True,
            "rows": [],
            "states": {},
        }
    )
    assert payload_tt["disabled_reason"] == ""
    assert payload_tt["plan_identity"]["guardrail_text"] == ""


def test_empty_execution_cards_surface_public_degradation_message() -> None:
    from core.models.scheduler_degradation_messages import RESOURCE_POOL_BUILD_FAILED_MESSAGE
    from web.viewmodels.scheduler_resource_dispatch_execution import build_execution_payload

    payload = build_execution_payload(
        {
            "plan_identity": {"label": "正式采用方案"},
            "can_write_feedback": True,
            "feedback_write_enabled": True,
            "rows": [],
            "states": {},
            "degradation_events": [{"code": "resource_pool_degraded", "message": "/tmp/internal/raw"}],
        }
    )

    assert payload["tasks"] == []
    assert payload["degradation_message"] == RESOURCE_POOL_BUILD_FAILED_MESSAGE
    assert payload["degradation_events"]
    assert "当前查询范围内暂无现场记录任务卡" not in payload["degradation_message"]
    assert "/tmp/internal/raw" not in json.dumps(payload, ensure_ascii=False)
    assert not (REPO_ROOT / "static/js/resource_execution_cards.js").exists()


def test_positive_int_consolidated_to_execution_scope_strict_parser() -> None:
    # R09 收编 parity:A(service)/B(viewmodel) 两份 _positive_int 已委托 scope.py 收口点
    # parse_positive_execution_int。合法面与收编前零漂移;脏值面(5.9/3.0/True)按 O01 裁定
    # 统一严格化为 None——旧宽松 int() 截断(5.9→5)正是"现场记录写到错工序"的入口。
    from core.services.scheduler.resource_dispatch_execution_service import (
        _positive_int as service_positive_int,
    )
    from web.viewmodels.scheduler_resource_dispatch_execution import (
        _positive_int as viewmodel_positive_int,
    )

    for fn in (service_positive_int, viewmodel_positive_int):
        # 合法面(收编前后零漂移)
        assert fn(7) == 7
        assert fn("7") == 7
        assert fn(" 7 ") == 7
        assert fn(None) is None
        assert fn("") is None
        assert fn("abc") is None
        assert fn("5.9") is None
        assert fn(0) is None
        assert fn(-3) is None
        assert fn(False) is None
        # 严格面(O01 裁定的有意差异:旧宽松 int() 截断接受 5.9→5/True→1,现统一拒绝)
        assert fn(5.9) is None
        assert fn(3.0) is None
        assert fn(True) is None
