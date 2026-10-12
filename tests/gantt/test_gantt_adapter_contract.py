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
const routeData=h.processFixture();
routeData.tasks[0].piece_id=null; routeData.gantt_graph.nodes[0].piece_id=null;
const sibling={...routeData.gantt_graph.nodes[1],task_ref:h.reference(90),operation_ref:h.reference(91),piece_id:'piece-b'};
routeData.gantt_graph.nodes.push(sibling);
routeData.gantt_graph.edges.push({from_task_ref:routeData.tasks[0].task_ref,to_task_ref:sibling.task_ref,edge_type:'process'});
const selected=routeData.tasks[1], candidateTask={...selected,row_ref:selected.task_ref,batch_label:selected.batch_id,
  machine:{label:'Machine 1'},operator:{label:'Operator 1'},data_gaps:[],source:'internal',execution_at_generation:null};
for (const candidate of [false,true]) {
  let collapsed=0;
  const props=candidate?{data:{tasks:[candidateTask],gantt_graph:routeData.gantt_graph},task:candidateTask,onClose:()=>assert.fail('Collapse must retain selection')}:
    {data:routeData,selected:{task:selected,before:false},onSelect:()=>assert.fail('Collapse must retain selection')};
  const panel=h.render(candidate?h.runtime.RunCandidateControls.Detail:h.runtime.PlanDetailsUI.TaskDetail,
    {...props,onCollapse:()=>collapsed++,onRelated:()=>{}});
  const nodes=h.walk(panel), body=nodes.find(node=>node.props.className==='wb-gantt-detail-body');
  assert(body && !h.walk(body).some(node=>node.props.className==='wb-gantt-detail-header'),'The fixed header stays outside the scrolling body');
  nodes.find(node=>node.type==='button'&&h.text(node)==='收起详情').props.onClick({currentTarget:{}});
  assert.equal(collapsed,1);
  const groups=nodes.filter(node=>node.type==='details'&&node.props.className==='gantt-route-group');
  assert(groups.find(node=>h.text(node).includes('共同工序')).props.open);
  assert(groups.find(node=>h.text(node).includes('分件 piece-a')).props.open);
  assert(!groups.find(node=>h.text(node).includes('分件 piece-b')).props.open);
  assert(!nodes.some(node=>node.type==='summary'&&h.text(node)==='原安排对照'),'No empty comparison block without a baseline');
  assert(nodes.filter(node=>node.type==='details'&&node.props.className==='wb-gantt-detail-section').every(node=>!node.props.open));
  if (!candidate) assert(h.text(panel).includes('本工序目标量原计划未记录应做数量'), 'Missing quantity explains its captured source without opening another section');
}
const zeroTask={...task,quantity:0,batch_quantity:3,quantity_reason:null,quantity_basis:'run_admission'};
const zeroDetail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task:zeroTask,before:false},onSelect:()=>{},onCollapse:()=>{}});
assert(h.text(zeroDetail).includes('本工序目标量0.00'),'A recorded zero must remain a quantity');
const generation=h.render(h.runtime.RunCandidateControls.Generation,{data:{
  candidate:{label:'候选A',status:'completed',completeness:'complete',candidate_ref:h.reference(301),data_gaps:[],blocked_reasons:[],
    metrics:Object.fromEntries(h.runtime.RunCandidateAPI.metricKeys.map(key=>[key,{value:0,reason:null}]))},
  generation:{run_ref:h.reference(302),accepted_at:'2026-05-11T07:00:00',finished_at:'2026-05-11T07:01:00',
    input:{start_date:'2026-05-11',end_date:'2026-05-12',material_strategy:'strict',ready_check:false,hold_window:null,missing_resource_policy:'exclude',completed_policy:'preserve_actuals'},
    baseline:{captured_task_count:0},data_gaps:[]},data_gaps:[],blocked_reasons:[]
}});
assert(!h.walk(generation).some(node=>node.type==='dt'&&h.text(node)==='实际工时 / 成本'),'Candidate metrics must not invent an unavailable actual-hours/cost metric');
const missingNames={...candidateTask,machine:{ref:h.reference(401),label:null},operator:{ref:h.reference(402),label:null},supplier:null,
  data_gaps:[{field:'machine',code:'source_missing',message:'排产时设备目录已不存在。'},{field:'operator.label',code:'not_recorded',message:'排产时人员姓名未填写。'}]};
