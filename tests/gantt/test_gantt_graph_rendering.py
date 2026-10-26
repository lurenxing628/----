"""Shipped plan and candidate components keep hover and selection wired to edges."""

from tests._support.gantt_current_js import run_current_js


def test_actual_critical_chain_reuses_prepared_nodes_across_renders():
    result = run_current_js(r"""
const data=h.processFixture(), index=h.runtime.GanttGraph.create(data.gantt_graph), located=[];
const expected=data.gantt_graph.critical_task_refs.slice();
Object.defineProperty(data.gantt_graph,'nodes',{get(){throw Error('Critical-chain rendering must consume the prepared node index');}});
for (const items of [data.tasks.map(task=>({task})),[],data.tasks.slice(0,1).map(task=>({task}))]) {
  const tree=h.render(h.runtime.ActualGanttControls.Chain,{index,model:{shownRefs:new Set(items.map(item=>item.task.task_ref))},onLocate:ref=>located.push(ref)});
  const buttons=h.walk(tree).filter(node=>node.props['data-chain-node']);
  assert.deepEqual(buttons.map(node=>node.props['data-chain-node']),expected);
  for (const button of buttons) {
    const node=index.nodes.get(button.props['data-chain-node']);
    assert(h.text(button).includes(node.batch_id));
    assert(h.text(button).includes(node.process_label));
  }
  assert.equal(h.walk(tree).filter(node=>node.props['data-chain-edge-reason']).length,index.graph.critical_edges.length);
  buttons[0].props.onClick({currentTarget:{}});
  assert.equal(located.at(-1),expected[0]);
  if (!items.length) assert(buttons.every(button=>h.text(button).includes('当前视图外')));
}
return true;
""")
    assert result["result"] is True


def test_shipped_gantts_highlight_complete_route_on_hover_and_keep_clicked_route():
    result = run_current_js(r"""
const plan=h.processFixture();
const candidate={tasks:plan.tasks.map(task=>({...task,row_ref:task.task_ref,batch_ref:h.reference(300),batch_label:task.batch_id,
  machine:{ref:task.machine_ref,label:'Machine 1'},operator:{ref:task.operator_ref,label:'Operator 1'},supplier:null,
  source:'internal',data_gaps:[]})),task_count:plan.task_count,task_span:plan.plan_span,candidate_span:plan.plan_span,unplanned_operations:[],
  delivery_risks:{items:[]},candidate:{label:'测试候选'},
  generation:{algorithm:{mode_label:'测试算法',strategy_label:null},baseline:{version:1,captured_at:'2026-05-11T08:00:00'}},
  gantt_graph:{...plan.gantt_graph,scope:'full_candidate'}};
for (const isCandidate of [false,true]) {
  const component=isCandidate?'RunCandidateGantt':'PlanGantt', data=isCandidate?candidate:plan;
  const choices=[], props={data,prepared:h.prepare(h.runtime[isCandidate?'RunCandidateModel':'PlanGanttModel'],data),query:'',selected:null,onSelect:(task,before)=>choices.push(isCandidate?task:{task,before}),
    onQuery:()=>{},asOf:'2026-05-11T12:00:00'};
  const render=states=>h.render(h.runtime[component],props,states||{});
  const edges=tree=>h.walk(tree).filter(node=>node.props['data-gantt-edge']);
  let tree=render();
  assert.equal(edges(tree).length,0,component+' starts with clear critical marks and no global lines');
  assert(h.walk(tree).some(node=>node.props.className==='wb-gantt-route-caption'),'The hover caption reserves its slot before interaction');
  assert(h.walk(tree).some(node=>node.type==='button'&&h.text(node.children)==='清除工艺聚焦'&&node.props.disabled),'The clear action reserves its slot before interaction');
  if (!isCandidate) assert.equal(h.walk(tree).filter(node=>node.props['data-gantt-critical']).length,3);
  const target=h.walk(tree).find(node=>isCandidate?node.props['data-candidate-lane']:
    node.props['data-plan-task']===data.tasks[1].task_ref);
  const pointer={clientX:300,clientY:20};
  (isCandidate?target.props.onMouseMove:target.props.onMouseEnter)(pointer);
  const hover=h.updates().find(update=>update.name===component&&update.value&&
    (isCandidate?update.value.taskRef:update.value.task));
  assert(hover,component+' hover reaches the owning component');
  tree=render({[component]:{[hover.index]:hover.value}});
  assert.equal(edges(tree).filter(node=>node.props['data-gantt-edge-kind']==='related').length,2);
  assert(h.text(tree).includes('完整工艺')&&h.text(tree).includes('3 道'));
  if (!isCandidate) assert.equal(h.walk(tree).filter(node=>node.props['data-gantt-related']).length,3);
  target.props.onClick(pointer);
  assert.equal(choices.length,1);
  props.selected=choices[0];
  // No hover override: after the mouse leaves, the persisted selection owns the route.
  tree=render();
  assert.equal(edges(tree).filter(node=>node.props['data-gantt-edge-kind']==='related').length,2);
  if (!isCandidate) assert.equal(h.walk(tree).filter(node=>node.props['data-gantt-related']).length,3);
}
return true;
""")
    assert result["result"] is True


