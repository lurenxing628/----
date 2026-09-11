"""Short-task geometry and read-only selection on the current shipped renderer.

Frappe's resize/move callbacks, 12px hitbox and named zoom modes are retired.
The retained contracts are exact dates, visible positive geometry, selection and
consistent zoom. Names stay stable for gate identity and failure history.
"""

from tests._support.gantt_current_js import run_current_js


def test_frappe_gantt_keeps_short_tasks_visible_and_draggable() -> None:
    result = run_current_js(r"""
const data = h.fixture([
  ['T36','2026-05-11T08:00:00','2026-05-11T08:36:00'],
  ['T51','2026-05-11T08:51:36','2026-05-11T09:43:12'],
  ['T73','2026-05-11T10:00:00','2026-05-11T11:13:12'],
  ['T36MID','2026-05-11T23:24:00','2026-05-12T00:00:00']]);
const original = JSON.stringify(data), M = h.runtime.PlanGanttModel, rendered = h.gantt(data);
const bars = rendered.nodes.filter(node => node.type === 'button' && node.props['data-plan-task']);
assert.strictEqual(bars.length, 4);
for (const task of data.tasks) {
  const bar = bars.find(node => node.props['data-plan-task'] === task.task_ref);
  const expected = (M.instant(task.end) - M.instant(task.start)) / (M.instant(data.plan_span.end) - M.instant(data.plan_span.start)) * 830;
  assert(bar.props.style.width > 0);
  assert(Math.abs(bar.props.style.width - expected) < 0.001);
  assert(bar.props.title.includes(task.start.replace('T',' ')) && bar.props.title.includes(task.end.replace('T',' ')));
  for (const key of ['onDrag','onDragStart','onMouseDown','onTouchStart','onPointerDown','onResize','onProgressChange']) assert.strictEqual(bar.props[key], undefined);
  assert.notStrictEqual(bar.props.draggable, true);
  bar.props.onClick();
  const selected = rendered.selections[rendered.selections.length-1];
  assert.strictEqual(selected.task, task); assert.strictEqual(selected.before, false);
  const active = h.gantt(data, {selected:{task,before:false}}).nodes.find(node => node.props['data-plan-task'] === task.task_ref);
  assert.strictEqual(active.props['aria-pressed'], true);
}
assert.strictEqual(JSON.stringify(data), original);
assert.strictEqual(h.runtime.Gantt, undefined);
return bars.length;
""")
    assert result["result"] == 4


def test_frappe_gantt_supports_hour_and_minute_zoom_geometry() -> None:
    result = run_current_js(r"""
const M = h.runtime.PlanGanttModel, data = h.fixture([['T36','2026-05-11T08:00:00','2026-05-11T08:36:00']]);
data.plan_span = {start:'2026-05-11T00:00:00',end:'2026-05-12T00:00:00'};
const original = JSON.stringify(data), steps = [];
for (const zoom of [1,2,4,8,16,32,64,128,256,512,1024]) {
  const width = 830 * zoom, left = 8 / 24 * width;
  const view = h.gantt(data, {states:{PlanGantt:{2:zoom,5:{left,top:0,width:1000,height:440}}}});
  const bar = view.nodes.find(node => node.type === 'button' && node.props['data-plan-task']);
  assert(bar); assert(Math.abs(bar.props.style.width - 36 / 1440 * width) < 0.001);
  assert(Math.abs(bar.props.style.left - 8 / 24 * width) < 0.001);
  const ticks = M.ticks(M.instant(data.plan_span.start),M.instant(data.plan_span.end),width,left,830);
  assert(ticks.length > 0 && ticks.length < 12);
  for (const tick of ticks) assert(Math.abs(tick.x - (tick.at-M.instant(data.plan_span.start))/86400000*width) < 0.001);
  if (ticks.length > 1) steps.push(ticks[1].at-ticks[0].at);
}
assert(steps.some(step => step === 3600000));
assert(steps.some(step => step <= 60000));
assert.strictEqual(JSON.stringify(data), original);
return steps;
""")
    assert len(result["result"]) == 11


def test_short_task_width_matrix_covers_all_readonly_zoom_levels_and_midnight_edges() -> None:
    result = run_current_js(r"""
const M = h.runtime.PlanGanttModel, data = h.fixture([
  ['T51','2026-05-11T00:05:00','2026-05-11T00:56:00'],
  ['T36','2026-05-11T08:00:00','2026-05-11T08:36:00'],
  ['T73','2026-05-11T10:00:00','2026-05-11T11:13:00'],
  ['T36MID','2026-05-11T23:24:00','2026-05-12T00:00:00'],
  ['T30CROSS','2026-05-11T23:45:00','2026-05-12T00:15:00']]);
const original = JSON.stringify(data), start=M.instant(data.plan_span.start), end=M.instant(data.plan_span.end);
let checked=0;
for (const zoom of [1,2,4,8,16,32,64,128,256,512,1024]) for (const task of data.tasks) {
  const width=830*zoom, left=Math.max(0,Math.min(width-830,(M.instant(task.start)-start)/(end-start)*width-20));
  const view=h.gantt(data,{query:task.process_label,states:{PlanGantt:{2:zoom,5:{left,top:0,width:1000,height:1000}}}});
  const bar=view.nodes.find(node=>node.type==='button' && node.props['data-plan-task']===task.task_ref);
  assert(bar, task.process_label+' must be rendered in its selected viewport');
  assert(bar.props.style.width>0);
  assert(Math.abs(bar.props.style.width-(M.instant(task.end)-M.instant(task.start))/(end-start)*width)<0.001);
  assert(Math.abs(bar.props.style.left-(M.instant(task.start)-start)/(end-start)*width)<0.001);
  bar.props.onClick(); assert.strictEqual(view.selections[0].task,task);
  assert.strictEqual(M.wire(M.instant(task.start)),task.start);
  assert.strictEqual(M.wire(M.instant(task.end)),task.end);
  checked++;
}
assert.strictEqual(JSON.stringify(data),original);
return checked;
""")
    assert result["result"] == 11 * 5


def main() -> None:
    test_frappe_gantt_keeps_short_tasks_visible_and_draggable()
    test_frappe_gantt_supports_hour_and_minute_zoom_geometry()
    test_short_task_width_matrix_covers_all_readonly_zoom_levels_and_midnight_edges()
    print("OK")


if __name__ == "__main__":
    main()
