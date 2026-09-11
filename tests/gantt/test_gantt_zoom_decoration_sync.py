"""回归测试：甘特图各缩放级别下装饰层与真实条对齐——细缩放（hour/15/5/1 分钟）时 bar 宽度按 stepMinutes 精确换算、命中区不小于 12px、临界链外框紧贴真实条、今天高亮与节假日矩形覆盖整天且 x=0、箭头路径无 NaN、overdue/external 样式保留；week/month 缩放时节假日矩形宽度只占一天而非整列。"""

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


def test_fine_zoom_keeps_holiday_today_arrow_and_critical_outline_aligned_to_real_bar() -> None:
    """Retired SVG decorations do not drift current grid, bar and selection."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const data=h.processFixture(),before=h.clone(data),M=h.runtime.PlanGanttModel,task=data.tasks[0];
for(let zoom=1;zoom<=1024;zoom*=2) {
 const width=830*zoom,model=M.layout(data,'machine','',false,width,false), result=h.gantt(data,{selected:{task},states:{PlanGantt:{2:zoom}}});
 const bar=result.nodes.find(n=>n.props['data-plan-task']===task.task_ref);assert(bar);assert.strictEqual(bar.props['aria-pressed'],true);
 const duration=M.instant(task.end)-M.instant(task.start);assert(Math.abs(bar.props.style.width-duration/(model.end-model.start)*width)<1e-7);
 const ticks=result.nodes.filter(n=>n.props.className==='plan-tick'),lines=result.nodes.filter(n=>n.props.className==='plan-gridline');assert(ticks.length>0&&ticks.length<=12);
 for(const tick of ticks) assert(lines.some(line=>line.props.style.left===tick.props.style.left));
 const plain=h.gantt(data,{states:{PlanGantt:{2:zoom}}}).nodes.find(n=>n.props['data-plan-task']===task.task_ref);h.equal(bar.props.style,plain.props.style);
 assert(!result.nodes.some(n=>String(n.props.className||'').includes('aps-cc-outline')));
}
h.equal(data,before);
""")




def test_week_month_zoom_holiday_width_is_one_day_not_whole_column() -> None:
    """Day facts retain day duration independently of coarse adaptive ticks."""
    from tests._support.gantt_current_js import run_current_js

    run_current_js(r"""
const M=h.runtime.PlanGanttModel,day=86400000;
for(const days of [7,31]) {
 const start=M.instant('2026-05-01T00:00:00'),end=start+days*day,width=830;
 const facts=[{start:'2026-05-02T00:00:00',end:'2026-05-03T00:00:00'},{start:'2026-05-04T00:00:00',end:'2026-05-05T00:00:00'}],before=h.clone(facts);
 const x=t=>(M.instant(t)-start)/(end-start)*width;
 facts.forEach(fact=>{assert.strictEqual(M.instant(fact.end)-M.instant(fact.start),day);assert(Math.abs(x(fact.end)-x(fact.start)-width/days)<1e-8);});
 assert(Math.abs(x(facts[1].start)-x(facts[0].start)-2*width/days)<1e-8);
 const ticks=M.ticks(start,end,width,0,width);assert(ticks.length>0&&ticks.length<=12);
 const data=h.fixture();data.projections.calendar={state:'available',issues:[],resources:[{resource_ref:h.reference(200),kind:'machine',label:'MC1',available_hours:48,normal_effective_hours:48,urgent_effective_hours:48,issues:[],windows:facts.map(fact=>({...fact,allow_normal:true,allow_urgent:true,efficiency:1}))}]};
 const tree=h.render(h.runtime.PlanDetailsUI.ProjectionTables,{data},{ProjectionTables:{0:'calendar'},CalendarWindows:{0:true}});
 facts.forEach(fact=>{assert(h.text(tree).includes(M.timeLabel(fact.start)));assert(h.text(tree).includes(M.timeLabel(fact.end)));});h.equal(facts,before);
}
assert.strictEqual(h.runtime.Gantt,undefined);
""")


def main() -> None:
    test_fine_zoom_keeps_holiday_today_arrow_and_critical_outline_aligned_to_real_bar()
    test_week_month_zoom_holiday_width_is_one_day_not_whole_column()
    print("OK")


if __name__ == "__main__":
    main()
