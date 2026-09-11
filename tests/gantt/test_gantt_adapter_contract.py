"""Current view/scenario rendering contracts after the Frappe adapter retirement.

The old simulate drag adapter has no new UI equivalent. Saved scenarios remain
readable and the separate validate/save services keep their own POST contracts.
"""

from tests._support.gantt_current_js import run_current_js


def test_adapter_builds_view_and_simulate_options_from_zoom_contract() -> None:
    result = run_current_js(r"""
const data=h.fixture(), before=JSON.stringify(data), checks=[];
for (const kind of ['official','scenario']) {
  const variant=h.clone(data); variant.plan.kind=kind;
  for (const zoom of [1,2,1024]) {
    const view=h.gantt(variant,{states:{PlanGantt:{2:zoom}}});
    const plus=view.nodes.find(node=>node.type==='button' && node.props['aria-label']==='放大时间轴');
    const minus=view.nodes.find(node=>node.type==='button' && node.props['aria-label']==='缩小时间轴');
    assert.strictEqual(!!plus.props.disabled,zoom===1024);
    assert.strictEqual(!!minus.props.disabled,zoom===1);
    plus.props.onClick(); minus.props.onClick();
    const values=h.updates().filter(item=>item.name==='PlanGantt' && item.index===2).map(item=>item.value);
    h.equal(values,[Math.min(1024,zoom*2),Math.max(1,zoom/2)]);
    for (const node of view.nodes.filter(node=>node.props['data-plan-task'])) {
      assert.strictEqual(node.type,'button'); assert.strictEqual(typeof node.props.onClick,'function');
      assert(!node.props.onDateChange && !node.props.onProgressChange && !node.props.onMouseDown);
    }
    checks.push([kind,zoom]);
  }
}
assert.strictEqual(JSON.stringify(data),before);
assert.strictEqual(h.runtime.APS_GANTT_ADAPTER,undefined);
return checks.length;
""")
    assert result["result"] == 6


def test_adapter_create_gantt_uses_vendor_geometry_without_copying_zoom_mapping() -> None:
    result = run_current_js(r"""
const M=h.runtime.PlanGanttModel, data=h.fixture([['36 minutes','2026-05-11T08:00:00','2026-05-11T08:36:00']]);
data.plan_span={start:'2026-05-11T08:00:00',end:'2026-05-11T12:00:00'};
const before=JSON.stringify(data), widths=[];
for (const zoom of [1,2,4,16,1024]) {
  const width=830*zoom, model=M.layout(data,'machine','',false,width);
  const view=h.gantt(data,{states:{PlanGantt:{2:zoom}}});
  const bar=view.nodes.find(node=>node.type==='button' && node.props['data-plan-task']);
  const item=model.rows[0].items[0];
  assert(Math.abs(bar.props.style.width-(item.end-item.start)/(model.end-model.start)*width)<0.001);
  assert.strictEqual(bar.props.style.left,0);
  assert(!view.nodes.some(node=>String(node.props.className||'').includes('handle')));
  widths.push(bar.props.style.width);
}
assert.strictEqual(widths[1],2*widths[0]); assert.strictEqual(widths[4],1024*widths[0]);
assert.strictEqual(JSON.stringify(data),before);
return widths;
""")
    assert len(result["result"]) == 5


def test_render_uses_adapter_options_and_keeps_readonly_click_popup() -> None:
    result = run_current_js(r"""
const data=h.fixture(), before=JSON.stringify(data), view=h.gantt(data), task=data.tasks[0];
const bar=view.nodes.find(node=>node.type==='button' && node.props['data-plan-task']===task.task_ref);
bar.props.onClick(); assert.strictEqual(view.selections[0].task,task);
assert.strictEqual(view.selections[0].before,false);
const detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task,before:false},onSelect:()=>{}});
const text=h.text(detail);
for (const value of [task.batch_id,task.process_label,'Machine 1','Operator 1',task.start.replace('T',' '),task.end.replace('T',' ')]) assert(text.includes(value),value);
assert(h.walk(detail).some(node=>node.type==='aside' && node.props['aria-label']==='任务详情'));
const command=h.walk(detail).find(node=>node.type==='button' && h.text(node).includes('调整此工序'));
assert(command.props.disabled);
assert.strictEqual(JSON.stringify(data),before);
assert.strictEqual(view.queries.length,0);
return true;
""")
    assert result["result"] is True


def main() -> None:
    test_adapter_builds_view_and_simulate_options_from_zoom_contract()
    test_adapter_create_gantt_uses_vendor_geometry_without_copying_zoom_mapping()
    test_render_uses_adapter_options_and_keeps_readonly_click_popup()
    print("OK")


if __name__ == "__main__":
    main()
