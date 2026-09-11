/** Current shipped React/model component harness. Input: {root, program, data}. */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const root = path.resolve(input.root), loaded = [];
const document = {body: {style: {}}, documentElement: {}, addEventListener() {}, removeEventListener() {}, elementFromPoint: () => null};
const runtime = vm.createContext({console, document, URL, URLSearchParams, Map, Set, Date,
  setTimeout, clearTimeout, AbortController, FormData, innerWidth: 1280, innerHeight: 800});
runtime.window = runtime; runtime.self = runtime;
function load(relative) {
  const absolute = path.resolve(root, relative);
  assert(absolute.startsWith(root + path.sep));
  vm.runInContext(fs.readFileSync(absolute, 'utf8'), runtime, {filename: absolute});
  loaded.push(relative);
}
load('static/workbench/vendor/react-18.3.1.production.min.js');
const realReact = runtime.React;
let frame = null, overrides = {}, updates = [], frames = [];
const stubNode = () => ({scrollLeft: 0, scrollTop: 0, clientWidth: 1000, clientHeight: 440,
  focus() {}, getBoundingClientRect: () => ({left:0, top:0, width:1000, height:440}), querySelectorAll: () => []});
runtime.React = Object.assign({}, realReact, {
  useState(value) {
    assert(frame, 'Hooks need a component frame');
    const current = frame, index = current.index++;
    const values = overrides[current.name] || {};
    const initial = Object.prototype.hasOwnProperty.call(values, index) ? values[index] : typeof value === 'function' ? value() : value;
    return [initial, next => updates.push({name: current.name, index, value: typeof next === 'function' ? next(initial) : next})];
  },
  useMemo: fn => fn(), useCallback: fn => fn, useRef: value => ({current:value}),
  useEffect() {}, useLayoutEffect() {},
});
for (const name of ['resource-contract', 'PointContract', 'PointGanttModel', 'PlanProcessOrder', 'PlanContract',
  'ResourceControls', 'PointGantt', 'PlanGanttModel', 'PlanGanttCanvas', 'PlanGantt', 'PlanDetailsUI', 'PlanLayout', 'resource-api']) {
  load('static/workbench/app/' + name + '.js');
}
function expand(element) {
  if (element === null || element === undefined || typeof element === 'boolean') return null;
  if (typeof element === 'string' || typeof element === 'number') return element;
  if (Array.isArray(element)) return element.map(expand);
  assert(realReact.isValidElement(element), 'Only actual React elements may be expanded');
  if (element.type === realReact.Fragment) return expand(element.props.children);
  if (typeof element.type === 'function') {
    const previous = frame;
    frame = {name:element.type.name, index:0}; frames.push(frame.name);
    try {
      const child = element.type.prototype && element.type.prototype.isReactComponent
        ? new element.type(element.props).render() : element.type(element.props);
      return expand(child);
    } finally { frame = previous; }
  }
  assert.strictEqual(typeof element.type, 'string', 'Unexpected provider/context element in the inspected surface');
  assert(!Object.prototype.hasOwnProperty.call(element.props, 'dangerouslySetInnerHTML'), 'Raw HTML is forbidden on this surface');
  if (element.ref && typeof element.ref === 'object') element.ref.current = stubNode();
  return {type:element.type, props:element.props, children:expand(element.props.children)};
}
function walk(tree) {
  if (tree === null || tree === undefined) return [];
  if (Array.isArray(tree)) return tree.flatMap(walk);
  if (typeof tree !== 'object') return [];
  return [tree, ...walk(tree.children)];
}
function text(tree) {
  if (tree === null || tree === undefined) return '';
  if (Array.isArray(tree)) return tree.map(text).join('');
  return typeof tree === 'object' ? text(tree.children) : String(tree);
}
function render(component, props, states = {}) {
  overrides = states; updates = []; frames = [];
  return expand(realReact.createElement(component, props));
}
const reference = number => number.toString(16).padStart(48, '0');
function fixture(specs) {
  const tasks = (specs || [['A','2026-05-11T08:00:00','2026-05-11T09:00:00'], ['B','2026-05-11T10:00:00','2026-05-11T11:00:00']])
    .map(([label,start,end], index) => ({plan_ref:reference(100), task_ref:reference(index+1), operation_ref:reference(index+20),
      batch_id:'B1', sequence:(index+1)*10, process_label:label, piece_id:'piece-a', quantity:null, batch_quantity:null,
      quantity_reason:'plan_target_not_recorded', quantity_basis:null, start, end,
      machine_ref:reference(200), operator_ref:reference(201), supplier_ref:null}));
  return {plan:{plan_ref:reference(100),kind:'official',version:5}, tasks, task_count:tasks.length, tasks_complete:true,
    scope:{plan_ref:reference(100),range_start:null,range_end:null},
    plan_span:{start:tasks[0].start,end:tasks[tasks.length-1].end},
    time_scope:{range_start:tasks[0].start,range_end:tasks[tasks.length-1].end,selection:'overlap',boundary:'half_open',time_basis:'factory_local'},
    resources:[{ref:reference(200),label:'Machine 1',business_code:'M1'}, {ref:reference(201),label:'Operator 1',business_code:'O1'}],
    projections:{baseline:{state:'unavailable',items:[],reason:'Initial plan not recorded'},
      calendar:{state:'unavailable',resources:[],issues:[]}, occupancy:{state:'available',resources:[],issues:[]},
      delivery_risks:{state:'unavailable',items:[],issues:[]},
      process_order:{state:'unavailable',basis:null,items:[],issues:[{code:'process_order_unavailable',message:'Frozen process order unavailable'}]}}};
}
function gantt(data, options = {}) {
  const selections = [], queries = [];
  const states = Object.assign({}, options.states || {});
  const tree = render(runtime.PlanGantt, {data,query:options.query || '',selected:options.selected || null,
    onSelect:(task,before) => selections.push({task,before}),onQuery:value => queries.push(value),disabled:!!options.disabled}, states);
  return {tree, nodes:walk(tree), selections, queries};
}
function processFixture() {
  const data = fixture(['A1','A2','A3'].map((label,index) => [label,'2026-05-11T'+String(8+index).padStart(2,'0')+':00:00','2026-05-11T'+String(9+index).padStart(2,'0')+':00:00']));
  data.projections.process_order = {state:'available',basis:'run_admission',issues:[],items:data.tasks.map((task,index) => ({
    task_ref:task.task_ref,operation_ref:task.operation_ref,predecessor_operation_refs:index ? [data.tasks[index-1].operation_ref] : []}))};
  assert(runtime.PlanProcessOrder.validate(data.projections.process_order,data));
  return data;
}
const h = {runtime,load,loaded,render,walk,text,fixture,processFixture,gantt,reference,clone:value => JSON.parse(JSON.stringify(value)),
  updates:() => updates.slice(), equal:(left,right) => assert.strictEqual(JSON.stringify(left),JSON.stringify(right))};
Promise.resolve(new Function('h','assert','sourceData',input.program)(h,assert,input.data))
  .then(result => process.stdout.write(JSON.stringify({result:result === undefined ? true : result,loaded})))
  .catch(error => {console.error(error.stack);process.exitCode=1;});
