"""Public task details on current components and retained legacy JSON builders.

Legacy execution/priority/link rows and popup critical-chain text are retired
UI, not new forecast facts. Their retained payload fields are checked separately
from the current plan inspector and frozen process-order relation controls.
"""

import copy

from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_tasks import build_tasks
from tests._support.gantt_current_js import run_current_js
from web.viewmodels.scheduler_gantt_public_payload import public_gantt_data_payload


def test_gantt_click_updates_stable_detail_without_showing_internal_fields() -> None:
    meta = {"batch_id": "B1", "part_label": "P001 零件一", "operation_label": "10（车削）",
            "resource_label": "设备：M1 一号设备；人员：O1 张三", "priority": "urgent", "source": "internal",
            "duration_minutes": 150, "execution_status_label": "已完工",
            "actual_start_time_label": "2026-05-01 08:12:00", "actual_end_time_label": "2026-05-01 08:58:00",
            "overdue_label": "已标记超期", "is_overdue": True,
            "detail_links": [{"label": "查看资源排班", "url": "/scheduler/resource-dispatch?version=2&batch_id=B1"},
                             {"label": "查看计划和现场实际", "url": "/reports/execution-review?version=2&batch_id=B1"},
                             {"label": "查看超期清单", "url": "/reports/overdue?version=2&batch_id=B1"}],
            "op_id": "OP-SECRET", "schedule_id": "SCH-SECRET", "source_table": "schedule", "scenario_id": "SC-SECRET"}
    original = copy.deepcopy(meta)
    public = public_gantt_data_payload({"tasks": [{"meta": meta}]})["tasks"][0]["meta"]
    for key in ("op_id", "schedule_id", "source_table", "scenario_id"):
        assert key not in public
    assert public == {key: value for key, value in original.items()
                      if key not in ("op_id", "schedule_id", "source_table", "scenario_id")}
    assert meta == original
    result = run_current_js(r"""
const data=h.fixture([['车削','2026-05-01T08:00:00','2026-05-01T09:00:00']]), task=data.tasks[0];
data.resources[0].label='一号设备'; data.resources[1].label='张三';
Object.assign(task,{op_id:'OP-SECRET',schedule_id:'SCH-SECRET',scenario_id:'SC-SECRET',source_table:'schedule',name:'op_123'});
const original=JSON.stringify(data);
const empty=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:null,onSelect:()=>{}});
assert(h.text(empty).includes('尚未选中任务'));
const view=h.gantt(data), bar=view.nodes.find(node=>node.type==='button' && node.props['data-plan-task']);
bar.props.onClick(); assert.strictEqual(view.selections[0].task,task);
const detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task,before:false},onSelect:()=>{}}), text=h.text(detail);
for (const label of ['任务详情','B1','10','车削','设备','一号设备','人员','张三','计划开始','2026-05-01 08:00:00','计划结束','2026-05-01 09:00:00','1 h']) assert(text.includes(label),label);
for (const value of ['op_123','op_id','schedule_id','source_table','scenario_id','OP-SECRET','SCH-SECRET','SC-SECRET']) assert(!text.includes(value),value);
assert.strictEqual(JSON.stringify(data),original);
return true;
""")
    assert result["result"] is True


def test_legacy_popup_title_uses_public_detail_title_fallback() -> None:
    result = run_current_js(r"""
const data=h.fixture([['车削','2026-05-01T08:00:00','2026-05-01T09:00:00']]), task=data.tasks[0];
task.name='op_123 一号设备 张三'; task.meta={_raw_name:task.name};
const title=h.runtime.PlanGanttModel.taskTitle(task,h.runtime.PlanGanttModel.names(data),false);
assert(title.includes('B1') && title.includes('10') && title.includes('车削'));
assert(!title.includes('op_123'));
const detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task,before:false},onSelect:()=>{}});
const text=h.text(detail);
assert(!text.includes('op_123') && text.includes('Frozen process order unavailable'));
assert(text.includes('未记录，无法核实'));
assert(!text.includes('已完工') && !text.includes('预计按期'));
assert.strictEqual(h.runtime.__APS_GANTT__,undefined);
return true;
""")
    assert result["result"] is True


def test_backend_missing_op_code_tasks_render_public_titles_and_keep_process_dependencies() -> None:
    rows = []
    for schedule_id, op_id, seq, label, start, end in (
        (9001, 111, 10, "车削", "2026-05-01 08:00:00", "2026-05-01 09:00:00"),
        (9002, 222, 20, "精加工", "2026-05-01 09:00:00", "2026-05-01 10:00:00"),
    ):
        rows.append({"schedule_id": schedule_id, "op_id": op_id, "op_code": "", "batch_id": "B1", "piece_id": "piece-a",
                     "part_no": "P001", "part_name": "零件一", "seq": seq, "op_type_name": label,
                     "source": "internal", "op_status": "scheduled", "machine_id": "M1", "machine_name": "一号设备",
                     "operator_id": "O1", "operator_name": "张三", "priority": "normal", "lock_status": "locked",
                     "start_time": start, "end_time": end, "due_date": "2026-05-01"})
    original = copy.deepcopy(rows)
    tasks = build_tasks(view="machine", wr=resolve_week_range(start_date="2026-05-01", end_date="2026-05-01"),
                        rows=rows, overdue_set=set()).value
    first_id = tasks[0]["id"]
    assert all(str(task["id"]).startswith("task_") for task in tasks)
    assert all("op_" not in str(task["id"]) for task in tasks)
    assert tasks[1]["dependencies"] == first_id
    assert all("op_" not in task["name"] for task in tasks)
    assert tasks[1]["name"].startswith("20（精加工）")
    assert rows == original
    result = run_current_js(r"""
const data=h.fixture(sourceData.map(task=>[task.meta.operation_label,task.start.replace(' ','T'),task.end.replace(' ','T')]));
data.projections.process_order={state:'available',basis:'run_admission',issues:[],items:data.tasks.map((task,index)=>({
  task_ref:task.task_ref,operation_ref:task.operation_ref,predecessor_operation_refs:index?[data.tasks[0].operation_ref]:[]}))};
assert(h.runtime.PlanProcessOrder.validate(data.projections.process_order,data));
const before=JSON.stringify(data), selected={task:data.tasks[1],before:false}, links=[];
const detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected,onSelect:()=>{},onRelated:ref=>links.push(ref)});
const text=h.text(detail);
assert(text.includes('20（精加工）') && text.includes('10（车削）'));
for (const hidden of ['op_111','op_222']) assert(!text.includes(hidden));
const previous=h.walk(detail).find(node=>node.type==='button' && String(node.props['aria-label']).startsWith('前序'));
previous.props.onClick(); h.equal(links,[data.tasks[0].task_ref]);
assert(h.runtime.PlanGanttModel.taskTitle(selected.task,h.runtime.PlanGanttModel.names(data),false).includes('20（精加工）'));
assert.strictEqual(JSON.stringify(data),before);
return true;
""", tasks)
    assert result["result"] is True