def test_printed_gantt_connections_travel_with_each_paginating_row():
    result = run_current_js(r"""
const plan=h.processFixture();
plan.tasks.forEach((task,index)=>task.machine_ref=h.reference(200+index));
plan.resources=plan.tasks.map((task,index)=>({ref:task.machine_ref,label:'Machine '+index,business_code:'M'+index}));
const candidate={tasks:plan.tasks.map(task=>({...task,row_ref:task.task_ref,batch_ref:h.reference(300),batch_label:task.batch_id,
  machine:{ref:task.machine_ref,label:'Machine'},operator:{ref:task.operator_ref,label:'Operator'},supplier:null,
  source:'internal',data_gaps:[]})),task_count:plan.task_count,task_span:plan.plan_span,candidate_span:plan.plan_span,unplanned_operations:[],
  delivery_risks:{items:[]},candidate:{label:'测试候选'},
  generation:{algorithm:{mode_label:'测试算法',strategy_label:null},baseline:{version:1,captured_at:'2026-05-11T08:00:00'}},
  gantt_graph:{...plan.gantt_graph,scope:'full_candidate'}};
const original=h.runtime.WorkbenchControls.usePrintLayout;
try {
  h.runtime.WorkbenchControls.usePrintLayout=()=>true;
  for (const isCandidate of [false,true]) {
    const data=isCandidate?candidate:plan, task=data.tasks[1];
    const tree=h.render(h.runtime[isCandidate?'RunCandidateGantt':'PlanGantt'],{
      data,prepared:h.prepare(h.runtime[isCandidate?'RunCandidateModel':'PlanGanttModel'],data),query:'',selected:isCandidate?task:{task,before:false},onSelect:()=>{},onQuery:()=>{},asOf:'2026-05-11T12:00:00'});
    const nodes=h.walk(tree), rows=nodes.filter(node=>node.props.className===(isCandidate?'rc-lane':'plan-lane'));
    const slices=nodes.filter(node=>node.props['data-gantt-graph-lines']);
    assert.equal(rows.length,3); assert.equal(slices.length,rows.length,'Printing must not keep an independently paginating whole-chart SVG');
    rows.forEach((row,index)=>{
      const local=h.walk(row).filter(node=>node.props['data-gantt-graph-lines']);
      assert.equal(local.length,1,'Each naturally paginating row owns its connection slice');
      const slice=local[0], box=slice.props.viewBox.split(' ').map(Number);
      assert.deepEqual(box,[0,index*56,640,56]);
      assert.equal(slice.props.style.top,0);
      const edges=h.walk(slice).filter(node=>node.props['data-gantt-edge']);
      assert.equal(edges.length,index===1?2:1,'A slice only contains edges intersecting this row');
      assert(edges.every(edge=>!String(edge.props.d).includes('NaN')));
    });
  }
} finally { h.runtime.WorkbenchControls.usePrintLayout=original; }
return true;
""")
    assert result["result"] is True


