"""当前甘特图点击详情与只读行为。"""

import json
from pathlib import Path

from tests._support.gantt_current_js import run_current_js


def test_render_uses_adapter_options_and_keeps_readonly_click_popup() -> None:
    result = run_current_js(r"""
const data=h.fixture(), before=JSON.stringify(data), view=h.gantt(data), task=data.tasks[0];
const bar=view.nodes.find(node=>node.type==='button' && node.props['data-plan-task']===task.task_ref);
bar.props.onClick(); assert.strictEqual(view.selections[0].task,task);
assert.strictEqual(view.selections[0].before,false);
const trials=[], detail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,prepared:h.prepare(h.runtime.PlanGanttModel,data),selected:{task,before:false},onSelect:()=>{},
  renderTrial:value=>{trials.push(value);return null;},scope:{},query:'',disabled:false});
const text=h.text(detail);
for (const value of [task.batch_id,task.process_label,'Machine 1','Operator 1',h.runtime.WorkbenchFormat.compactDateTime(task.start),h.runtime.WorkbenchFormat.compactDateTime(task.end)]) assert(text.includes(value),value);
assert(h.walk(detail).some(node=>node.type==='aside' && node.props['aria-label']==='工序详情'));
assert.equal(trials.length,1); assert.equal(trials[0].label,'调整此工序');
assert.deepEqual(trials[0].taskOrigin,{plan_ref:data.plan.plan_ref,operation_ref:task.operation_ref,task_ref:task.task_ref});
assert.strictEqual(JSON.stringify(data),before);
assert.strictEqual(view.queries.length,0);
const routeData=h.processFixture();
routeData.tasks[0].piece_id=null; routeData.gantt_graph.nodes[0].piece_id=null;
const sibling={...routeData.gantt_graph.nodes[1],task_ref:h.reference(90),operation_ref:h.reference(91),piece_id:'piece-b',predecessor_operation_refs:[routeData.tasks[0].operation_ref]};
routeData.gantt_graph.nodes.push(sibling);
const selected=routeData.tasks[1], candidateTask={...selected,row_ref:selected.task_ref,batch_label:selected.batch_id,
  machine:{label:'Machine 1'},operator:{label:'Operator 1'},data_gaps:[],source:'internal',execution_at_generation:null};
for (const candidate of [false,true]) {
  let collapsed=0;
  const candidateData={tasks:[candidateTask],unplanned_operations:[],gantt_graph:routeData.gantt_graph};
  const props=candidate?{data:candidateData,prepared:h.prepare(h.runtime.RunCandidateModel,candidateData),task:candidateTask,onClose:()=>assert.fail('Collapse must retain selection')}:
    {data:routeData,prepared:h.prepare(h.runtime.PlanGanttModel,routeData),selected:{task:selected,before:false},onSelect:()=>assert.fail('Collapse must retain selection'),renderTrial:()=>null};
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
const zeroData={...data,tasks:data.tasks.map(row=>row.task_ref===zeroTask.task_ref?zeroTask:row)};
const zeroDetail=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data:zeroData,prepared:h.prepare(h.runtime.PlanGanttModel,zeroData),selected:{task:zeroTask,before:false},onSelect:()=>{},renderTrial:()=>null,onCollapse:()=>{}});
assert(h.text(zeroDetail).includes('本工序目标量0.00'),'A recorded zero must remain a quantity');
const generation=h.render(h.runtime.RunCandidateControls.Generation,{data:{
  candidate:{label:'候选A',status:'completed',completeness:'complete',candidate_ref:h.reference(301),data_gaps:[],blocked_reasons:[],
    metrics:Object.fromEntries(h.runtime.RunCandidateAPI.metricKeys.map(key=>[key,{value:0,reason:null}]))},
  generation:{run_ref:h.reference(302),accepted_at:'2026-05-11T07:00:00',finished_at:'2026-05-11T07:01:00',
    algorithm:{mode_label:'候选计算',strategy_label:null},
    input:{start_date:'2026-05-11',end_date:'2026-05-12',material_strategy:'strict',ready_check:false,hold_window:null,missing_resource_policy:'exclude',completed_policy:'preserve_actuals'},
    baseline:{captured_task_count:0},data_gaps:[]},data_gaps:[],blocked_reasons:[]
}});
assert(!h.walk(generation).some(node=>node.type==='dt'&&h.text(node)==='实际工时 / 成本'),'Candidate metrics must not invent an unavailable actual-hours/cost metric');
const missingNames={...candidateTask,machine:{ref:h.reference(401),label:null},operator:{ref:h.reference(402),label:null},supplier:null,
  data_gaps:[{field:'machine',code:'source_missing',message:'排产时设备目录已不存在。'},{field:'operator.label',code:'not_recorded',message:'排产时人员姓名未填写。'}]};
const candidateResourceData={tasks:[missingNames],unplanned_operations:[],gantt_graph:routeData.gantt_graph};
const resourcePanel=h.render(h.runtime.RunCandidateControls.Detail,{data:candidateResourceData,prepared:h.prepare(h.runtime.RunCandidateModel,candidateResourceData),task:missingNames,onCollapse:()=>{},onRelated:()=>{}});
for (const label of ['设备名称未记录：排产时设备目录已不存在。','人员名称未记录：排产时人员姓名未填写。']) {
  assert(h.text(resourcePanel).includes(label)); assert(h.runtime.RunCandidateModel.title(missingNames).includes(label));
}
for (const ref of [missingNames.machine.ref,missingNames.operator.ref])
  assert(h.walk(resourcePanel).some(node=>node.type==='code'&&h.text(node)===ref),'Known resource identity remains inspectable in the existing reference section');
const candidateLayout=value=>{const M=h.runtime.RunCandidateModel,B=h.runtime.RunBaselineModel,candidate=M.selectPrepared(M.groupPrepared(M.prepare(value),'machine'));
  return B.layoutPrepared(B.selectPrepared(candidate,B.groupPrepared(B.prepare(null),'machine'),'',null,false));};
const resourceLayout=candidateLayout({...candidateResourceData,task_span:{start:missingNames.start,end:missingNames.end}});
assert(resourceLayout.rows[0].label.includes('设备名称未记录'));
const untimed={...candidateTask,row_ref:h.reference(404),start:null,end:null,data_gaps:[{field:'start',code:'not_recorded',message:'正式归档未保存有效起止时间。'}]};
const archived={tasks:[candidateTask,untimed],unplanned_operations:[],gantt_graph:routeData.gantt_graph,task_span:{start:candidateTask.start,end:candidateTask.end}}, archivedBefore=JSON.stringify(archived);
const archivedLayout=candidateLayout(archived);
assert.deepEqual(archivedLayout.tasks,[candidateTask]); assert.deepEqual(archivedLayout.unplottableTasks,[untimed]);
assert(archivedLayout.rows.every(row=>row.items.every(item=>Number.isFinite(item.start)&&Number.isFinite(item.end))));
assert.strictEqual(JSON.stringify(archived),archivedBefore,'Unknown-time saved arrangements remain in the source task table');
const untimedData={tasks:archived.tasks,unplanned_operations:[],gantt_graph:routeData.gantt_graph};
const untimedPanel=h.render(h.runtime.RunCandidateControls.Detail,{data:untimedData,prepared:h.prepare(h.runtime.RunCandidateModel,untimedData),task:untimed,onCollapse:()=>{},onRelated:()=>{}});
assert(h.text(untimedPanel).includes('开始未记录') && h.text(untimedPanel).includes('结束未记录'));
assert(h.walk(untimedPanel).some(node=>node.type==='div'&&h.text(node).includes(untimed.data_gaps[0].message)),'The archive time gap remains inspectable in operation details');
const formalData={...archived,candidate:{candidate_ref:h.reference(405),label:'受理时正式计划 v1'},generation:{algorithm:null,baseline:{version:1}},
  reference:{kind:'admission_official',label:'受理时正式计划 v1'},gantt_graph:routeData.gantt_graph,delivery_risks:{items:[]},task_count:2};
const formalGantt=h.render(h.runtime.RunCandidateGantt,{data:formalData,prepared:h.prepare(h.runtime.RunCandidateModel,formalData),query:'',selected:untimed,comparison:null,onQuery:()=>{},onSelect:()=>{}});
assert(h.text(formalGantt).includes('正式归档') && h.text(formalGantt).includes('安排的时间缺项或无效'));
assert(!h.text(formalGantt).includes('算法排产结果'),'The official archive does not claim a newly computed algorithm result');
const focusedTask={...candidateTask,machine:{ref:h.reference(501),label:'Focus Machine'},operator:{ref:h.reference(502),label:'Focus Operator'}},
  otherResource={...candidateTask,row_ref:h.reference(503),machine:{ref:h.reference(504),label:'Other Machine'},operator:{ref:h.reference(505),label:'Other Operator'}};
const focusedData={...formalData,tasks:[focusedTask,otherResource],task_count:2}, sourceBefore=JSON.stringify(focusedData);
for (const kind of ['machine','operator']) {
  const focusedGantt=h.render(h.runtime.RunCandidateGantt,{data:focusedData,prepared:h.prepare(h.runtime.RunCandidateModel,focusedData),query:'',selected:null,comparison:null,onQuery:()=>{},onSelect:()=>{},resourceFocus:{kind,ref:focusedTask[kind].ref}});
  const lanes=h.walk(focusedGantt).filter(node=>node.type==='canvas'&&node.props['data-candidate-lane']);
  assert.equal(lanes.length,1,'A resource drill renders only the requested actual resource');
  assert.equal(lanes[0].props['data-item-count'],1); assert(lanes[0].props['aria-label'].includes(focusedTask[kind].label));
}
assert.strictEqual(JSON.stringify(focusedData),sourceBefore,'A resource drill keeps the complete saved arrangements immutable');
const external={...missingNames,source:'external',machine:null,operator:null,supplier:{ref:h.reference(403),label:'外协商A'},data_gaps:[]};
assert.equal(h.runtime.RunCandidateModel.resourceLabel(external,'machine'),'不适用（外协工序）');
assert.equal(h.runtime.RunCandidateModel.resourceLabel(external,'supplier'),'外协商A');
assert.equal(h.runtime.RunCandidateModel.resourceLabel({...external,row_ref:null,status:'unscheduled'},'operator'),'尚未安排');
assert(h.runtime.RunCandidateModel.resourceLabel({...external,data_gaps:[{field:'machine',message:'冻结身份资料缺失。'}]},'machine').includes('冻结身份资料缺失。'));
const missingQuantities={...candidateTask,quantity:null,batch_quantity:null,data_gaps:[
  {field:'execution_at_generation.target_quantity',code:'not_recorded',message:'生成时执行记录未保存目标数量。'},
  {field:'batch',code:'source_missing',message:'生成时批次原始记录缺失。'}]};
const quantityData={tasks:[missingQuantities],unplanned_operations:[],gantt_graph:routeData.gantt_graph};
const quantityPanel=h.render(h.runtime.RunCandidateControls.Detail,{data:quantityData,prepared:h.prepare(h.runtime.RunCandidateModel,quantityData),task:missingQuantities,onCollapse:()=>{},onRelated:()=>{}});
assert(h.text(quantityPanel).includes('本工序目标量生成时执行记录未保存目标数量。'),'Compact details expose the target-quantity source gap');
for (const message of missingQuantities.data_gaps.map(gap=>gap.message)) {
  assert(h.walk(quantityPanel).some(node=>node.type==='dd'&&h.text(node)===message));
  assert(h.runtime.RunCandidateModel.title(missingQuantities).includes(message));
}
assert.equal(h.runtime.RunCandidateModel.quantityLabel({...missingQuantities,quantity:0}),'0','A recorded zero overrides no-data explanations');
data.resources.push({ref:h.reference(202),label:'Original machine'});
data.projections.baseline={state:'available',items:[{operation_ref:task.operation_ref,change:'changed',before_in_scope:true,after_in_scope:true,
  before:{...task,start:'2026-05-11T07:00:00',end:'2026-05-11T10:00:00',machine_ref:h.reference(202)},after:task}]};
const comparison=h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,prepared:h.prepare(h.runtime.PlanGanttModel,data),selected:{task,before:false},onSelect:()=>{},renderTrial:()=>null,onCollapse:()=>{}});
const comparisonNodes=h.walk(comparison);
for (const value of ['延后 60 分钟','提前 60 分钟','Original machine → Machine 1'])
  assert(comparisonNodes.some(node=>node.type==='dd'&&h.text(node)===value),value);
assert(!comparisonNodes.some(node=>node.type==='dt'&&h.text(node)==='人员变化'),'Unchanged resources add no redundant change row');
// A real resource-table click opens the same formal plan/scope and leaves the source table restorable.
const resourceData=h.fixture(), navigated=[], remembered=[], initial={plan_ref:resourceData.plan.plan_ref,
  range_start:'2026-05-11T07:59:59.123400',range_end:'2026-05-11T12:00:00.654321',
  query:'source-only search',projection_tab:'load',projection_page:1};
Object.assign(resourceData.plan,{display_name:'Formal plan 5',is_current_official:true,completeness:'complete',capabilities:{view:true,export:true},blocked_reasons:[]});
Object.assign(resourceData.scope,{range_start:initial.range_start,range_end:initial.range_end});
Object.assign(resourceData.time_scope,{range_start:initial.range_start,range_end:initial.range_end});
const selectedResource={kind:'operator',resource_ref:resourceData.tasks[0].operator_ref,label:'Operator 1',
  available_hours:4,available_occupied_hours:2,utilization:.5,arranged_hours:2,occupied_hours:2,
  overlap_hours:0,outside_available_hours:0,has_overlap:false,issues:[],
  segments:resourceData.tasks.map(task=>({start:task.start,end:task.end,concurrent_operations:1}))};
const conflictData=h.fixture(), conflictResource={...selectedResource,metric_version:'decision-resource-v4',
  has_overlap:false,available_overlap_hours:0,overlap_hours:1,conflict_segments:[],
  segments:[{start:conflictData.tasks[0].start,end:conflictData.tasks[0].end,concurrent_operations:2}]};
conflictData.projections.occupancy={state:'available',plan_ref:conflictData.plan.plan_ref,basis:'selected_plan_only',
  time_scope:conflictData.time_scope,resources:[conflictResource],issues:[]};
assert.equal(h.runtime.PlanDetailsUI.conflictRows(conflictData).rows.length,0,'Natural reservation overlap outside the work calendar is not a calendar conflict');
Object.assign(conflictResource,{has_overlap:true,available_overlap_hours:.25,conflict_segments:[{
  start:'2026-05-11T08:15:00',end:'2026-05-11T08:30:00',concurrent_operations:2}]});
const calendarConflicts=h.runtime.PlanDetailsUI.conflictRows(conflictData).rows;
assert.equal(calendarConflicts.length,1); assert.equal(calendarConflicts[0].start,'2026-05-11T08:15:00');
assert.equal(calendarConflicts[0].end,'2026-05-11T08:30:00','The UI consumes the authoritative calendar segment without rebuilding natural-span conflicts');
resourceData.projections.occupancy.resources=Array.from({length:20},(_,index)=>({...selectedResource,
  resource_ref:h.reference(600+index),label:'Other resource '+index})).concat(selectedResource);
const resourceBefore=JSON.stringify(resourceData), oldQuery=h.runtime.APSResourceSession.useQuery,
  oldSnapshot=h.runtime.WorkbenchPageContext.useSnapshot;
const resourceResult={data:resourceData,meta:{as_of:'2026-05-11T12:00:00',snapshot_ref:'resource-read'},warnings:[]};
try {
  h.runtime.APSResourceSession.useQuery=(_read,dependencies)=>({loading:false,error:null,reload:()=>{},
    result:dependencies.length===3?resourceResult:{data:{plans:[resourceData.plan],page:{has_more:false}},warnings:[]}});
  h.runtime.WorkbenchPageContext.useSnapshot=value=>remembered.push(JSON.parse(JSON.stringify(value)));
  const props={view:'analysis',adapter:{catalog:async()=>{},workspace:async()=>{},export:async()=>{}},
    initialContext:initial,onNavigate:(target,context)=>navigated.push({target,context}),renderTrial:()=>null};
  const resourcePage=h.render(h.runtime.PlanWorkspace,props), resourceButton=h.walk(resourcePage)
    .find(node=>node.type==='button'&&h.text(node)==='Operator 1');
  assert(resourceButton,'The second resource page is restored before the resource is clicked');
  resourceButton.props.onClick({currentTarget:{}});
  assert.equal(navigated.length,1); assert.equal(navigated[0].target,'gantt');
  const target=navigated[0].context;
  for (const key of ['plan_ref','range_start','range_end','projection_tab','projection_page']) assert.equal(target[key],initial[key],key);
  assert.equal(target.resource_kind,'operator'); assert.equal(target.selected_task_ref,resourceData.tasks[0].task_ref);
  assert.equal(target.selected_task_side,'current');
  assert.equal(target.query,'','The resource opens by saved task identity rather than the source search text');
  const targetGantt=h.render(h.runtime.PlanGantt,{data:resourceData,prepared:h.prepare(h.runtime.PlanGanttModel,resourceData),asOf:resourceResult.meta.as_of,
    query:target.query,initialMode:target.resource_kind,selected:{task:resourceData.tasks[0],before:false,locate:true},onSelect:()=>{},onQuery:()=>{}});
  assert(h.walk(targetGantt).some(node=>node.props['aria-label']==='人员甘特时间轴'));
  assert(h.walk(targetGantt).some(node=>node.props['data-plan-task']===target.selected_task_ref&&node.props['aria-pressed']===true));
  const sourceContext=remembered[0];
  for (const key of Object.keys(initial)) assert.equal(sourceContext[key],initial[key],key);
  const returned=h.render(h.runtime.PlanWorkspace,{...props,initialContext:sourceContext});
  assert(h.walk(returned).some(node=>node.type==='table'&&node.props['aria-label']==='资源负荷列表'));
  assert(h.walk(returned).some(node=>node.type==='button'&&h.text(node)==='Operator 1'),'Return keeps the source resource page');
  assert.equal(JSON.stringify(resourceData),resourceBefore);
} finally {
  h.runtime.APSResourceSession.useQuery=oldQuery; h.runtime.WorkbenchPageContext.useSnapshot=oldSnapshot;
}
// A saved original task retains its own permanent identity and side on return.
const returnData=h.fixture(), originalTask={...returnData.tasks[0],plan_ref:h.reference(99),task_ref:h.reference(300),
  start:'2026-05-11T07:00:00',end:'2026-05-11T08:00:00'};
Object.assign(returnData.plan,{display_name:'Formal plan 5',is_current_official:true,completeness:'complete',capabilities:{view:true,export:true},blocked_reasons:[]});
returnData.projections.baseline={state:'available',baseline_plan:{...returnData.plan,plan_ref:originalTask.plan_ref,version:4},
  items:[{operation_ref:originalTask.operation_ref,change:'changed',before_in_scope:true,after_in_scope:true,before:originalTask,after:returnData.tasks[0]}]};
const returnResult={data:returnData,meta:{as_of:'2026-05-11T12:00:00',snapshot_ref:'return-read'},warnings:[]},
  returnedContexts=[], restoreEffects=[], oldEffect=h.runtime.React.useEffect;
try {
  h.runtime.APSResourceSession.useQuery=(_read,dependencies)=>({loading:false,error:null,reload:()=>{},
    result:dependencies.length===3?returnResult:{data:{plans:[returnData.plan],page:{has_more:false}},warnings:[]}});
  h.runtime.WorkbenchPageContext.useSnapshot=value=>returnedContexts.push(JSON.parse(JSON.stringify(value)));
  const props={view:'gantt',adapter:{catalog:async()=>{},workspace:async()=>{},export:async()=>{}},
    initialContext:{plan_ref:returnData.plan.plan_ref},onNavigate:()=>{},renderTrial:()=>null};
  const originalView=h.gantt(returnData,{states:{PlanGantt:{1:true}}});
  originalView.nodes.find(node=>node.type==='button'&&node.props['data-plan-task']===originalTask.task_ref).props.onClick();
  assert.equal(originalView.selections[0].task,originalTask); assert.equal(originalView.selections[0].before,true);
  h.render(h.runtime.PlanWorkspace,props,{WorkspaceSession:{7:{task:originalTask,before:true,result:returnResult}},PlanGantt:{1:true}});
  const saved=returnedContexts.pop();
  assert.equal(saved.selected_task_ref,originalTask.task_ref); assert.equal(saved.selected_task_side,'before');
  h.runtime.React.useEffect=(callback,dependencies)=>{if(dependencies&&dependencies.length===4&&dependencies[1]===returnResult)restoreEffects.push(callback);};
  const restore=context=>{
    restoreEffects.length=0;
    const page=h.render(h.runtime.PlanWorkspace,{...props,initialContext:context});
    for(const effect of restoreEffects)effect();
    return {page,updates:h.updates(),selected:h.updates().find(item=>item.name==='WorkspaceSession'&&item.index===7)};
  };
  const restored=restore(saved);
  assert(h.walk(restored.page).some(node=>node.props['data-plan-task']===originalTask.task_ref&&node.props['data-before']), 'The original lane is visible before the saved selection is applied');
  assert.equal(restored.selected.value.task,originalTask); assert.equal(restored.selected.value.before,true); assert.equal(restored.selected.value.locate,true);
  const selectedPage=h.render(h.runtime.PlanWorkspace,{...props,initialContext:saved},{WorkspaceSession:{7:restored.selected.value}});
  assert(h.walk(selectedPage).some(node=>node.props['data-plan-task']===originalTask.task_ref&&node.props['aria-pressed']===true));
  assert(h.walk(selectedPage).some(node=>node.props.className==='plan-muted plan-inspector-kind'&&h.text(node)==='原安排'));
  const cleared=returnedContexts[returnedContexts.length-1];
  assert.equal(cleared.selected_task_ref,originalTask.task_ref); assert.equal(cleared.selected_task_side,'before');
  returnData.projections.baseline.items[0].before_in_scope=false;
  const outside=restore(saved);
  assert.equal(outside.selected.value.task,originalTask); assert.equal(outside.selected.value.before,true);
  assert.equal(outside.selected.value.locate,undefined,'An original task outside the read scope restores detail without automatic location');
  const current=restore({...saved,selected_task_ref:returnData.tasks[0].task_ref,selected_task_side:undefined});
  assert.equal(current.selected.value.task,returnData.tasks[0]); assert.equal(current.selected.value.before,false,'Older contexts restore the current side');
  returnData.projections.baseline.items=[];
  const missing=restore(saved);
  assert(!missing.selected); assert.equal(missing.updates.find(item=>item.name==='WorkspaceSession'&&item.index===4).value.message,'要恢复的原安排已不存在。');
  const emptyContext=returnedContexts[returnedContexts.length-1];
  assert(!Object.hasOwn(emptyContext,'selected_task_ref')&&!Object.hasOwn(emptyContext,'selected_task_side'));
  returnData.plan_span.end_inclusive=true;
  const caption=h.runtime.PlanGanttModel.scopeCaption(returnData);
  assert(caption.includes('包含末端零工时工序'));
  Object.assign(returnData.scope,{range_start:returnData.time_scope.range_start,range_end:returnData.time_scope.range_end});
  assert(h.runtime.PlanGanttModel.scopeCaption(returnData).includes('不含结束时刻'));
  returnData.scope.range_start=null; returnData.scope.range_end=null; returnData.plan_span.start=returnData.plan_span.end;
  assert.equal(h.runtime.PlanGanttModel.scopeCaption(returnData),'计划时刻：'+h.runtime.PlanGanttModel.timeLabel(returnData.plan_span.end));
} finally {
  h.runtime.APSResourceSession.useQuery=oldQuery; h.runtime.WorkbenchPageContext.useSnapshot=oldSnapshot;
  h.runtime.React.useEffect=oldEffect;
}
return true;
""")
    assert result["result"] is True


