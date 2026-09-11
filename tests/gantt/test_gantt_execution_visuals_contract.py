"""甘特现场事实可视化 payload 契约（fusion-gantt-execution-visuals）。

钉死点（4.10）：progress 只允许 completed→100（禁部分进度）；execution-<status>
着色类按四态白名单追加（not_started 假记录/未知码零类——DOM class 不收垃圾串）；
无事实工序 payload 与现状逐字节一致（preview 身份自动满足）；meta 键集零新增
（raw 状态码不进 meta，只在服务端拼 class 时消费一次）。
"""

from __future__ import annotations

from types import SimpleNamespace

from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_tasks import build_tasks

_WR = resolve_week_range(start_date="2026-05-01", end_date="2026-05-01")


def _row(op_id=123):
    return {
        "schedule_id": 9001,
        "op_id": op_id,
        "op_code": "B1-20",
        "batch_id": "B1",
        "piece_id": "piece-a",
        "part_no": "P1",
        "part_name": "零件1",
        "seq": 20,
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
        "end_time": "2026-05-01 12:00:00",
        "due_date": "2026-05-30",
    }


def _fact(status, *, start=None, end=None):
    return SimpleNamespace(actual_status=status, actual_start_time=start, actual_end_time=end)


def _one_task(facts=None):
    outcome = build_tasks(
        view="machine", wr=_WR, rows=[_row()], overdue_set=set(), execution_facts_by_op_id=facts
    )
    return outcome.value[0]


def test_completed_fact_sets_progress_100_and_class():
    task = _one_task({123: _fact("completed", start="2026-05-01 08:05:00")})
    assert task["progress"] == 100
    assert "execution-completed" in task["custom_class"].split()


def test_processing_paused_exception_keep_progress_zero_with_class():
    for status in ("processing", "paused", "exception"):
        task = _one_task({123: _fact(status, start="2026-05-01 08:05:00")})
        assert task["progress"] == 0, status
        assert f"execution-{status}" in task["custom_class"].split(), status


def test_no_fact_payload_identical_to_baseline():
    baseline = _one_task(facts=None)
    no_fact = _one_task(facts={})
    assert baseline == no_fact  # 无事实=计划行原样（preview 身份自动满足）
    # 冻结关键字段期望值（不是只比两条新路径相等——锁改动前的旧 payload 语义）
    assert baseline["progress"] == 0
    assert baseline["custom_class"] == "priority-normal"
    assert baseline["meta"]["execution_status_label"] == "待开工"
    assert baseline["meta"]["actual_summary_label"] == "暂未记录现场实际"


def test_not_started_fake_record_gets_no_class():
    # 假数据拼出「有实际时间但状态 not_started」：has_record 为真但不在四态白名单
    task = _one_task({123: _fact("not_started", start="2026-05-01 08:05:00")})
    assert task["progress"] == 0
    assert "execution-" not in task["custom_class"]


def test_unknown_status_code_gets_no_class_no_progress():
    task = _one_task({123: _fact("weird_code", start="2026-05-01 08:05:00")})
    assert task["progress"] == 0
    assert "execution-" not in task["custom_class"]


def test_meta_keys_unchanged_no_raw_status_leak():
    with_fact = _one_task({123: _fact("processing", start="2026-05-01 08:05:00")})
    without = _one_task(facts=None)
    assert set(with_fact["meta"].keys()) == set(without["meta"].keys())  # meta 键集零新增
    assert "actual_status" not in with_fact["meta"]  # raw 码不出服务端
    assert with_fact["meta"]["execution_status_label"] == "生产中"


# ---------- CSS 写法契约（选择器语义钉死，防重排/拆规则漏值） ----------

_CSS = None


def _css() -> str:
    global _CSS
    if _CSS is None:
        from tests._support.gantt_current_js import run_current_js

        _CSS = run_current_js("return h.text(h.render(h.runtime.PlanLayout, {}));")["result"]
    return _CSS


def test_css_completed_overlay_covers_normal_hover_active_with_values():
    from tests._support.gantt_current_js import run_current_js

    fact = _one_task({123: _fact("completed", start="2026-05-01 08:05:00")})
    assert fact["progress"] == 100 and "execution-completed" in fact["custom_class"].split()
    # The plan canvas no longer overlays actual progress. Completion must not
    # silently become an on-time forecast or change selected task geometry.
    result = run_current_js(r"""
const data=h.fixture(), task=data.tasks[0]; Object.assign(task,{progress:100,custom_class:'execution-completed'});
const before=JSON.stringify(data), view=h.gantt(data), bar=view.nodes.find(node=>node.props['data-plan-task']===task.task_ref);
assert(bar.props.className.includes('primary') && !bar.props.className.includes('success'));
assert(!view.nodes.some(node=>/bar-progress|execution-completed/.test(node.props.className||'')));
bar.props.onMouseEnter({clientX:100,clientY:100}); bar.props.onClick();
const active=h.gantt(data,{selected:{task,before:false}}).nodes.find(node=>node.props['data-plan-task']===task.task_ref);
h.equal(active.props.style,bar.props.style); assert(active.props['aria-pressed']);
assert.strictEqual(JSON.stringify(data),before);
return true;
""")
    assert result["result"] is True
    assert ".plan-bar[aria-pressed=true] .plan-bar-face,.plan-bar:focus-visible .plan-bar-face" in _css()
    assert "box-shadow:inset 0 0 0 2px var(--wb-gantt-gold)" in _css()


def test_css_execution_strokes_guarded_by_not_overdue():
    from tests._support.gantt_current_js import run_current_js

    css = _css()
    for status in ("processing", "paused", "exception"):
        task = _one_task({123: _fact(status, start="2026-05-01 08:05:00")})
        assert task["progress"] == 0 and "execution-" + status in task["custom_class"].split()
    result = run_current_js(r"""
const M=h.runtime.PlanGanttModel, data=h.fixture(), task=data.tasks[0];
for (const status of ['processing','paused','exception','completed']) {
  task.custom_class='execution-'+status;
  assert.strictEqual(M.tone(task,new Set(),new Map([[task.batch_id,'overdue']])),'critical');
  assert.strictEqual(M.tone(task,new Set([task.task_ref]),new Map([[task.batch_id,'on_time']])),'critical');
  assert.strictEqual(M.tone(task,new Set(),new Map()),'primary');
}
return true;
""")
    assert result["result"] is True
    assert ".plan-bar.critical .plan-bar-face { background:var(--wb-gantt-critical-fill); border-color:var(--wb-gantt-critical-edge); }" in css
    assert ".plan-bar.conflict .plan-bar-face { border-style:dashed; }" in css


def test_css_dark_block_restates_execution_and_overdue_strokes():
    from tests._support.paths import REPO_ROOT

    css = _css()
    theme = (REPO_ROOT / "static/workbench/prototype/ui_kits/workbench/gantt-theme.css").read_text(encoding="utf-8")
    light, dark = theme.split('html[data-theme="dark"]', 1)
    for token, light_value, dark_value in (
        ("primary-edge", "#6085ac", "#7aa0c6"), ("critical-edge", "#b25f69", "#c38796"),
        ("success-edge", "#527f70", "#77a795"), ("gold", "#9b7d32", "#d7ba76"),
    ):
        assert "--wb-gantt-" + token + ":" + light_value in light
        assert "--wb-gantt-" + token + ":" + dark_value in dark
        assert "var(--wb-gantt-" + token + ")" in css
    assert "execution-processing" not in css and "execution-completed" not in css
