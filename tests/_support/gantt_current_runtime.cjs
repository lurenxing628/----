/** Current shipped React/model component harness. Input: {root, program, data}. */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const { compile, normalizeRelPath } = require('../../scripts/workbench/compile.cjs');
const { createTreeHost, walk } = require('./hook_host.cjs');
const route = require('../workbench/route_fetch.cjs');
const { memoryStorage } = require('./memory_storage.cjs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const root = path.resolve(input.root), loaded = [];
const document = {body: {style: {}}, documentElement: {setAttribute() {}}, addEventListener() {}, removeEventListener() {}, elementFromPoint: () => null,
  querySelector: () => null, querySelectorAll: () => []};
const runtime = vm.createContext({console, document, URL, URLSearchParams, Map, Set, Date,
  setTimeout, clearTimeout, queueMicrotask, AbortController, DOMException, FormData, Blob, Headers, Response, TextEncoder, TextDecoder, innerWidth: 1280, innerHeight: 800});
runtime.window = runtime; runtime.self = runtime;
// Window events reach the listeners mounted effects registered (storage, online, same-page pending-store events).
const windowListeners = new Map();
runtime.addEventListener = (type, listener) => { if (!windowListeners.has(type)) windowListeners.set(type, new Set()); windowListeners.get(type).add(listener); };
runtime.removeEventListener = (type, listener) => { if (windowListeners.has(type)) windowListeners.get(type).delete(listener); };
runtime.dispatchEvent = event => { for (const listener of Array.from(windowListeners.get(event.type) || [])) listener(event); return true; };
runtime.CustomEvent = class { constructor(type, options) { this.type = type; this.detail = options.detail; } };
runtime.matchMedia = query => ({media: String(query), matches: String(query).trim().toLowerCase() === 'screen', addEventListener() {}, removeEventListener() {}});
runtime.location = {origin: 'http://localhost', href: 'http://localhost/workbench'};
// Mounted trees run their effects (h.mount(...).settle()); layout effects observe these browser surfaces.
runtime.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
runtime.history = {state: null, replaceState() {}, pushState() {}};
runtime.requestAnimationFrame = callback => setTimeout(callback, 0); runtime.cancelAnimationFrame = clearTimeout;
function load(relative) {
  const absolute = path.resolve(root, relative);
  assert(absolute.startsWith(root + path.sep));
  vm.runInContext(fs.readFileSync(absolute, 'utf8'), runtime, {filename: absolute});
  loaded.push(relative);
}
load('static/workbench/vendor/react-18.3.1.production.min.js');
const realReact = runtime.React;
const fixtureAsOf = '2026-05-11T12:00:00';
// Stub DOM nodes for object refs: the harness has no parent chain, so ancestor lookups find nothing.
const stubNode = () => ({scrollLeft: 0, scrollTop: 0, clientWidth: 1000, clientHeight: 440,
  focus() {}, closest: () => null, getBoundingClientRect: () => ({left:0, top:0, width:1000, height:440}), querySelector: () => null, querySelectorAll: () => []});
// Mounted trees (h.mount) keep hook state per component instance; tests/_support/hook_host.cjs describes the identities.
const treeHost = createTreeHost(realReact, {refNode: stubNode}), mountTree = treeHost.mount;
runtime.React = Object.assign({}, realReact, treeHost.hooks);
// Compile and load initial workbench modules; additional modules are compiled on demand via h.module(relPath).
document.getElementById = id => id === 'workbench-boot' ? {textContent:'{}'} : {setAttribute() {}, replaceChildren() {}};
document.createElement = () => ({setAttribute() {}});
const appDir = path.join(root, 'frontend/workbench/app');
const initialSources = [
  'shared/network/transport.js',
  'shared/session/command-session.js',
  'WorkbenchFormat.js',
  'GanttGraph.js',
  'PlanGanttModel.js',
  'PlanGantt.jsx',
];
function compileIntoRuntime(relPaths) {
  const compiled = compile({
    sources: relPaths.map(rel => ({ path: rel, code: fs.readFileSync(path.join(appDir, rel), 'utf8') })),
    check_combined: false,
  });
  for (const out of compiled.outputs) {
    vm.runInContext(out.code, runtime, { filename: out.path });
    loaded.push('frontend/workbench/app/' + out.path);
  }
}
compileIntoRuntime(initialSources);
function getModule(rawPath) {
  const rel = normalizeRelPath(rawPath);
  if (!runtime.__wbRuntime || !runtime.__wbRuntime.hasModule(rel)) compileIntoRuntime([rel]);
  return runtime.__wbRuntime.getModule(rel);
}
function setStub(relPath, value) {
  runtime.__wbRuntime.setStub(relPath, value);
}
function setStubs(stubsByRel) {
  runtime.__wbRuntime.setStubs(stubsByRel);
}

function text(tree) {
  if (tree === null || tree === undefined) return '';
  if (Array.isArray(tree)) return tree.map(text).join('');
  if (typeof tree !== 'object') return String(tree);
  if (tree.props.hidden || tree.props.style && (tree.props.style.display === 'none' || tree.props.style.visibility === 'hidden')) return '';
  if (tree.type === 'details' && !tree.props.open) {
    // Browser innerText omits the closed diagnostic body; walk() still retains every original node.
    const children = Array.isArray(tree.children) ? tree.children.flat(Infinity) : [tree.children];
    return text(children.find(node => node && node.type === 'summary') || null);
  }
  return text(tree.children);
}
// One render without effects: what the component shows for these props on its first paint.
const render = (component, props) => mountTree(component, props).tree;
function styles() {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'), 'utf8'));
  return manifest.styles.map(relative => fs.readFileSync(path.join(root, 'static', relative), 'utf8')).join('\n');
}
const reference = number => number.toString(16).padStart(48, '0');
function fixture(specs) {
  const tasks = (specs || [['A','2026-05-11T08:00:00','2026-05-11T09:00:00'], ['B','2026-05-11T10:00:00','2026-05-11T11:00:00']])
    .map(([label,start,end], index) => ({plan_ref:reference(100), task_ref:reference(index+1), operation_ref:reference(index+20),
      batch_id:'B1', sequence:(index+1)*10, process_label:label, piece_id:'piece-a', quantity:null, batch_quantity:null,
      quantity_reason:'plan_target_not_recorded', quantity_basis:null, start, end,
      machine_ref:reference(200), operator_ref:reference(201), supplier_ref:null}));
  return {plan:{plan_ref:reference(100),kind:'official',version:5}, tasks, task_count:tasks.length, tasks_complete:true,
    provenance:{state:'unavailable',reason:'No generation evidence',source_kind:null,source_ref:null,source_label:null,run_ref:null,accepted_at:null,finished_at:null,adopted_at:null,algorithm:null,baseline:null},
    gantt_graph:{state:'unavailable',reason:'Frozen process order unavailable',scope:'full_plan',nodes:[],critical_task_refs:[],critical_edges:[]},
    scope:{plan_ref:reference(100),range_start:null,range_end:null},
    plan_span:{start:tasks[0].start,end:tasks[tasks.length-1].end},
    time_scope:{range_start:tasks[0].start,range_end:tasks[tasks.length-1].end,selection:'overlap',boundary:'half_open',time_basis:'factory_local'},
    resources:[{ref:reference(200),label:'Machine 1',business_code:'M1'}, {ref:reference(201),label:'Operator 1',business_code:'O1'}],
    projections:{baseline:{state:'unavailable',items:[],reason:'Initial plan not recorded'},
      calendar:{state:'unavailable',resources:[],issues:[]}, occupancy:{state:'available',resources:[],issues:[]},
      delivery_risks:{state:'unavailable',items:[],issues:[]},
      process_order:{state:'unavailable',basis:null,issues:[{code:'process_order_unavailable',message:'Frozen process order unavailable'}]}}};
}
function prepare(model, data, ...args) {
  const planGanttModel = getModule('PlanGanttModel.js');
  if (model === planGanttModel || model === planGanttModel.default) {
    const taskFacts = model.prepareTasks(data);
    return model.combinePrepared(taskFacts, model.prepareBaseline(data, taskFacts, ...args), model.prepareOccupancy(data, null, null, taskFacts.labels));
  }
  const facts = model.prepare(data, ...args);
  facts.graph = getModule('GanttGraph.js').create(data.gantt_graph);
  return facts;
}
// 计划页按需子读取（useResultSlice 的返回）夹具：默认空闲，按需覆盖 loading / error / request。
const slice = (state = {}) => Object.assign({value:null, loading:false, error:null, request() {}}, state);
function gantt(data, options = {}) {
  const selections = [], queries = [];
  // The product receives meta.as_of from its workspace response. Synthetic fixtures use a fixed local clock.
  const asOf = options.asOf === undefined ? input.data && input.data.meta && input.data.meta.as_of || fixtureAsOf : options.asOf;
  const planGanttModel = getModule('PlanGanttModel.js');
  const mounted = mountTree(getModule('PlanGantt.jsx').default, {data,prepared:prepare(planGanttModel,data),graph:getModule('GanttGraph.js').create(data.gantt_graph),asOf,query:options.query || '',selected:options.selected || null,
    baselineSlice:slice(),graphSlice:slice(),onSelect:(task,before) => selections.push({task,before}),onQuery:value => queries.push(value)});
  return {mounted, tree:mounted.tree, nodes:mounted.nodes, selections, queries};
}
function processFixture() {
  const data = fixture(['A1','A2','A3'].map((label,index) => [label,'2026-05-11T'+String(8+index).padStart(2,'0')+':00:00','2026-05-11T'+String(9+index).padStart(2,'0')+':00:00']));
  data.projections.process_order = {state:'available',basis:'run_admission',issues:[]};
  const edges = data.tasks.slice(1).map((task,index) => ({from_task_ref:data.tasks[index].task_ref,to_task_ref:task.task_ref,edge_type:'process'}));
  data.gantt_graph = {state:'available',reason:null,scope:'full_plan',
    nodes:data.tasks.map((task,index) => ({...Object.fromEntries(['task_ref','operation_ref','batch_id','piece_id','sequence','process_label','start','end'].map(key => [key,task[key]])),
      predecessor_operation_refs:index ? [data.tasks[index-1].operation_ref] : []})),
    critical_task_refs:data.tasks.map(task => task.task_ref),critical_edges:edges};
  return data;
}
// Fetch-level answers (tests/workbench/route_fetch.cjs): requests still pass through the shipped API modules and transport.
const serve = routes => (runtime.fetch = route.routeFetch(routes, {origin: runtime.location.origin}));
// 本机存储替身（tests/_support/memory_storage.cjs）：契约按页面换一份，挂到 h.runtime.localStorage / sessionStorage。
const h = {runtime,module:getModule,getModule,setStub,setStubs,load,loaded,render,mount:mountTree,serve,route,memoryStorage,walk,text,styles,fixture,processFixture,prepare,gantt,slice,reference,
  clone:value => JSON.parse(JSON.stringify(value)), equal:(left,right) => assert.strictEqual(JSON.stringify(left),JSON.stringify(right))};
// Programs may await mounted trees settling.
const AsyncFunction = (async () => {}).constructor;
new AsyncFunction('h','assert','sourceData',input.program)(h,assert,input.data)
  .then(result => process.stdout.write(JSON.stringify({result:result === undefined ? true : result,loaded})))
  .catch(error => {console.error(error.stack);process.exitCode=1;});