def test_plan_gantt_source_preserves_unavailable_reason_and_plan_identity():
    result = run_current_js(r"""
const plan=h.processFixture();
Object.assign(plan.plan,{kind:'scenario',version:null,display_name:'机加试调'});
plan.projections.baseline.reason='采纳凭据未记录，无法读取原安排。';
plan.provenance.reason='生成来源凭据不完整，暂时无法核对。';
let tree=h.render(h.runtime.PlanGanttSource,{data:plan});
const source=tree=>h.walk(tree).find(node=>node.props['data-gantt-comparison-source']);
assert(h.text(source(tree)).includes(plan.projections.baseline.reason),'Unavailable evidence must not be described as no original plan');
assert(h.text(source(tree)).includes(plan.provenance.reason),'The generation source must retain its own unavailable reason');
assert(!h.text(source(tree)).includes('vnull'),'A plan without an official version must not invent a version label');
assert(h.text(source(tree)).includes('当前安排：试调方案 · 机加试调'));
plan.projections.baseline={state:'available',basis:'scenario_base',items:[],
  baseline_plan:{kind:'candidate',version:null,display_name:'候选 A'}};
tree=h.render(h.runtime.PlanGanttSource,{data:plan});
assert(h.text(source(tree)).includes('原安排：候选方案 · 候选 A'));
assert(!h.text(source(tree)).includes('正式计划'),'A candidate used as the scenario basis must retain its real identity');
assert(!h.text(source(tree)).includes('vnull'));
return true;
""")
    assert result["result"] is True


def test_field_detail_keeps_positive_microsecond_interval_distinct_from_point():
    result = run_current_js(r"""
const ref=h.reference(100),task={task_ref:ref,plan_ref:ref,operation_ref:ref,
  planned_start:'2026-10-12T08:00:00.000001',planned_end:'2026-10-12T08:00:00.000002',
  piece_id:null,quantity:1,batch_quantity:1,quantity_basis:'run_admission',quantity_reason:null,batch_id:'B1',operation_label:'精加工',
  execution:{operation_ref:ref,comparison_task_ref:ref,execution_state:'unreported',data_quality:'complete',target_quantity:1,
    known_completed_quantity:0,remaining_quantity:1,records_complete:true,quantity_complete:false,unknown_record_count:0,
    data_gaps:[],reports:[],legacy_facts:[],voided_reports:[],write_context:{write_token:null,capabilities:{},blocked_reasons:[]},completion_basis:null}};
const response={ok:true,schema_version:1,meta:{source:'production',time_basis:'factory_local',snapshot_ref:ref,as_of:'2026-10-12T08:00:00'},data:{task}};
const query=h.runtime.APSResourceSession.useQuery;
try {
  h.runtime.APSResourceSession.useQuery=()=>({result:h.runtime.FieldContract.query(response,'detail',ref),loading:false,error:null});
  const render=()=>h.render(h.runtime.FieldDetail,{taskRef:ref,adapter:{},scope:{},snapshot:ref,revision:0,command:{locked:false}},{FieldDetail:{1:true}});
  let nodes=h.walk(render()),bar=nodes.find(node=>node.props.className==='field-timeline-bar planned');
  assert(bar,'A positive interval must render the actual planned bar');
  assert(Number.isFinite(parseFloat(bar.props.style.left))); assert(Number.isFinite(parseFloat(bar.props.style.width)));
  assert(parseFloat(bar.props.style.width)>0,'Sub-millisecond positive duration must not collapse into zero width');
  assert(nodes.filter(node=>node.props.className==='wb-gantt-axis-band').every(node=>Number.isFinite(node.props.style.left)&&Number.isFinite(node.props.style.width)));
  task.planned_end=task.planned_start;
  Object.assign(task,{event_kind:'point',duration_seconds:0,occupies_resources:false});
  nodes=h.walk(render());
  assert(nodes.some(node=>node.props['data-field-point']==='plan'));
  assert(!nodes.some(node=>node.props.className==='field-timeline-bar planned'),'A real point keeps the existing marker contract');
} finally { h.runtime.APSResourceSession.useQuery=query; }
return true;
""")
    assert result["result"] is True