def test_plan_detail_switches_to_out_of_scope_current_arrangement() -> None:
    result = run_current_js(r"""
const data=h.fixture(), current=data.tasks[0], original={...current,plan_ref:h.reference(99),task_ref:h.reference(300)},
  moved={...current,start:'2026-05-12T08:00:00',end:'2026-05-12T10:30:00'};
data.tasks=data.tasks.slice(1); data.task_count=data.tasks.length;
Object.assign(data.scope,{range_start:'2026-05-11T08:00:00',range_end:'2026-05-11T12:00:00'});
Object.assign(data.time_scope,{range_start:data.scope.range_start,range_end:data.scope.range_end});
data.plan_span={start:data.tasks[0].start,end:moved.end};
data.projections.baseline={state:'available',items:[{operation_ref:current.operation_ref,change:'changed',
  before_in_scope:true,after_in_scope:false,before:original,after:moved}]};
const prepared=h.prepare(h.runtime.PlanGanttModel,data), before=JSON.stringify(data), selections=[];
assert(!prepared.taskIndex.has(moved.task_ref),'The current arrangement outside the scope stays out of the plotted tasks');
let selected={task:original,before:true};
const render=()=>h.render(h.runtime.PlanDetailsUI.TaskDetail,{data,prepared,selected,renderTrial:()=>null,onSelect:(task,before)=>{
  selected={task,before}; selections.push(selected);
}});
const duration=tree=>{
  const nodes=h.walk(tree), label=nodes.findIndex(node=>node.type==='dt'&&h.text(node)==='安排时长');
  assert(label>=0 && nodes[label+1].type==='dd'); return h.text(nodes[label+1]);
};
let panel=render(); assert.equal(duration(panel),'1.00 小时');
h.walk(panel).find(node=>node.type==='button'&&h.text(node)==='查看当前安排').props.onClick({currentTarget:{}});
assert.strictEqual(selected.task,moved); assert.equal(selected.before,false);
panel=render(); assert.equal(duration(panel),'2.50 小时');
assert(h.text(panel).includes('当前安排已移出所选时间范围，仍显示完整起止时间。'));
h.walk(panel).find(node=>node.type==='button'&&h.text(node)==='查看原安排').props.onClick({currentTarget:{}});
assert.strictEqual(selected.task,original); assert.equal(selected.before,true);
assert.equal(duration(render()),'1.00 小时'); assert.equal(selections.length,2);
selected={task:data.tasks[0],before:false}; assert.equal(duration(render()),'1.00 小时');
assert.strictEqual(JSON.stringify(data),before,'Switching detail sides preserves the scoped task collection and saved comparison');
return true;
""")
    assert result["result"] is True


