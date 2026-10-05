"""当前甘特图点击详情与只读行为。"""

from tests._support.gantt_current_js import run_current_js


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
