'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const babel = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
const source = name => fs.readFileSync(path.join(app, name), 'utf8');
function load(ctx, name, code = source(name)) {
  const output = compile({ babel_path: babel, sources: [{ path: name, code }] }).outputs[0].code;
  vm.runInContext(output, ctx, { filename: name });
}
function hooks() {
  let cursor = 0; const slots = [], effects = [];
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  const useMemo = (fn, deps) => { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() }; return slots[i].value; };
  const useEffect = (fn, deps) => { const i = cursor++, old = slots[i]; if (!old || !same(old.deps, deps)) { slots[i] = { deps, cleanup: old && old.cleanup }; effects.push(() => { if (slots[i].cleanup) slots[i].cleanup(); slots[i].cleanup = fn(); }); } };
  return { React: { createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), Fragment: 'fragment',
    useRef(value) { const i = cursor++; if (!slots[i]) slots[i] = { current: value }; return slots[i]; },
    useState(value) { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof value === 'function' ? value() : value }; return [slots[i].value, v => { slots[i].value = typeof v === 'function' ? v(slots[i].value) : v; }]; },
    useReducer(reducer, value) { const [state, setState] = this.useState(value); return [state, action => setState(current => reducer(current, action))]; },
    useId() { return 'runtime-contract-' + cursor++; },
    useMemo, useCallback: (fn, deps) => useMemo(() => fn, deps), useEffect, useLayoutEffect: useEffect },
    render(fn) { cursor = 0; return fn(); }, flush() { while (effects.length) effects.shift()(); },
    unmount() { effects.length = 0; slots.forEach(slot => { if (slot.cleanup) { const cleanup = slot.cleanup; slot.cleanup = null; cleanup(); } }); }, slots };
}
const turns = async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); };
async function main() {
  // Ordinary GET hooks keep cancellation and identity boundaries in the existing owner.
  const queryHooks = hooks(), queryContext = vm.createContext({ window: { APSResourceContract: {} }, React: queryHooks.React, AbortController, DOMException });
  load(queryContext, 'resource-session.js'); load(queryContext, 'TrialSession.js');
  let first, second, oldSignal;
  const read = (id, load, enabled = true) => queryHooks.render(() => queryContext.window.TrialSession.useRead(load, [id], enabled));
  read('old', signal => { oldSignal = signal; return new Promise(resolve => { first = resolve; }); }); queryHooks.flush(); await turns();
  assert.equal(read('new', () => new Promise(resolve => { second = resolve; })).result, null); queryHooks.flush(); await turns();
  assert.equal(oldSignal.aborted, true); first('stale'); await turns();
  assert.equal(read('new', () => {}).result, null); second('current'); await turns(); assert.equal(read('new', () => {}).result, 'current');
  let reopenLoads = 0;
  assert.equal(read('new', () => { reopenLoads++; }, false).result, 'current'); queryHooks.flush(); await turns();
  assert.equal(read('new', () => { reopenLoads++; }, true).result, 'current'); queryHooks.flush(); await turns();
  assert.equal(reopenLoads, 0, 'Showing the same successful data identity uses the retained result');
  let waitingSignal, queuedLoads = 0;
  const outcomes = [], observe = promise => promise.then(() => outcomes.push('resolved'), error => outcomes.push(error.name));
  const inFlight = observe(read('new', () => {}).reloadAndWait(signal => { waitingSignal = signal; return new Promise(() => {}); }));
  read('new', () => {}); queryHooks.flush(); await turns();
  const replaced = observe(read('new', () => {}).reloadAndWait(() => { queuedLoads++; }));
  const queued = observe(read('new', () => {}).reloadAndWait(() => { queuedLoads++; }));
  // No next render/effect commit: the last request is still queued at unmount.
  queryHooks.unmount(); await turns();
  assert.deepEqual(outcomes, ['AbortError', 'AbortError', 'AbortError']);
  await Promise.all([inFlight, replaced, queued]);
  assert.equal(waitingSignal.aborted, true); assert.equal(queuedLoads, 0); assert.equal(queryHooks.slots[2].current, null);

  // Errors can retry after reopening; a hidden new snapshot waits until shown.
  const retryHooks = hooks(), retryContext = vm.createContext({ window: { APSResourceContract: {} }, React: retryHooks.React, AbortController, DOMException });
  load(retryContext, 'resource-session.js');
  let retryLoads = 0;
  const retryRead = (id, enabled = true) => retryHooks.render(() => retryContext.window.APSResourceSession.useQuery(() => {
    retryLoads++; return retryLoads === 1 ? Promise.reject(new Error('read failed')) : Promise.resolve('snapshot-' + id);
  }, [id], enabled));
  retryRead('one'); retryHooks.flush(); await turns(); assert.equal(retryRead('one').error.message, 'read failed');
  retryRead('one', false); retryHooks.flush(); retryRead('one'); retryHooks.flush(); await turns();
  assert.equal(retryRead('one').result, 'snapshot-one'); assert.equal(retryLoads, 2);
  assert.equal(retryRead('two', false).result, null); retryHooks.flush(); await turns(); assert.equal(retryLoads, 2);
  retryRead('two'); retryHooks.flush(); await turns(); assert.equal(retryRead('two').result, 'snapshot-two'); assert.equal(retryLoads, 3);
  retryHooks.unmount();

  // Combined workspaces can issue a new parent object with the same snapshot token.
  const ownerHooks = hooks(), ownerContext = vm.createContext({ window: { APSResourceContract: {} }, React: ownerHooks.React, AbortController, DOMException });
  load(ownerContext, 'resource-session.js'); let owner = { meta: { snapshot_ref: 'same-token' } }, ownerLoads = 0;
  const ownerRead = (enabled = true) => ownerHooks.render(() => ownerContext.window.APSResourceSession.useQuery(() => { ownerLoads++; return Promise.resolve(owner); }, [owner], enabled));
  ownerRead(); ownerHooks.flush(); await turns(); assert.strictEqual(ownerRead().result, owner);
  ownerRead(false); ownerHooks.flush(); ownerRead(); ownerHooks.flush(); await turns(); assert.equal(ownerLoads, 1);
  owner = { meta: { snapshot_ref: 'same-token' } }; assert.equal(ownerRead(false).result, null); ownerHooks.flush(); await turns(); assert.equal(ownerLoads, 1);
  ownerRead(); ownerHooks.flush(); await turns(); assert.strictEqual(ownerRead().result, owner); assert.equal(ownerLoads, 2);
  ownerHooks.unmount();

  // R18 retains the private baseline result while its display toggle masks it.
  const baselineHooks = hooks(), baselineWindow = { APSResourceContract: {}, RunCandidateModel: {}, RunBaselineModel: {}, RunCandidateControls: { Button: 'button' } };
  let baselineLoads = 0; const frozenBaseline = { snapshot: 'baseline-one' };
  baselineWindow.RunBaselineAPI = { create: () => ({ read: async () => { baselineLoads++; return frozenBaseline; } }) };
  const baselineContext = vm.createContext({ window: baselineWindow, React: baselineHooks.React, AbortController, DOMException });
  load(baselineContext, 'resource-session.js'); load(baselineContext, 'RunBaselineControls.jsx'); let baselineData = {};
  const baselineRead = () => baselineHooks.render(() => baselineWindow.RunBaselineControls.useBaseline(baselineData, true));
  baselineRead().toggle(true); baselineRead(); baselineHooks.flush(); await turns(); assert.strictEqual(baselineRead().result, frozenBaseline);
  baselineRead().toggle(false); assert.equal(baselineRead().result, null); baselineHooks.flush();
  baselineRead().toggle(true); baselineRead(); baselineHooks.flush(); await turns(); assert.strictEqual(baselineRead().result, frozenBaseline); assert.equal(baselineLoads, 1);
  baselineRead().retry(); baselineRead(); baselineHooks.flush(); await turns(); assert.equal(baselineLoads, 2);
  baselineData = {}; assert.equal(baselineRead().result, null); baselineHooks.flush(); await turns(); assert.equal(baselineLoads, 3); baselineHooks.unmount();

  // Scrolling no longer registers controls or recomputes native step values/labels.
  const numberHooks = hooks(), listeners = {}, frames = new Map(); let frameId = 0, scans = 0, values = 0, positions = 0, observer;
  const document = { body: {}, querySelectorAll() { scans++; return []; }, addEventListener(name, fn) { listeners[name] = fn; }, removeEventListener() {} };
  const numberContext = vm.createContext({ window: { addEventListener(name, fn) { listeners['window:' + name] = fn; }, removeEventListener() {} }, document,
    React: numberHooks.React, MutationObserver: class { constructor(fn) { observer = fn; } observe() {} disconnect() {} },
    requestAnimationFrame(fn) { const id = ++frameId; frames.set(id, fn); return id; }, cancelAnimationFrame(id) { frames.delete(id); } });
  load(numberContext, 'WorkbenchNumberControls.jsx'); numberHooks.render(() => numberContext.window.WorkbenchNumberControls()); numberHooks.flush();
  const refreshers = numberHooks.slots[1].current, inputs = Array.from({ length: 100 }, () => ({}));
  inputs.forEach(input => refreshers.set(input, { refresh() { values++; }, position() { positions++; }, scrollDependent: false }));
  const flushFrames = () => { while (frames.size) { const [id, fn] = frames.entries().next().value; frames.delete(id); fn(); } };
  listeners.scroll({ target: { contains: () => false } }); flushFrames(); assert.equal(scans, 1); assert.equal(values, 0); assert.equal(positions, 0);
  refreshers.get(inputs[0]).scrollDependent = true; listeners.scroll({ target: document }); flushFrames(); assert.equal(positions, 1); assert.equal(values, 0);
  listeners.input({ target: inputs[7] }); assert.equal(values, 1);
  observer([{ type: 'attributes', target: { nodeType: 1, matches: () => false, closest: () => null } }]); flushFrames(); assert.equal(scans, 2); assert.equal(values, 101);

  // Run the actual App publication closure with a fake clock/history, including
  // navigation before the trailing write and immediate Back/Forward restoration.
  const appHooks = hooks(), timers = new Map(), animation = new Map(), events = new Map(), documentEvents = new Map(); let timerId = 0, animationId = 0, writes = 0, index = 0;
  const location = { href: 'http://localhost/workbench?view=reports', origin: 'http://localhost', pathname: '/workbench' },
    savedScroll = { windowTop: 80, windowLeft: 0, mainTop: 0, mainLeft: 0, containers: {} },
    entries = [{ state: { workbench: { view: 'reports', key: 0, context: { selected: 'old' }, scroll: savedScroll } }, href: location.href }];
  const setLocation = href => { const url = new URL(href, location.origin); location.href = url.href; location.pathname = url.pathname; };
  const window = { scrollX: 0, scrollY: 0, scrollTo(x, y) { this.scrollX = x; this.scrollY = y; }, dispatchEvent(event) { (events.get(event.type) || []).forEach(fn => fn(event)); },
    addEventListener(name, fn) { if (!events.has(name)) events.set(name, []); events.get(name).push(fn); }, removeEventListener() {},
    APSBatchAPI: { create: () => ({}) }, APSWorkbenchTheme: { get: () => ({}), subscribe: () => () => {} }, WorkbenchDensity: { get: () => ({}), subscribe: () => () => {} },
    WorkbenchGuards: { hasDirty: () => false, confirmLeave: async () => true }, WorkbenchPageContext: { Provider: 'remember' }, WorkbenchCaption: { Provider: 'caption' } };
  const history = { scrollRestoration: 'auto', get state() { return entries[index].state; },
    replaceState(state, _, href) { writes++; setLocation(href); entries[index] = { state, href: location.href }; },
    pushState(state, _, href) { entries.splice(++index); setLocation(href); entries.push({ state, href: location.href }); },
    go(delta) { index += delta; setLocation(entries[index].href); window.dispatchEvent({ type: 'popstate' }); } };
  const appDocument = { querySelector: () => null, addEventListener(name, fn) { documentEvents.set(name, fn); }, removeEventListener() {} };
  const appContext = vm.createContext({ window, document: appDocument, history, location, React: appHooks.React, Event,
    boot: { view: 'reports', titles: { reports: '报表', field: '现场', trial: '试调', gantt: '计划' }, entry_url: '/workbench', trial_url: '/trial' }, root: { setAttribute() {} },
    WorkbenchShell: 'shell', SystemLive: 'system', URL, performance: { now: () => 0 },
    setTimeout(fn) { const id = ++timerId; timers.set(id, fn); return id; }, clearTimeout(id) { timers.delete(id); },
    requestAnimationFrame(fn) { const id = ++animationId; animation.set(id, fn); return id; }, cancelAnimationFrame(id) { animation.delete(id); } });
  load(appContext, 'WorkbenchNavigation.js');
  const helpBoot = { entry_url: '/workbench', trial_url: '/trial', help_url: '/help', titles: { analysis: '分析', reports: '报表' } };
  const historyHelp = { view: 'analysis', context: { source: 'run_history', history_topic: 'decision_history' } };
  const decisionHelp = new URL(window.WorkbenchNavigation.helpUrl(helpBoot, historyHelp), location.origin);
  assert.equal(decisionHelp.searchParams.get('page'), 'analysis');
  assert.equal(decisionHelp.searchParams.get('src'), '/workbench?view=analysis');
  assert.equal(decodeURIComponent(decisionHelp.hash), '#排产记录');
  assert.equal(new URL(window.WorkbenchNavigation.helpUrl(helpBoot,
    { ...historyHelp, context: { source: 'run_history', history_topic: 'run_catalog' } }), location.origin).searchParams.get('page'), 'run');
  assert.equal(new URL(window.WorkbenchNavigation.helpUrl(helpBoot, { view: 'reports', context: {} }), location.origin).searchParams.get('page'), 'reports');
  const mainSource = source('main.jsx'), start = mainSource.indexOf('  function App() {'), end = mainSource.indexOf('  ReactDOM.createRoot(root).render(<App />);');
  load(appContext, 'App-test.jsx', mainSource.slice(start, end) + '\nwindow.TestApp = App;');
  const find = (node, type, matches = () => true) => { if (!node || !node.props) return null; if (node.type === type && matches(node.props)) return node.props; for (const child of node.props.children.flat(Infinity)) { const result = find(child, type, matches); if (result) return result; } return null; };
  const finishRestore = () => { while (animation.size) { const [id, fn] = animation.entries().next().value; animation.delete(id); fn(); } };
  const renderApp = (completeRestore = true) => { const node = appHooks.render(() => window.TestApp()); appHooks.flush(); if (completeRestore) finishRestore(); return node; };
  let appNode = renderApp(false), publish = find(appNode, 'remember').remember;
  publish({ selected: 'restoring-latest' }); window.dispatchEvent({ type: 'pagehide' });
  assert.equal(history.state.workbench.context.selected, 'restoring-latest'); assert.deepEqual(history.state.workbench.scroll, savedScroll);
  finishRestore(); timers.values().next().value(); timers.clear(); writes = 0;
  for (let n = 0; n < 60; n++) publish({ selected: n, scroll: { tableTop: n } });
  assert.equal(writes, 0); assert.equal(timers.size, 1);
  timers.values().next().value(); timers.clear(); assert.equal(writes, 1); assert.equal(history.state.workbench.context.selected, 59);
  publish({ selected: 60 }); await find(appNode, 'shell').navigate('field', {});
  assert.equal(history.state.workbenchPages.reports.context.selected, 60); assert.equal(timers.size, 0);
  appNode = renderApp(); find(appNode, 'remember').remember({ selected: 'field-latest' }); history.go(-1);
  assert.equal(history.state.workbench.context.selected, 60); history.go(1); assert.equal(history.state.workbench.context.selected, 'field-latest');
  renderApp(); window.dispatchEvent({ type: 'pagehide' }); assert.equal(history.state.workbench.context.selected, 'field-latest');

  window.TrialContract = { ref: value => /^[a-f0-9]{48}$/.test(value), check: (value, message) => assert(value, message) };
  load(appContext, 'TrialAdoptionHistoryState.js');
  appNode = renderApp(); const scenario = '1'.repeat(48), planA = 'a'.repeat(48), planB = 'b'.repeat(48);
  await find(appNode, 'remember').navigate('trial', { scenario_ref: scenario }); appNode = renderApp();
  await window.TrialAdoptionHistoryState.openPlan(scenario, planA, find(appNode, 'remember').navigate); appNode = renderApp();
  find(appNode, 'remember').remember({ plan_ref: planA, query: 'old-forward-entry' }); history.go(-1); appNode = renderApp();
  await window.TrialAdoptionHistoryState.openPlan(scenario, planB, find(appNode, 'remember').navigate); renderApp();
  assert.equal(history.state.workbench.context.plan_ref, planB); assert.equal(history.state.workbench.context.query, undefined);

  // The current issue batch owns the comparison scope across analysis changes and page restoration.
  let dashboardHooks = hooks(); const dashboardRequests = [], dashboardStates = [];
  const dashboardRun = '1'.repeat(48), dashboardCandidate = '2'.repeat(48), batchOne = '3'.repeat(48), batchTwo = '4'.repeat(48);
  const dashboardChoice = { run_ref: dashboardRun, candidate_ref: dashboardCandidate,
    range_start: '2026-10-13T00:00:00', range_end: '2026-10-31T00:00:00' };
  const dashboardApi = {
    catalog: async () => ({ data: { candidates: [{ candidate_ref: dashboardCandidate, label: '原算法', status: 'completed', task_count: 2 }],
      candidate_count: 1, page: { has_more: false } }, meta: { snapshot_ref: 'dashboard-directory' } }),
    workspace: (candidateRef, scope, signal) => new Promise(resolve => dashboardRequests.push({ candidateRef, scope, signal, resolve }))
  };
  const dashboardWindow = { RunCandidateAPI: { create: () => dashboardApi, time: value => typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(value) },
    RunBaselineAPI: { create: () => ({ read: async data => ({ data: { batch_ref: data.batch_ref } }) }) },
    DashboardCandidatePanels: { Metrics: 'dashboard-metrics', Batches: 'dashboard-batches', Summary: 'dashboard-summary' },
    ResourceControls: { Button: 'button', ErrorBox: 'error', Issues: 'issues' }, WorkbenchReference: 'reference',
    WorkbenchFormat: { dateTime: String, compactRange: (start, end) => start + ' / ' + end, compactDateTime: String },
    WorkbenchTerms: { candidate_statuses: { completed: '计算完成' }, hold_window: () => '未设置', material_strategy: () => '全部齐套' } };
  const dashboardContext = vm.createContext({ window: dashboardWindow, React: dashboardHooks.React, AbortController });
  load(dashboardContext, 'DashboardContract.js'); load(dashboardContext, 'DashboardAnalysisAPI.js'); load(dashboardContext, 'DashboardCandidateComparisonAPI.js');
  dashboardWindow.DashboardCandidateComparisonAPI.create = () => ({ read: async (data, baseline) => {
    assert.equal(baseline.batch_ref, data.batch_ref);
    const batchRefs = data.batch_ref ? [data.batch_ref] : [batchOne, batchTwo];
    return { data: { candidate: data.candidate, generation: data.generation, baseline: { available: false }, batch_refs: batchRefs,
      batches: batchRefs.map(batch_ref => ({ batch_ref, batch_id: batch_ref === batchOne ? 'DC-01' : 'DC-02' })) } };
  } });
  load(dashboardContext, 'DashboardCandidates.jsx');
  let dashboardProps = { catalog: { runs: [{ run_ref: dashboardRun, candidate_count: 1, accepted_at: dashboardChoice.range_start }] },
    initialContext: { run_ref: dashboardRun, candidate_ref: dashboardCandidate, batch_ref: batchTwo }, issueBatchRef: batchOne, selectedBatch: batchOne,
    onSelectBatch() {}, onState: state => dashboardStates.push(JSON.parse(JSON.stringify(state))) };
  const renderDashboard = () => { const tree = dashboardHooks.render(() => dashboardWindow.DashboardCandidates(dashboardProps)); dashboardHooks.flush(); return tree; };
  const completeDashboard = async request => {
    request.resolve({ data: { candidate: { candidate_ref: request.candidateRef, run_ref: dashboardRun, label: '原算法' }, batch_ref: request.scope.batch_ref || null,
      generation: { run_ref: dashboardRun, input: { start_date: '2026-10-13', end_date: '2026-10-30', ready_check: true, missing_resource_policy: 'exclude', hold_window: null } } } }); await turns(); await turns();
    return renderDashboard();
  };
  const assertDashboardBatch = (tree, request, batchRef) => {
    assert.equal(request.scope.batch_ref, batchRef);
    assert.equal(find(tree, 'reference', props => props.entries && '原问题批次编号' in props.entries).entries['原问题批次编号'], batchRef);
    assert.deepEqual(Array.from(find(tree, 'dashboard-batches').data.batches, row => row.batch_ref), [batchRef]);
    assert.deepEqual(dashboardStates.at(-1).context, { ...dashboardChoice, batch_ref: batchRef });
  };
  let dashboardTree = renderDashboard(); dashboardTree = await completeDashboard(dashboardRequests[0]);
  assert.deepEqual({ ...dashboardRequests[0].scope }, { batch_ref: batchOne }, 'Admission-range discovery already follows the current issue batch');
  const initialDashboardRequest = dashboardRequests.at(-1); dashboardTree = await completeDashboard(initialDashboardRequest);
  assertDashboardBatch(dashboardTree, initialDashboardRequest, batchOne); const savedDashboard = dashboardStates.at(-1);
  find(dashboardTree, 'button', props => props['aria-label'] === '刷新候选方案比较').onClick(); renderDashboard();
  const oldDashboardRequest = dashboardRequests.at(-1);
  dashboardProps = { ...dashboardProps, issueBatchRef: batchTwo, selectedBatch: batchTwo }; dashboardTree = renderDashboard();
  assert.equal(find(dashboardTree, 'dashboard-batches'), null, 'Changing the issue hides the previous batch result immediately');
  assert.equal(oldDashboardRequest.signal.aborted, true);
  const currentDashboardRequest = dashboardRequests.at(-1); dashboardTree = await completeDashboard(currentDashboardRequest);
  assertDashboardBatch(dashboardTree, currentDashboardRequest, batchTwo);
  assert.equal(dashboardStates.at(-1).caption.name, '原算法');
  dashboardTree = await completeDashboard(oldDashboardRequest); assertDashboardBatch(dashboardTree, currentDashboardRequest, batchTwo);
  dashboardHooks.unmount(); dashboardHooks = hooks(); dashboardContext.React = dashboardHooks.React;
  dashboardProps = { ...dashboardProps, initialContext: savedDashboard.context }; renderDashboard();
  const restoredDashboardRequest = dashboardRequests.at(-1); dashboardTree = await completeDashboard(restoredDashboardRequest);
  assertDashboardBatch(dashboardTree, restoredDashboardRequest, batchTwo);
  dashboardProps = { ...dashboardProps, issueBatchRef: null, selectedBatch: batchOne }; renderDashboard();
  const wholeDashboardRequest = dashboardRequests.at(-1); dashboardTree = await completeDashboard(wholeDashboardRequest);
  assert.equal(Object.prototype.hasOwnProperty.call(wholeDashboardRequest.scope, 'batch_ref'), false);
  assert.equal(find(dashboardTree, 'reference', props => props.entries && '原问题批次编号' in props.entries), null);
  assert.deepEqual(Array.from(find(dashboardTree, 'dashboard-batches').data.batches, row => row.batch_id), ['DC-01', 'DC-02']);
  assert.equal(find(dashboardTree, 'dashboard-batches').selected, batchOne, 'General catalog highlighting keeps its parent selection without narrowing the request');
  assert.deepEqual(dashboardStates.at(-1).context, dashboardChoice); dashboardHooks.unmount();

  // A narrower plan scope starts on its first analysis page; stale remembered pages still show available rows.
  const planHooks = hooks(), timeScope = { range_start: '2026-10-12T08:00:00', range_end: '2026-10-14T18:00:00' };
  const planData = { plan: { plan_ref: planA, display_name: '正式计划', kind: 'official', version: 1, is_current_official: true },
    scope: { range_start: null }, time_scope: timeScope, plan_span: { start: timeScope.range_start, end: timeScope.range_end, end_inclusive: true },
    task_count: 0, tasks: [], provenance: {}, projections: { delivery_risks: { state: 'available', issues: [], items: [] } } };
  const planRead = { result: { data: planData, warnings: [], meta: { snapshot_ref: 'plan-snapshot' } }, loading: false, error: null, reload() {} };
  const planWindow = { APSResourceContract: { failure: text => new Error(text) }, APSPlanContract: { workspaceScope: (_, value) => value },
    APSResourceSession: { useQuery: () => planRead }, ResourceControls: { Button: 'button', ErrorBox: 'error', Issues: 'issues' },
    PlanCatalogUI: { Catalog: 'catalog' },
    WorkbenchFormat: { compactRange: () => '时间范围', dateTime: String }, WorkbenchDatePickerModel: { factoryTime: value => value },
    WorkbenchTerms: { current_official: '当前正式计划', plan_version: String },
    PlanDetailsUI: { TaskDetail: 'task-detail', ProjectionTables: 'projection-tables', Conflicts: 'conflicts' },
    WorkbenchPageContext: { useSnapshot() {} }, WorkbenchCaption: { useCaption() {} }, WorkbenchControls: { Pager: 'pager', EmptyState: 'empty' } };
  const planContext = vm.createContext({ window: planWindow, React: planHooks.React });
  load(planContext, 'PlanGanttModel.js'); Object.assign(planWindow.PlanGanttModel, { names: () => new Map(), timeLabel: String, number: String });
  load(planContext, 'PlanWorkspace.jsx', source('PlanWorkspace.jsx').replace('window.PlanWorkspace = PlanWorkspace;', 'window.PlanWorkspaceSession = WorkspaceSession;'));
  const renderPlan = () => planHooks.render(() => planWindow.PlanWorkspaceSession({ adapter: {}, planRef: planA, initialContext: { projection_page: 3 } }));
  let planTree = renderPlan(); assert.equal(find(planTree, 'projection-tables').page, 3);
  find(find(planTree, 'catalog').actions, 'button').onClick(); planTree = renderPlan();
  find(planTree, 'form').onSubmit({ preventDefault() {} }); planTree = renderPlan();
  assert.equal(find(planTree, 'projection-tables').page, 3, 'Applying the same range preserves the current analysis page');
  find(find(planTree, 'catalog').actions, 'button').onClick(); planTree = renderPlan();
  find(planTree, 'input', props => props['aria-label'] === '读取开始时间').onChange({ target: { value: '2026-10-13T08:00:00' } });
  planTree = renderPlan(); find(planTree, 'form').onSubmit({ preventDefault() {} }); planTree = renderPlan();
  assert.equal(find(planTree, 'projection-tables').page, 0);
  planData.projections.delivery_risks.items = [{ batch_ref: 'batch-1', batch_id: 'B-01', part_no: 'P-01', part_label: '轴',
    due_date: null, completion_state: 'complete', risk: 'on_time', unscheduled_operation_count: 0, ordinary_unscheduled_operation_count: 0, deferred_operation_count: 0, issues: [] }];
  Object.assign(planWindow.WorkbenchTerms, { delivery_risks: { on_time: '准时' }, delivery_completion_states: { complete: '已排齐' }, due_date: () => '未指定' });
  load(planContext, 'PlanDetailsUI.jsx');
  const projection = planHooks.render(() => planWindow.PlanDetailsUI.ProjectionTables({ data: planData, page: 3, onPage() {}, onTab() {}, onBatch() {} }));
  assert.equal(find(projection, 'pager').page, 1); assert(find(projection, 'button', props => props.children.includes('B-01')));
  assert.equal(find(projection, 'empty'), null);

  // Result/constraint/preparation task selection uses the same guarded detail-opening action.
  const trialHooks = hooks(), trialData = { draft_ref: 'draft', base: {}, base_identity: {}, name: '试调', status: 'editing',
    baseline: { version: null }, time_scope: { start: timeScope.range_start, end: timeScope.range_end }, comparison: {}, tasks: [], validation: { constraints_status: 'valid' } };
  let mayLeave = true, guardCalls = 0;
  const trialWindow = { addEventListener() {}, removeEventListener() {}, TrialAPI: {}, TrialContract: {},
    TrialControls: { Button: 'button', ErrorBox: 'error', statusLabel: String, sourceLabel: () => '原安排' },
    TrialSession: { useRead: () => ({ result: { data: trialData, meta: {} }, busy: false, error: null }), useCommands: () => ({ blocked: false }) },
    WorkbenchGuards: { useDirtyGuard() {}, confirmLeave: async () => { guardCalls++; return mayLeave; } },
    WorkbenchCaption: { useCaption() {} }, WorkbenchFormat: { dateTime: String, compactRange: () => '时间范围' }, WorkbenchTerms: { delivery_coverage: () => '' },
    TrialCatalog: { Directory: 'trial-directory' }, TrialGantt: 'trial-gantt', TrialDetails: 'trial-details', TrialResults: { Summary: 'trial-summary', Results: 'trial-results' } };
  const trialContext = vm.createContext({ window: trialWindow, React: trialHooks.React, document: { documentElement: {} } });
  load(trialContext, 'TrialWorkspace.jsx', source('TrialWorkspace.jsx').replace('window.WorkbenchTrialWorkspace = WorkbenchTrialWorkspace;', 'window.TrialWorkspaceSession = Session;'));
  const renderTrial = () => trialHooks.render(() => trialWindow.TrialWorkspaceSession({ initialTarget: { draft_ref: 'draft' } }));
  let trialTree = renderTrial(); assert.equal(find(trialTree, 'trial-details'), null);
  await find(trialTree, 'trial-gantt').onSelect('task-one'); trialTree = renderTrial();
  assert.equal(find(trialTree, 'trial-details'), null, 'Ordinary Gantt selection keeps details collapsed');
  await find(trialTree, 'trial-results').onSelect('task-one'); trialTree = renderTrial();
  assert.equal(find(trialTree, 'trial-details').selected, 'task-one');
  mayLeave = false; await find(trialTree, 'trial-results').onSelect('task-two'); trialTree = renderTrial();
  assert.equal(find(trialTree, 'trial-details').selected, 'task-one');
  mayLeave = true; await find(trialTree, 'trial-details').onCollapse(); trialTree = renderTrial(); assert.equal(find(trialTree, 'trial-details'), null);
  const beforeReopen = guardCalls; await find(trialTree, 'trial-results').onSelect('task-one'); trialTree = renderTrial();
  assert.equal(find(trialTree, 'trial-details').selected, 'task-one'); assert.equal(guardCalls, beforeReopen);

  // Related-resource editing keeps the current list on its displayed clamped page.
  const resourceHooks = hooks(), resourceRequests = [], resourceDetails = [], resourceSnapshots = [];
  const machineRef = '1'.repeat(48), operatorRef = '2'.repeat(48);
  const resourceForms = () => null; resourceForms.Detail = 'resource-detail'; resourceForms.Feedback = 'resource-feedback';
  const resourceTables = () => null; resourceTables.Pager = 'resource-pager';
  const resourceContract = { nodes: { machine: { kind: 'machine', label: '设备', chain: 'internal' }, operator: { kind: 'operator', label: '人员', chain: 'internal' } },
    statuses: { machine: [], operator: [] }, object: value => value !== null && typeof value === 'object' && !Array.isArray(value),
    own: (value, key) => Object.prototype.hasOwnProperty.call(value, key), query: value => value, failure: message => new Error(message),
    message: error => error.message, blocked: () => '', receipt: value => value && value.ok ? 'terminal' : 'pending',
    requestKey: () => 'related-resource-request', resultRef: (value, fallback) => value.data.entity_ref || fallback };
  const resourceAdapter = {
    async list(kind, scope) {
      resourceRequests.push({ kind, ...scope });
      return { data: { entities: [], page: { number: scope.page, size: scope.size, total: kind === 'machine' ? 21 : 1 } },
        meta: { source: 'production', snapshot_ref: scope.snapshot_ref || 'snapshot-' + kind }, warnings: [] };
    },
    async detail(kind, ref) { resourceDetails.push({ kind, ref }); return { data: { ref, fields: {}, write_context: { write_token: 'resource-token' } }, meta: { source: 'production' } }; },
    async command(kind, action, ref) { assert.equal(kind, 'operator'); assert.equal(action, 'update'); assert.equal(ref, operatorRef); return { ok: true, receipt_ref: 'related-save', data: { entity_ref: ref } }; }
  };
  const resourceWindow = { APSResourceContract: resourceContract, ResourceControls: { Button: 'button', Icon: 'icon', ErrorBox: 'error', Issues: 'issues', Modal: 'modal' },
    ResourceForms: resourceForms, ResourceTables: resourceTables, ResourceRail: 'resource-rail', ResourceMetrics: 'resource-metrics',
    ResourceTableFilterModel: { restore: filters => ({ filters, notice: '' }) }, WorkbenchPageContext: { useSnapshot: (...args) => resourceSnapshots.push(args) },
    addEventListener() {}, removeEventListener() {} };
  const resourceContext = vm.createContext({ window: resourceWindow, React: resourceHooks.React, AbortController, DOMException });
  load(resourceContext, 'resource-session.js'); resourceWindow.APSResourceSession.useCounts = () => ({ summary: { reload() {} } });
  load(resourceContext, 'ResourceWorkspace.jsx');
  const resourceContextInput = { source: 'production', kind: 'machine', read_view: { scope: { query: '', status: '', page: 3, size: 20, sort: 'business_code', direction: 'asc' },
    selected_refs: [], sort_active: false, detail: null } };
  const resourceRender = () => resourceHooks.render(() => resourceWindow.ResourceWorkspace({ adapter: resourceAdapter, initialContext: resourceContextInput }));
  const settleResource = async () => { let tree; for (let n = 0; n < 4; n++) { tree = resourceRender(); resourceHooks.flush(); await turns(); } return tree; };
  let resourceTree = await settleResource();
  assert.deepEqual(resourceRequests.map(value => [value.kind, value.page, value.snapshot_ref || null]), [['machine', 3, null], ['machine', 2, 'snapshot-machine']]);
  assert.equal(resourceSnapshots.at(-1)[0].read_view.scope.page, 2);
  find(resourceTree, resourceTables).onOpen(machineRef); resourceTree = await settleResource();
  find(resourceTree, 'resource-detail').onRelated('operator', operatorRef); resourceTree = await settleResource();
  assert.equal(find(resourceTree, 'resource-detail').kind, 'operator');
  find(resourceTree, 'resource-detail').onEdit(); resourceTree = resourceRender();
  const resourceEditor = find(resourceTree, resourceForms); assert.equal(resourceEditor.kind, 'operator');
  await resourceEditor.command.submit('operator', 'update', operatorRef, { write_token: 'resource-token' }, { label: '保存后的人员' });
  resourceTree = await settleResource();
  assert.deepEqual(resourceRequests.slice(2).map(value => [value.kind, value.page, value.snapshot_ref || null]), [['operator', 1, null], ['machine', 2, null]],
    'Saving a related operator reads its own category and refreshes the current machine list at the displayed page');
  assert.deepEqual(resourceDetails, [{ kind: 'machine', ref: machineRef }, { kind: 'operator', ref: operatorRef }, { kind: 'operator', ref: operatorRef }]);
  assert.equal(find(resourceTree, resourceForms).refreshState.done, true);
  assert.equal(find(resourceTree, resourceForms).refreshState.detail.data.ref, operatorRef);
  assert.equal(resourceSnapshots.at(-1)[0].read_view.scope.page, 2); resourceHooks.unmount();

  const modelContext = vm.createContext({ window: { WorkbenchFormat: {}, FieldContract: { quantityReasons: {}, states: {} } } });
  load(modelContext, 'PlanGanttModel.js'); load(modelContext, 'ActualGanttModel.js'); let reads = 0;
  const data = { availability: { state: 'available' }, execution_summary: { scope: 'full_response_cohort', complete: 334, pending: 333, reported: 333, average_finish_deviation_minutes: 30, known_finish_count: 334 }, items: Array.from({ length: 1000 }, (_, n) => ({ task: { end: '2026-09-09T08:00:00' },
    execution: { get execution_state() { reads++; return ['complete', 'unreported', 'partial'][n % 3]; }, confirmed_finish: '2026-09-09T08:30:00' } })) };
  assert.deepEqual(JSON.parse(JSON.stringify(modelContext.window.ActualGanttModel.metrics(data))), { complete: 334, pending: 333, reported: 333, average: 30 }); assert.equal(reads, 0, 'Actual metrics consume the shared full cohort summary without recomputing execution rows');

  // R19's actual parent retains overview facts while print/fit unmount the child.
  const overviewParentHooks = hooks(), overviewThemes = [], overviewResizes = [], fills = [], pointXs = [], planWidths = [], overviewSteps = [];
  let overviewHooks = null, cssWidth = 200.2, cssHeight = 16, binBuilds = 0, overviewTimeReads = 0, printChange, primary = 'light', printing = false;
  const overviewCtx = { setTransform() {}, fillRect(...args) { fills.push({ args, color: this.fillStyle }); }, strokeRect() {} };
  const canvas = { getBoundingClientRect: () => ({ width: cssWidth, height: cssHeight }), getContext: () => overviewCtx };
  const overviewWindow = { devicePixelRatio: 1, PointContract: { isPoint: task => task.event_kind === 'point' }, PointGanttModel: { paint: (_, x) => pointXs.push(x) },
    GanttPresentation: { palette: () => ({ primary: { edge: primary }, plan: {}, gold: 'gold' }) },
    matchMedia: () => ({ addEventListener(_, fn) { printChange = fn; }, removeEventListener() {} }) };
  const overviewContext = vm.createContext({ window: overviewWindow, React: overviewParentHooks.React, document: { documentElement: {} },
    Float64Array: class extends Float64Array { constructor(length) { binBuilds++; super(length); } },
    MutationObserver: class { constructor(fn) { this.draw = fn; overviewThemes.push(this); } observe() {} disconnect() {} },
    ResizeObserver: class { constructor(fn) { this.draw = fn; overviewResizes.push(this); } observe() {} disconnect() {} },
    requestAnimationFrame(fn) { fn(); return 1; }, cancelAnimationFrame() {} });
  load(overviewContext, 'PlanGanttModel.js'); const overviewInstant = overviewWindow.PlanGanttModel.instant;
  const planAsOf = '2026-10-10T00:00:00';
  overviewWindow.PlanGanttModel.instant = value => { if (value !== planAsOf) overviewTimeReads++; return overviewInstant(value); };
  load(overviewContext, 'PlanGanttCanvas.jsx');
  const overviewTasks = [{ start: '2026-10-12T08:00:00', end: '2026-10-12T09:00:00' },
    { start: '2026-10-12T08:30:00', end: '2026-10-12T09:30:00' },
    { start: '2026-10-12T10:00:00', end: '2026-10-12T10:00:00', event_kind: 'point' }];
  const planStart = overviewInstant(overviewTasks[0].start), planEnd = overviewInstant(overviewTasks[2].end);
  const planBoard = { scrollLeft: 0, scrollTop: 0, clientWidth: 1000, clientHeight: 440 };
  Object.assign(overviewWindow.PlanGanttModel, { prepare: () => ({}), layoutPrepared(_, width) { planWidths.push(width); return { start: planStart, end: planEnd, rows: [], tasks: [],
    groupCount: 0, height: 0, locations: new Map(), baselineLocations: new Map(), conflicts: new Set(), labels: {} }; }, visibleRows: rows => rows });
  Object.assign(overviewWindow, { ResourceControls: { Button: 'button', Icon: 'icon', TimelineZoom: 'plan-zoom', timelineZoomKey: () => null },
    WorkbenchFormat: { compactDateTime: String }, WorkbenchControls: { usePrintLayout: () => printing, EmptyState: 'empty' },
    GanttPresentationUI: { useExpanded: () => ({ expanded: false }), Axis: 'axis' }, GanttGraphLayer: { Controls: 'graph-controls', Lines: 'graph-lines' },
    GanttGraph: { create: () => ({}), selection: () => ({ related: new Set(), critical: new Set() }), locations: () => new Map(), locationIndex: () => ({}), paths: () => ({}) } });
  overviewWindow.GanttPresentation.axis = () => ({ ticks: [] });
  load(overviewContext, 'PlanGantt.jsx');
  let overviewParentData = { tasks: overviewTasks, task_count: overviewTasks.length, gantt_graph: {}, projections: { baseline: { state: 'absent' }, delivery_risks: { items: [] } } };
  let overviewProps, overviewMounts = 0;
  const planRender = () => {
    overviewContext.React = overviewParentHooks.React;
    const tree = overviewParentHooks.render(() => overviewWindow.PlanGantt({ data: overviewParentData, asOf: planAsOf, selected: null, onSelect() {}, query: '', onQuery() {} }));
    find(tree, 'div', props => props.className === 'plan-board').ref.current = planBoard; overviewParentHooks.flush();
    overviewProps = find(tree, overviewWindow.PlanGanttCanvas.Overview);
    if (overviewProps) {
      if (!overviewHooks) { overviewHooks = hooks(); overviewMounts++; }
      overviewContext.React = overviewHooks.React;
      const child = overviewHooks.render(() => overviewWindow.PlanGanttCanvas.Overview(overviewProps));
      find(child, 'canvas').ref.current = canvas; overviewHooks.flush();
    } else if (overviewHooks) { overviewHooks.unmount(); overviewHooks = null; }
    return tree;
  };
  let overviewParentTree = planRender(); assert.equal(overviewProps, null); assert.equal(overviewTimeReads, 0); assert.equal(binBuilds, 0);
  find(overviewParentTree, 'plan-zoom').onZoom(2); overviewParentTree = planRender(); const parentOverviewCache = overviewProps.cache;
  assert.equal(binBuilds, 1); assert.equal(overviewTimeReads, 5); assert.equal(pointXs.at(-1), cssWidth);
  overviewSteps.push({ phase: 'first_display', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  planBoard.scrollLeft += 20; find(overviewParentTree, 'div', props => props.className === 'plan-board').onScroll();
  overviewParentTree = planRender(); primary = 'dark'; overviewThemes.at(-1).draw(); printChange();
  assert.equal(overviewProps.left, planBoard.scrollLeft);
  overviewWindow.devicePixelRatio = 2; printChange(); find(overviewParentTree, 'plan-zoom').onZoom(4); overviewParentTree = planRender();
  assert.equal(binBuilds, 1); assert.equal(overviewTimeReads, 5); assert.equal(fills.at(-1).color, 'dark');
  printing = true; overviewParentTree = planRender(); assert.equal(overviewProps, null); assert.equal(overviewHooks, null); assert.equal(planWidths.at(-1), 640);
  printing = false; overviewParentTree = planRender(); assert.strictEqual(overviewProps.cache, parentOverviewCache);
  assert.equal(overviewMounts, 2); assert.deepEqual({ date_reads: overviewTimeReads, histogram_builds: binBuilds }, { date_reads: 5, histogram_builds: 1 },
    'A freshly mounted Overview after print reuses the parent-owned date facts and histogram');
  overviewSteps.push({ phase: 'after_print_remount', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  find(overviewParentTree, 'plan-zoom').onFit(); overviewParentTree = planRender(); assert.equal(overviewHooks, null);
  find(overviewParentTree, 'plan-zoom').onZoom(2); overviewParentTree = planRender(); assert.strictEqual(overviewProps.cache, parentOverviewCache);
  assert.equal(overviewMounts, 3); assert.equal(overviewTimeReads, 5); assert.equal(binBuilds, 1);
  overviewSteps.push({ phase: 'after_fit_remount', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  cssWidth = 200.8; overviewResizes.at(-1).draw(); assert.equal(binBuilds, 2); assert.equal(overviewTimeReads, 5); assert.equal(pointXs.at(-1), cssWidth);
  cssHeight = 24; overviewResizes.at(-1).draw(); assert.equal(binBuilds, 2);
  overviewSteps.push({ phase: 'after_actual_css_resize', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  printing = true; planRender(); overviewParentData = { ...overviewParentData, tasks: overviewTasks.slice() }; planRender();
  assert.equal(overviewTimeReads, 5, 'Tasks changed while the overview is hidden wait until it is mounted');
  overviewSteps.push({ phase: 'hidden_new_tasks', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  printing = false; planRender(); assert.equal(overviewMounts, 4); assert.equal(overviewTimeReads, 10); assert.equal(binBuilds, 3);
  overviewSteps.push({ phase: 'display_new_tasks', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  overviewHooks.unmount(); overviewHooks = null; overviewParentHooks.unmount();

  // An unrestricted trial keeps its scope, resource names and row preparation on hover/scroll.
  const trialGanttHooks = hooks(); let trialFilters = 0, trialNames = 0;
  const trialTasks = [8, 9].map((hour, index) => ({ task_ref: 'task-' + index, batch_ref: 'batch', batch_id: 'B1', sequence: index + 1, process_label: '加工',
    start: '2026-10-12T0' + hour + ':00:00', end: '2026-10-12T' + String(hour + 1).padStart(2, '0') + ':00:00', machine_ref: 'machine', operator_ref: null, issues: [], quantity: 1, batch_quantity: 1, piece_id: null }));
  trialTasks.push({ ...trialTasks[1], task_ref: 'point', start: trialTasks[1].end, event_kind: 'point' });
  trialTasks.forEach(task => { task.original = { start: task.start, end: task.end, machine_ref: task.machine_ref, operator_ref: task.operator_ref }; });
  trialTasks.filter = function (...args) { trialFilters++; return Array.prototype.filter.apply(this, args); };
  const trialMachines = [{ ref: 'machine', business_code: 'M1', label: '机床' }];
  trialMachines.forEach = function (...args) { trialNames++; return Array.prototype.forEach.apply(this, args); };
  const trialGanttData = { tasks: trialTasks, task_count: 3, scope: { batch_refs: ['batch'] }, resources: { machines: trialMachines, operators: [] } };
  const trialValues = { mode: 'machine', baseline: false, only_changed: false, query: '' };
  const trialGanttWindow = { TrialControls: { Button: 'button', Tabs: 'tabs', Pager: 'pager', timeLabel: String, number: String },
    ResourceControls: { TimelineZoom: 'zoom' }, TrialViewState: { useView: () => ({ value: trialValues, change() {} }), Notice: 'notice' },
    GanttPresentationUI: { useExpanded: () => ({ expanded: false }), Axis: 'axis' }, GanttPresentation: { axis: () => ({ ticks: [] }), taskLines: () => ({ primary: '加工', secondary: '' }) },
    PointContract: { isPoint: task => task.event_kind === 'point' }, PointGantt: { Marker: 'point' }, trialRowSorts: 0 };
  const trialGanttContext = vm.createContext({ window: trialGanttWindow, React: trialGanttHooks.React, innerWidth: 1280, innerHeight: 800,
    ResizeObserver: class { observe() {} disconnect() {} } });
  load(trialGanttContext, 'PlanGanttModel.js'); load(trialGanttContext, 'TrialGantt.jsx');
  vm.runInContext(`const rowSort = Array.prototype.sort; Array.prototype.sort = function (compare) {
    if (this[0] && this[0].t) window.trialRowSorts++; return rowSort.call(this, compare);
  };`, trialGanttContext);
  const trialGanttRender = () => trialGanttHooks.render(() => trialGanttWindow.TrialGantt({ data: trialGanttData, selected: null, onSelect() {} }));
  let trialGanttTree = trialGanttRender();
  find(trialGanttTree, 'div', props => props.className === 'tt-board').ref.current = { scrollLeft: 100, clientWidth: 1000, querySelector: () => ({ getBoundingClientRect: () => ({ width: 100 }) }) };
  find(trialGanttTree, 'div', props => props.className === 'tt-ticks').ref.current = { clientWidth: 1000 };
  trialGanttHooks.flush(); trialGanttTree = trialGanttRender();
  find(trialGanttTree, 'input', props => props.type === 'checkbox' && props.checked).onChange({ target: { checked: false } }); trialGanttTree = trialGanttRender();
  const preparedTrialFilters = trialFilters, preparedTrialRows = trialGanttWindow.trialRowSorts;
  find(trialGanttTree, 'point').onHover({ clientX: 200, clientY: 200 }); trialGanttTree = trialGanttRender();
  assert(find(trialGanttTree, 'div', props => props.role === 'tooltip'));
  find(trialGanttTree, 'div', props => props.className === 'tt-board').onScroll(); trialGanttTree = trialGanttRender();
  assert.equal(trialFilters, preparedTrialFilters); assert.equal(trialGanttWindow.trialRowSorts, preparedTrialRows); assert.equal(trialNames, 1); trialGanttHooks.unmount();

  // The three overdue flags share one pass and remain frozen with the data identity.
  const toolbarHooks = hooks(); let deadlineVisits = 0;
  const toolbarData = { task_count: 3, availability: { state: 'available' }, items: [{ task: { task_ref: 'one' }, deviation: { finish_late: true, unclosed: false, forecast_late: false } },
    { task: { task_ref: 'two' }, deviation: { finish_late: false, unclosed: true, forecast_late: true } },
    { task: { task_ref: 'three' }, deviation: { finish_late: false, unclosed: true, forecast_late: false } }] };
  const toolbarWindow = { ResourceControls: { Button: 'button', Icon: 'icon', TimelineZoom: 'zoom' }, WorkbenchTerms: { overdue: '超期' },
    ActualGanttModel: { ...modelContext.window.ActualGanttModel, deadlines(item) { deadlineVisits++; return modelContext.window.ActualGanttModel.deadlines(item); },
      wire() { assert.fail('Deadlines no longer convert an unused date'); }, tickStep: () => 1, tickLabel: String } };
  const toolbarContext = vm.createContext({ window: toolbarWindow, React: toolbarHooks.React }); load(toolbarContext, 'ActualGanttControls.jsx');
  const toolbarProps = { data: toolbarData, model: { groups: [], items: toolbarData.items }, view: { mode: 'machine', query: '', late: 'all', collapsed: {}, selected: null }, width: 640, zoom: 1 };
  const toolbar = toolbarHooks.render(() => toolbarWindow.ActualGanttControls.Toolbar(toolbarProps));
  toolbarHooks.render(() => toolbarWindow.ActualGanttControls.Toolbar({ ...toolbarProps, width: 1000 })); assert.equal(deadlineVisits, 3);
  assert.deepEqual(find(toolbar, 'select').children.flat().map(option => option.props.children.join('')), ['全部工序 (3)', '已晚完成 (1)', '到期未确认完成 (2)', '剩余安排预计晚完成 (1)']);
  // A first historical supplement preserves the selected original scope's
  // start/end, including legacy separators, padding and minute storage. It never takes the
  // aggregate start from another plan or replaces known time with now.
  const fieldContext = vm.createContext({ window: { APSResourceContract: { failure: message => new Error(message) },
    WorkbenchTerms: { execution_states: {}, report_actions: {} }, WorkbenchFormat: {} } });
  load(fieldContext, 'FieldContract.js'); load(fieldContext, 'FieldDraftModel.js');
  const field = fieldContext.window.FieldDraftModel, contract = fieldContext.window.FieldContract;
  const legacyTask = { execution: { first_actual_start: '2026-09-01T00:00:00', legacy_facts: [
    { event_type: 'start', recorded_against_task_ref: 'other-plan', event_time: '2026-09-01 00:00:00', actual_machine_ref: 'other-machine', actual_operator_ref: 'other-operator' },
    { event_type: 'start', recorded_against_task_ref: 'selected-plan', event_time: '2026-09-08  08:00', actual_machine_ref: 'original-machine', actual_operator_ref: 'original-operator' }
  ] } };
  const legacy = { recorded_against_task_ref: 'selected-plan', event_time: '2026-09-09  10:00', quantity_done: 10 };
  const initialized = field.initialize({ task: legacyTask, legacy, record: null, action: 'create', now: new Date('2030-01-01T00:00:00Z') });
  assert.equal(initialized.draft.actual_start, '2026-09-08T08:00:00');
  assert.equal(initialized.draft.actual_end, '2026-09-09T10:00:00');
  assert.equal(initialized.draft.actual_machine_ref, 'original-machine');
  assert.equal(initialized.draft.actual_operator_ref, 'original-operator');
  assert.equal(contract.input(initialized.draft, null, 'create').actual_end, '2026-09-09T10:00:00');
  for (const [start, end] of [
    ['2026/09/08 08:00', '2026/09/09 10:00'],
    ['2026-09-08 08：00', '2026-09-09 10：00'],
    ['2026-9-8 8:0', '2026-9-9 10:0'],
    ['2026-09- 8 08:00', '2026-09- 9 10:00']
  ]) {
    legacyTask.execution.legacy_facts[1].event_time = start;
    const normalized = field.initialize({ task: legacyTask, legacy: { ...legacy, event_time: end }, record: null, action: 'create' });
    const values = contract.input(normalized.draft, null, 'create');
    assert.equal(values.actual_start, '2026-09-08T08:00:00');
    assert.equal(values.actual_end, '2026-09-09T10:00:00');
  }
  assert.equal(field.initialize({ task: legacyTask, record: null, action: 'create',
    legacy: { recorded_against_task_ref: 'no-start', event_time: '2026-09-09', quantity_done: 10 } }).draft.actual_start, '');
  console.log(JSON.stringify({ read_identity_and_cancellation: true, same_identity_reopen_loads: reopenLoads, error_retry_and_hidden_snapshot_loads: retryLoads, unmount_refresh_waiters_cancelled: outcomes.length, unstarted_refresh_loads: queuedLoads,
    baseline_reopen_reads: 1, baseline_refresh_and_identity_reads: baselineLoads,
    resource_related_save_requests: resourceRequests.map(value => ({ kind: value.kind, page: value.page, snapshot_ref: value.snapshot_ref || null })),
    resource_related_save_detail_reads: resourceDetails, overview_time_reads: overviewTimeReads, overview_bin_builds: binBuilds,
    overview_mounts: overviewMounts, overview_preparation_steps: overviewSteps,
    trial_filter_calls: trialFilters, trial_row_sorts: trialGanttWindow.trialRowSorts, trial_resource_name_passes: trialNames, actual_deadline_visits: deadlineVisits,
    scroll_scans: scans, unrelated_scroll_refreshes: 0, context_updates: 60,
    trailing_history_writes: 1, immediate_navigation_and_history_restore: true, restoring_pagehide_preserved: true,
    forward_branch_plan_bound: true, history_help_chapters: true, dashboard_issue_scope_and_return: true, dashboard_late_request_isolated: true,
    dashboard_whole_run_preserves_highlight: true, plan_range_resets_analysis_page: true, stale_plan_page_clamped: true,
    same_plan_range_keeps_analysis_page: true, trial_task_opens_details: true, gantt_selection_keeps_details_closed: true,
    trial_edit_guard_preserved: true, metric_task_visits: reads }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