def test_formal_archive_detail_renders_full_saved_execution() -> None:
    """真实正式归档详情保留布尔完整性、空值、零计数和全部执行字段。"""
    payload = json.loads((Path(__file__).parent / "fixtures/admission_official_detail.json").read_text(encoding="utf-8"))
    result = run_current_js(r"""
const data=sourceData.data, before=JSON.stringify(data);
const task=data.tasks.find(row=>row.operation_ref==='33c238b3b8fe4c22dea83d88040a2babe5dbab3b83e851f7');
assert(task && task.execution_at_generation.records_complete===false && task.execution_at_generation.quantity_complete===false);
const detail=h.render(h.runtime.RunCandidateControls.Detail,{data,prepared:h.prepare(h.runtime.RunCandidateModel,data),task,onRelated:()=>{},onCollapse:()=>{}});
const nodes=h.walk(detail), facts=new Map(nodes.filter(node=>node.type==='div').map(node=>{
  const children=Array.isArray(node.children)?node.children.flat(Infinity):[node.children];
  return [children.find(child=>child&&child.type==='dt'),children.find(child=>child&&child.type==='dd')];
}).filter(([label,value])=>label&&value).map(([label,value])=>[h.text(label),h.text(value)]));
for (const [label,value] of Object.entries({
  '报工记录资料':'不完整','完成数量资料':'不完整','执行状态':'待报工','数据质量':'不完整',
  '目标数量':'7','已知完成数量':'0','剩余数量':'7','完成数量缺失记录数':'0','数量计算方式':'批',
  '最早实际开工时间':'保存时未记录最早实际开工时间。','确认完工时间':'保存时未记录确认完工时间。','完成依据':'保存时未记录完成依据。'
})) assert.equal(facts.get(label),value,label);
assert(nodes.some(node=>node.type==='summary'&&h.text(node)==='排产时的开工和完工记录'));
assert(nodes.every(node=>node.type!=='dt'||h.text(node)), 'Every saved execution field has a business label');
assert.strictEqual(JSON.stringify(data),before,'Detail formatting preserves all saved business facts');
for (const [workspace,label] of [[data,'正式归档'],[{...data,reference:undefined,generation:{...data.generation,algorithm:{mode_label:'候选计算',strategy_label:null}}},'新安排']]) {
  const gantt=h.render(h.runtime.RunCandidateGantt,{data:workspace,prepared:h.prepare(h.runtime.RunCandidateModel,workspace),query:'',selected:task,comparison:null,onQuery:()=>{},onSelect:()=>{}});
  const rendered=h.walk(gantt), kind=rendered.find(node=>node.props.className==='rc-lane-kind');
  const lane=rendered.find(node=>node.type==='canvas'&&node.props['data-candidate-lane']);
  const heading=rendered.find(node=>node.props.className==='rc-lane-label');
  assert(kind && lane && heading);
  assert.equal(h.text(kind),label); assert(lane.props['aria-label'].includes('，'+label+'，'));
  assert(heading.props.title.endsWith(' · '+label),'The visible lane and accessible name use the same saved identity');
}
return true;
""", payload)
    assert result["result"] is True
