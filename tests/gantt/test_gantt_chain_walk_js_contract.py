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
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
// depsMode=critical 下 currentTasks.dependencies 被改写的反例：手动污染渲染副本
state.currentTasks = state.allTasks.map(t => Object.assign({}, t, { dependencies: "X9" }));
ns.chainWalk.selectTaskById("A2", { scroll: false });
const beforeNext = ns.chainWalk.currentTaskId();
ns.chainWalk.walkProcess(1);
const afterNext = ns.chainWalk.currentTaskId();
ns.chainWalk.walkProcess(-1);
ns.chainWalk.walkProcess(-1);
const afterPrev2 = ns.chainWalk.currentTaskId();
const headStuck = ns.chainWalk.walkProcess(-1); // 链头再退：false
process.stdout.write(JSON.stringify({ beforeNext, afterNext, afterPrev2, headStuck,
  detail: document.getElementById("ganttTaskDetail").textContent }));
""")
    assert result["beforeNext"] == "A2"
    assert result["afterNext"] == "A3"  # 原始 deps 反查，不受污染影响
    assert result["afterPrev2"] == "A1"
    assert result["headStuck"] is False


def test_critical_walk_skips_out_of_range_ids_with_notice():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
ns.chainWalk.selectTaskById("A1", { scroll: false });
ns.chainWalk.walkCritical(1); // A1 → X9 缺失跳过 → C1
const landed = ns.chainWalk.currentTaskId();
const detail = document.getElementById("ganttTaskDetail").textContent;
process.stdout.write(JSON.stringify({ landed, detail }));
""")
    assert result["landed"] == "C1"
    assert "已跳过 1 道当前范围外的工序" in result["detail"]


def test_critical_walk_dead_end_stays_with_honest_notice():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
state.critical = { ids: ["A1", "X9"], edges: [], available: true };
ns.chainWalk.selectTaskById("A1", { scroll: false });
const moved = ns.chainWalk.walkCritical(1); // X9 缺失且无后续：停原地（向后/下一道）
process.stdout.write(JSON.stringify({ moved, current: ns.chainWalk.currentTaskId(),
  detail: document.getElementById("ganttTaskDetail").textContent }));
""")
    assert result["moved"] is False
    assert result["current"] == "A1"
    # 越界提示按方向区分：walkCritical(1) 找下一道
    assert "关键链下一道工序在当前日期范围/筛选之外" in result["detail"]


def test_critical_walk_backward_dead_end_notice_says_previous():
    # walkCritical(-1) 找上一道越界：文案须说「上一道」，不再笼统说「后续」
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
state.critical = { ids: ["X0", "C1"], edges: [], available: true };
ns.chainWalk.selectTaskById("C1", { scroll: false });
const moved = ns.chainWalk.walkCritical(-1); // X0 缺失且无前驱：停原地（向前/上一道）
process.stdout.write(JSON.stringify({ moved, current: ns.chainWalk.currentTaskId(),
  detail: document.getElementById("ganttTaskDetail").textContent }));
""")
    assert result["moved"] is False
    assert result["current"] == "C1"
    assert "关键链上一道工序在当前日期范围/筛选之外" in result["detail"]


def test_filtered_out_target_renders_detail_with_view_notice():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
ns.chainWalk.selectTaskById("A1", { scroll: false });
const focusBefore = state.focusBatch;
state.currentTasks = state.allTasks.filter(t => t.meta.batch_id !== "BA"); // 前端筛掉 BA
ns.chainWalk.walkProcess(1); // A2 在 allTasks 但不在视图
process.stdout.write(JSON.stringify({ current: ns.chainWalk.currentTaskId(),
  focusBefore, focusAfter: state.focusBatch,
  detail: document.getElementById("ganttTaskDetail").textContent }));
""")
    assert result["current"] == "A2"
    assert "该工序不在当前筛选视图中" in result["detail"]
    # 视图外目标「只提示、不装饰」：focusBatch 不被改写（不触发整图变暗/高亮）
    assert result["focusAfter"] == result["focusBefore"]


def test_keydown_arrows_walk_critical_and_input_focus_skipped():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
ns.chainWalk.selectTaskById("A1", { scroll: false });
document.dispatchEvent(Object.assign(new FakeEvent("keydown"), { key: "ArrowRight" }));
const afterRight = ns.chainWalk.currentTaskId();
// INPUT 聚焦跳过：事件 target 是 input 节点
const input = document.createElement("input");
const evt = Object.assign(new FakeEvent("keydown"), { key: "ArrowLeft", target: input });
document.dispatchEvent(evt);
const afterInputLeft = ns.chainWalk.currentTaskId();
document.dispatchEvent(Object.assign(new FakeEvent("keydown"), { key: "ArrowLeft" }));
const afterLeft = ns.chainWalk.currentTaskId();
process.stdout.write(JSON.stringify({ afterRight, afterInputLeft, afterLeft }));
""")
    assert result["afterRight"] == "C1"  # 跳过 X9
    assert result["afterInputLeft"] == "C1"  # input 聚焦不动
    assert result["afterLeft"] == "A1"


def test_focus_batch_idempotent_and_walk_buttons_in_html():
    helpers = _load_gantt_helpers()
    result = _run(helpers, """
ns.chainWalk.selectTaskById("A1", { scroll: false });
const focus1 = state.focusBatch;
ns.chainWalk.selectTaskById("A1", { scroll: false }); // 再选同批次：不清聚焦（幂等）
const focus2 = state.focusBatch;
const htmlMid = ns.popup.buildTaskDetailHtml(state.allTasks[1], state.critical); // A2 有前有后
const htmlHead = ns.popup.buildTaskDetailHtml(state.allTasks[0], state.critical); // A1 链头
process.stdout.write(JSON.stringify({ focus1, focus2, htmlMid, htmlHead }));
""")
    assert result["focus1"] == "BA"
    assert result["focus2"] == "BA"  # 幂等：不再 toggle 清空
    # 按钮态断言：精确锁可用态完整属性串（非切片——属性顺序由实现固定输出）
    assert 'data-walk="prev" title=' in result["htmlMid"]  # A2 有前驱：可用态带 title 无 disabled
    assert 'data-walk="prev" disabled' not in result["htmlMid"]
    assert "不在关键链" in result["htmlMid"]  # A2 不在 critical.ids
    assert "关键链 1/3" in result["htmlHead"]  # A1 在链上
    assert 'data-walk="prev" disabled' in result["htmlHead"]  # 链头上一道禁用
    assert "已是本件第一道" in result["htmlHead"]
