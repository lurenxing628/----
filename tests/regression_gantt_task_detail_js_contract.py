"""回归测试（Node DOM 仿真）：甘特图点击任务条后，任务详情面板只展示公开中文标签（批次/图号或物料/工序/资源/计划与现场实际时间/超期提示/跳转链接），不得泄漏内部字段（op_id/schedule_id/source_table/scenario_id 等）；旧弹窗标题回退公开详情标题；后端缺 op_code 的任务也要渲染公开标题并保留工艺依赖连线。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_tasks import build_tasks

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_gantt_helpers():
    helper_path = REPO_ROOT / "tests" / "regression_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gantt_click_updates_stable_detail_without_showing_internal_fields() -> None:
    helpers = _load_gantt_helpers()
    node_code = f"""
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
loadScript({helpers._gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
state.cfg = {{
  view: "machine",
  startDate: "2026-05-01",
  endDate: "2026-05-01",
  weekStart: "2026-05-01",
}};
state.allTasks = [{{
  id: "T1",
  name: "op_123 一号设备 张三",
  start: "2026-05-01 08:00:00",
  end: "2026-05-01 09:00:00",
  progress: 0,
  dependencies: "",
  meta: {{
    batch_id: "B1",
    part_label: "P001 零件一",
    operation_label: "10（车削）",
    resource_label: "设备：M1 一号设备；人员：O1 张三",
    planned_time_label: "2026-05-01 08:00:00 ～ 2026-05-01 09:00:00",
    execution_status_label: "已完工",
    actual_start_time_label: "2026-05-01 08:12:00",
    actual_end_time_label: "2026-05-01 08:58:00",
    actual_summary_label: "现场状态：已完工；实际开工：2026-05-01 08:12:00；实际完工：2026-05-01 08:58:00",
    overdue_label: "已标记超期",
    delay_hint: "该批次已被标记为超期，建议查看超期清单或排产诊断。",
    is_overdue: true,
    due_date: "2026-05-01",
    detail_links: [
      {{ label: "查看资源排班", url: "/scheduler/resource-dispatch?version=2&batch_id=B1", disabled: false }},
      {{ label: "查看计划和现场实际", url: "/reports/execution-review?version=2&batch_id=B1", disabled: false }},
      {{ label: "查看超期清单", url: "/reports/overdue?version=2&batch_id=B1", disabled: false }}
    ],
    op_id: "OP-SECRET",
    schedule_id: "SCH-SECRET",
    source_table: "schedule",
    scenario_id: "SC-SECRET"
  }},
}}];
state.critical = {{
  ids: ["op_111", "op_222"],
  edges: [{{
    from: "op_111",
    to: "op_222",
    from_label: "10（车削）",
    to_label: "20（精加工）",
    edge_type: "process",
    reason: "工艺前驱",
    gap_minutes: 0
  }}],
  available: true
}};
state.ccIdSet = new Set();
state.ccPrevByTo = new Map();
state.ccEdgeMetaByTo = new Map();
state.calendarDays = [];
state.ui.mode = "view";
state.ui.zoomLevel = "hour";
state.ui.viewMode = "Hour";
state.ui.colorMode = "batch";
state.ui.depsMode = "critical";
state.ui.highlightCC = true;
state.ui.onlyOverdue = false;
state.ui.onlyExternal = false;
state.ui.filterBatch = "";
state.ui.filterResource = "";

ns.render();
const emptyText = document.getElementById("ganttTaskDetail").textContent;
state.gantt.options.on_click(state.currentTasks[0]);
const detail = document.getElementById("ganttTaskDetail");
process.stdout.write(JSON.stringify({{
  emptyText,
  detailText: detail.textContent,
  focusBatch: state.focusBatch,
}}));
"""
    result = helpers._run_node_json(node_code)
    detail_text = result["detailText"]

    assert "点击甘特条查看任务详情" in result["emptyText"]
    assert result["focusBatch"] == "B1"
    for text in (
        "批次",
        "B1",
        "图号或物料",
        "P001 零件一",
        "工序",
        "10（车削）",
        "资源",
        "设备：M1 一号设备；人员：O1 张三",
        "计划时间",
        "现场状态",
        "已完工",
        "实际开工",
        "2026-05-01 08:12:00",
        "实际完工",
        "2026-05-01 08:58:00",
        "已标记超期",
        "查看资源排班",
        "查看计划和现场实际",
        "查看超期清单",
    ):
        assert text in detail_text
    for hidden in ("op_123", "op_id", "schedule_id", "source_table", "scenario_id", "OP-SECRET", "SCH-SECRET", "SC-SECRET"):
        assert hidden not in detail_text


def test_legacy_popup_title_uses_public_detail_title_fallback() -> None:
    helpers = _load_gantt_helpers()
    node_code = f"""
{helpers.DOM_SHIM_JS}
loadScript({helpers._gantt_js()});
loadScript({helpers._gantt_color_js()});
loadScript({helpers._gantt_contract_js()});
loadScript({helpers._gantt_popup_js()});

const ns = window.__APS_GANTT__;
const popupText = ns.popup.buildTaskPopupHtml({{
  id: "op_123",
  name: "op_123 一号设备 张三",
  start: "2026-05-01 08:00:00",
  end: "2026-05-01 09:00:00",
  progress: 0,
  meta: {{
    operation_label: "10（车削）",
    _raw_name: "op_123 一号设备 张三",
    batch_id: "B1",
    part_label: "P001 零件一"
  }}
}}, {{ ids: [], edges: [], available: true }});
const legacyCriticalPopupText = ns.popup.buildTaskPopupHtml({{
  id: "op_456",
  name: "20（精加工） 一号设备 张三",
  start: "2026-05-01 09:00:00",
  end: "2026-05-01 10:00:00",
  progress: 0,
  meta: {{ operation_label: "20（精加工）" }}
}}, {{
  ids: ["op_123", "op_456"],
  edges: [{{ from: "op_123", to: "op_456", edge_type: "process", reason: "工艺前驱", gap_minutes: 0 }}],
  available: true
}});
process.stdout.write(JSON.stringify({{ popupText, legacyCriticalPopupText }}));
"""
    result = helpers._run_node_json(node_code)
    assert '<div class="title">10（车削）</div>' in result["popupText"]
    assert "op_123" not in result["popupText"]
    assert "前面影响它的工序：未命名工序" in result["legacyCriticalPopupText"]
    assert "op_123" not in result["legacyCriticalPopupText"]


def test_backend_missing_op_code_tasks_render_public_titles_and_keep_process_dependencies() -> None:
    wr = resolve_week_range(start_date="2026-05-01", end_date="2026-05-01")
    outcome = build_tasks(
        view="machine",
        wr=wr,
        rows=[
            {
                "schedule_id": 9001,
                "op_id": 111,
                "op_code": "",
                "batch_id": "B1",
                "piece_id": "piece-a",
                "part_no": "P001",
                "part_name": "零件一",
                "seq": 10,
                "op_type_name": "车削",
                "source": "internal",
                "op_status": "scheduled",
                "machine_id": "M1",
                "machine_name": "一号设备",
                "operator_id": "O1",
                "operator_name": "张三",
                "priority": "normal",
                "lock_status": "locked",
                "start_time": "2026-05-01 08:00:00",
                "end_time": "2026-05-01 09:00:00",
                "due_date": "2026-05-01",
            },
            {
                "schedule_id": 9002,
                "op_id": 222,
                "op_code": "",
                "batch_id": "B1",
                "piece_id": "piece-a",
                "part_no": "P001",
                "part_name": "零件一",
                "seq": 20,
                "op_type_name": "精加工",
                "source": "internal",
                "op_status": "scheduled",
                "machine_id": "M1",
                "machine_name": "一号设备",
                "operator_id": "O1",
                "operator_name": "张三",
                "priority": "normal",
                "lock_status": "locked",
                "start_time": "2026-05-01 09:00:00",
                "end_time": "2026-05-01 10:00:00",
                "due_date": "2026-05-01",
            },
        ],
        overdue_set=set(),
    )
    tasks = outcome.value
    assert [task["id"] for task in tasks] == ["op_111", "op_222"]
    assert tasks[1]["dependencies"] == "op_111"
    assert all("op_" not in task["name"] for task in tasks)

    helpers = _load_gantt_helpers()
    tasks_json = json.dumps(tasks, ensure_ascii=False)
    node_code = f"""
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
loadScript({helpers._gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
state.cfg = {{
  view: "machine",
  startDate: "2026-05-01",
  endDate: "2026-05-01",
  weekStart: "2026-05-01",
}};
state.allTasks = {tasks_json};
state.critical = {{
  ids: ["op_111", "op_222"],
  edges: [{{
    from: "op_111",
    to: "op_222",
    from_label: "10（车削）",
    to_label: "20（精加工）",
    edge_type: "process",
    reason: "工艺前驱",
    gap_minutes: 0
  }}],
  available: true
}};
state.ccIdSet = new Set();
state.ccPrevByTo = new Map();
state.ccEdgeMetaByTo = new Map();
state.calendarDays = [];
state.ui.mode = "view";
state.ui.zoomLevel = "hour";
state.ui.viewMode = "Hour";
state.ui.colorMode = "batch";
state.ui.depsMode = "process";
state.ui.highlightCC = true;
state.ui.onlyOverdue = false;
state.ui.onlyExternal = false;
state.ui.filterBatch = "";
state.ui.filterResource = "";

ns.render();
const second = state.currentTasks.find((task) => task.id === "op_222");
state.gantt.options.on_click(second);
const detailText = document.getElementById("ganttTaskDetail").textContent;
const popupText = ns.popup.buildTaskPopupHtml(second, state.critical);
process.stdout.write(JSON.stringify({{
  detailText,
  popupText,
  dependency: second.dependencies,
  rawName: second.meta._raw_name,
}}));
"""
    result = helpers._run_node_json(node_code)
    dependency = result["dependency"]
    if isinstance(dependency, list):
        assert dependency == ["op_111"]
    else:
        assert dependency == "op_111"
    assert result["rawName"].startswith("20（精加工）")
    assert "20（精加工）" in result["detailText"]
    assert "20（精加工）" in result["popupText"]
    assert "前面影响它的工序：10（车削）" in result["popupText"]
    for hidden in ("op_111", "op_222"):
        assert hidden not in result["detailText"]
        assert hidden not in result["popupText"]