const resourcePanel=h.render(h.runtime.RunCandidateControls.Detail,{data:{tasks:[missingNames],gantt_graph:routeData.gantt_graph},task:missingNames,onCollapse:()=>{},onRelated:()=>{}});
for (const label of ['设备名称未记录：排产时设备目录已不存在。','人员名称未记录：排产时人员姓名未填写。']) {
  assert(h.text(resourcePanel).includes(label)); assert(h.runtime.RunCandidateModel.title(missingNames).includes(label));
}
for (const ref of [missingNames.machine.ref,missingNames.operator.ref])
  assert(h.walk(resourcePanel).some(node=>node.type==='code'&&h.text(node)===ref),'Known resource identity remains inspectable in the existing reference section');
const resourceLayout=h.runtime.RunCandidateModel.layout({tasks:[missingNames],task_span:{start:missingNames.start,end:missingNames.end}},'machine','');
assert(resourceLayout.rows[0].label.includes('设备名称未记录'));
const external={...missingNames,source:'external',machine:null,operator:null,supplier:{ref:h.reference(403),label:'外协商A'},data_gaps:[]};
assert.equal(h.runtime.RunCandidateModel.resourceLabel(external,'machine'),'不适用（外协工序）');
assert.equal(h.runtime.RunCandidateModel.resourceLabel(external,'supplier'),'外协商A');
assert.equal(h.runtime.RunCandidateModel.resourceLabel({...external,row_ref:null,status:'unscheduled'},'operator'),'尚未安排');
assert(h.runtime.RunCandidateModel.resourceLabel({...external,data_gaps:[{field:'machine',message:'冻结身份资料缺失。'}]},'machine').includes('冻结身份资料缺失。'));
const missingQuantities={...candidateTask,quantity:null,batch_quantity:null,data_gaps:[
  {field:'execution_at_generation.target_quantity',code:'not_recorded',message:'生成时执行记录未保存目标数量。'},
  {field:'batch',code:'source_missing',message:'生成时批次原始记录缺失。'}]};
const quantityPanel=h.render(h.runtime.RunCandidateControls.Detail,{data:{tasks:[missingQuantities],gantt_graph:routeData.gantt_graph},task:missingQuantities,onCollapse:()=>{},onRelated:()=>{}});
assert(h.text(quantityPanel).includes('本工序目标量生成时执行记录未保存目标数量。'),'Compact details expose the target-quantity source gap');
for (const message of missingQuantities.data_gaps.map(gap=>gap.message)) {
  assert(h.walk(quantityPanel).some(node=>node.type==='dd'&&h.text(node)===message));
  assert(h.runtime.RunCandidateModel.title(missingQuantities).includes(message));
}
assert.equal(h.runtime.RunCandidateModel.quantityLabel({...missingQuantities,quantity:0}),'0','A recorded zero overrides no-data explanations');
data.resources.push({ref:h.reference(202),label:'Original machine'});
data.projections.baseline={state:'available',items:[{operation_ref:task.operation_ref,change:'changed',before_in_scope:true,after_in_scope:true,
  before:{...task,start:'2026-05-11T07:00:00',end:'2026-05-11T10:00:00',machine_ref:h.reference(202)},after:task}]};
const comparison=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,selected:{task,before:false},onSelect:()=>{},onCollapse:()=>{}});
const comparisonNodes=h.walk(comparison);
for (const value of ['延后 60 分钟','提前 60 分钟','Original machine → Machine 1'])
  assert(comparisonNodes.some(node=>node.type==='dd'&&h.text(node)===value),value);
assert(!comparisonNodes.some(node=>node.type==='dt'&&h.text(node)==='人员变化'),'Unchanged resources add no redundant change row');
return true;
""")
    assert result["result"] is True
