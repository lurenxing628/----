"""Current Gantt bars select and inspect without editing dates or progress.

Retired Frappe readonly flags and popup handles are not current APIs. The
actual shipped bar and inspector contracts are exercised instead.
"""

from tests._support.gantt_current_js import run_current_js


def test_readonly_gantt_blocks_drag_resize_and_progress_events_but_keeps_click() -> None:
    result = run_current_js(r"""
const data=h.fixture(), before=JSON.stringify(data), view=h.gantt(data), bars=view.nodes.filter(node=>node.props['data-plan-task']);
const initial=bars.map(node=>h.clone(node.props.style));
for (const bar of bars) {
  for (const handler of ['onMouseDown','onMouseMove','onMouseUp','onPointerDown','onTouchStart','onDragStart','onDrop','onDateChange','onProgressChange']) assert.strictEqual(bar.props[handler],undefined);
  assert.notStrictEqual(bar.props.draggable,true);
  bar.props.onMouseEnter({clientX:300,clientY:200}); bar.props.onMouseLeave(); bar.props.onClick();
}
h.equal(bars.map(node=>node.props.style),initial);
assert.strictEqual(view.selections.length,bars.length);
assert(view.selections.every(row=>row.before===false && data.tasks.includes(row.task)));
assert(!view.nodes.some(node=>/handle|bar-progress/.test(node.props.className||'')));
assert.strictEqual(JSON.stringify(data),before);
return bars.length;
""")
    assert result["result"] == 2


def test_formal_render_passes_readonly_options_and_blocks_drag() -> None:
    result = run_current_js(r"""
const data=h.fixture(), task=data.tasks[0], before=JSON.stringify(data), view=h.gantt(data,{selected:{task,before:false}});
const bar=view.nodes.find(node=>node.type==='button' && node.props['data-plan-task']===task.task_ref);
assert.strictEqual(bar.props['aria-pressed'],true);
const initial=h.clone(bar.props.style), detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task,before:false},onSelect:()=>{}});
const text=h.text(detail);
assert(text.includes('计划开始') && text.includes('计划结束') && text.includes('当前所选计划安排'));
assert(text.includes(task.start.replace('T',' ')) && text.includes(task.end.replace('T',' ')));
assert(h.walk(detail).filter(node=>node.type==='input').length===0);
for (const node of view.nodes.filter(node=>node.props['data-plan-task'])) assert(!node.props.onMouseDown && !node.props.onDateChange && !node.props.onProgressChange);
bar.props.onClick(); h.equal(bar.props.style,initial);
assert.strictEqual(view.selections[0].task,task);
assert.strictEqual(JSON.stringify(data),before);
return true;
""")
    assert result["result"] is True


def main() -> None:
    test_readonly_gantt_blocks_drag_resize_and_progress_events_but_keeps_click()
    test_formal_render_passes_readonly_options_and_blocks_drag()
    print("OK")


if __name__ == "__main__":
    main()
