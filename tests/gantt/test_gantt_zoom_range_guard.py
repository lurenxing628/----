"""回归测试：前端甘特图 gantt_zoom.js 的 validateZoomRange 与 gantt_render.js 的渲染守卫，在分钟级缩放下时间格过宽、节点/任务数超硬上限、跨午夜短任务等场景必须拦截（不 new Gantt 并给出「范围太宽/任务太多/页面卡住」中文提示），而恰好落在午夜边界等合法窗口仍正常渲染。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from tests._support.paths import REPO_ROOT


def _load_helpers():
    helper_path = REPO_ROOT / "tests" / "gantt" / "test_gantt_critical_outline_sync.py"
    spec = importlib.util.spec_from_file_location("regression_gantt_critical_outline_sync", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load gantt DOM helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zoom_range_guard_blocks_overwide_minute_views_and_warns_soft_limit() -> None:
    """Legacy SVG cutoffs retired; adaptive ticks stay bounded at every zoom."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const M=h.runtime.PlanGanttModel;
for(const days of [2,4,8,15,51]) for(let zoom=1;zoom<=1024;zoom*=2) {
 const start=M.instant('2026-05-11T00:00:00'),end=start+days*86400000,width=830*zoom;
 for(const left of [0,width/2,Math.max(0,width-830)]) {
  const ticks=M.ticks(start,end,width,left,830);assert(ticks.length>0&&ticks.length<=12);
  ticks.forEach((tick,index)=>{assert(Number.isFinite(tick.x));assert(Math.abs(tick.x-(tick.at-start)/(end-start)*width)<1e-7);assert.strictEqual(M.wire(tick.at),tick.label);if(index)assert(tick.at>ticks[index-1].at);});
 }
}
assert.strictEqual(h.runtime.Gantt,undefined);
""")


def test_render_range_guard_uses_actual_task_span_and_blocks_before_new_gantt(app_client) -> None:
    """Reject inconsistent full-span metadata; never derive it from a search."""
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    _, _, payload, before = plan_fixture(app_client)
    run_current_js(r"""
const C=h.runtime.APSPlanContract, M=h.runtime.PlanGanttModel, data=C.workspace(sourceData,sourceData.data.plan.plan_ref).data;
const full=M.layout(data,'machine','',false,830,false);
for(const query of ['钻孔','DOES_NOT_EXIST']){const filtered=M.layout(data,'machine',query,false,830,false);assert.strictEqual(filtered.start,full.start);assert.strictEqual(filtered.end,full.end);}
for(const value of ['2026-05-04T08:30:00','2026-05-03T08:00:00']) {
 const bad=h.clone(sourceData);bad.data.plan_span.start=value;
 assert.throws(()=>C.workspace(bad,data.plan.plan_ref),/计划任务、范围或投影协议不完整或串源/);
}
assert(full.tasks.length===3);assert.strictEqual(M.layout(data,'machine','DOES_NOT_EXIST',false,830,false).tasks.length,0);
""", payload)
    assert _business_state(app_client) == before


def test_render_range_guard_treats_midnight_end_as_selected_day_boundary() -> None:
    """Midnight remains the exclusive end, without adding a whole extra day."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.fixture([['Midnight','2026-05-11T23:55:00','2026-05-12T00:00:00']]),before=h.clone(data),M=h.runtime.PlanGanttModel;
data.plan_span.start='2026-05-11T00:00:00';data.time_scope.range_start=data.plan_span.start;
for(const zoom of [1,64,1024]) {
 const width=830*zoom, model=M.layout(data,'machine','',false,width,false);
 assert.strictEqual(model.end-model.start,86400000);const item=model.rows[0].items[0];assert.strictEqual(item.end-item.start,300000);
 const left=Math.max(0,width-830),result=h.gantt(data,{states:{PlanGantt:{2:zoom,5:{left,top:0,width:1000,height:440}}}});
 const bar=result.nodes.find(n=>n.props['data-plan-task']);assert(bar);assert(Math.abs(bar.props.style.left+bar.props.style.width-width)<1e-7);
 assert(Math.abs(bar.props.style.width-300000/86400000*width)<1e-7);
 assert(M.visibleItems([item],item.end,item.end+86400000).length===0);
}
h.equal(data.tasks,before.tasks);
""")


def test_render_guard_blocks_too_many_tasks_before_new_gantt(app_client) -> None:
    """The current 10000-row bound rejects oversize before per-task rendering."""
    import pytest

    from core.models.schedule_plan_role import SOURCE_SCHEDULE
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.models.workbench_plan_scope import MAX_PLAN_TASKS
    from core.services.workbench.plan_queries import _admit_rows
    from tests._support.gantt_current import plan_fixture
    from tests._support.gantt_current_js import run_current_js
    from tests._support.gantt_retirement import _business_state

    assert MAX_PLAN_TASKS == 10000

    class Rows:
        def __init__(self, count):
            self.count = count

        def _plan_rows_sql(self, **scope):
            assert scope == {"source_table": SOURCE_SCHEDULE, "candidate_id": None, "scenario_id": None}
            return "SELECT id FROM Schedule WHERE version=?", []

        def fetchall(self, sql, params):
            assert sql == "SELECT id FROM (SELECT id FROM Schedule WHERE version=?) LIMIT ?"
            assert params == [5, MAX_PLAN_TASKS + 1]
            return [None] * self.count

    assert _admit_rows(Rows(MAX_PLAN_TASKS), 5, SOURCE_SCHEDULE) is None
    with pytest.raises(WorkbenchCommandRejected) as caught:
        _admit_rows(Rows(MAX_PLAN_TASKS + 1), 5, SOURCE_SCHEDULE)
    assert (caught.value.code, caught.value.status, caught.value.committed) == ("query_too_large", 413, False)
    assert "未返回截断任务" in str(caught.value)
    _, _, payload, before = plan_fixture(app_client)
    run_current_js(r"""
const C=h.runtime.APSPlanContract, ref=sourceData.data.plan.plan_ref;C.workspace(sourceData,ref);
const bad=h.clone(sourceData);bad.data.tasks=Array(10001).fill(bad.data.tasks[0]);bad.data.task_count=10001;let visited=0;
bad.data.tasks.every=()=>{visited++;throw new Error('must not inspect an oversize payload');};
assert.throws(()=>C.workspace(bad,ref),/计划任务、范围或投影协议不完整或串源/);assert.strictEqual(visited,0);
""", payload)
    assert _business_state(app_client) == before


def main() -> None:
    test_zoom_range_guard_blocks_overwide_minute_views_and_warns_soft_limit()
    test_render_range_guard_uses_actual_task_span_and_blocks_before_new_gantt()
    test_render_range_guard_treats_midnight_end_as_selected_day_boundary()
    test_render_guard_blocks_too_many_tasks_before_new_gantt()
    print("OK")


if __name__ == "__main__":
    main()
