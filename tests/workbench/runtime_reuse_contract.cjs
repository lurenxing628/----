'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const babel = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
const { routeFetch, envelope, file, browser, loadTransport } = require('./route_fetch.cjs');
const source = name => fs.readFileSync(path.join(app, name), 'utf8');
const unavailableGraph = () => ({ state: 'unavailable', reason: 'No captured process order', scope: 'full_plan', nodes: [], critical_task_refs: [], critical_edges: [] });
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
// Contexts that write or read through APSWorkbenchTransport load it the way the bundle does: WorkbenchTerms, then transport,
// with a fetch that fails loudly unless a section installs routes of its own.
function withTransport(context, routes = {}) {
  load(context, 'WorkbenchTerms.js'); const fetch = routeFetch(routes); browser(context, fetch); loadTransport(context); return fetch;
}
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
  baselineWindow.RunBaselineAPI = { read: async () => { baselineLoads++; return frozenBaseline; } };
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

  // Overview initialization and location consume their captured detail; later interaction reads current facts.
  const masterHooks = hooks(), masterRequests = [], masterRefs = ['a'.repeat(48), 'b'.repeat(48)];
  const masterEntity = ref => ({ key: 'material:' + ref, ref, domain: 'material', business_code: ref[0], label: '原料 ' + ref[0],
    status: 'attention', issue_count: 1, relation_count: 0, known_relation_count: 0, filled_fields: 0, checked_fields: 0,
    checks_complete: true, relations_complete: true, summary: '待核对到料',
    target: { view: 'process', context: { source: 'production', kind: 'material', entity_ref: ref } } });
  const masterIssue = (ref, title) => ({ key: 'issue:' + ref, issue_ref: 'arrival:' + ref, entity_ref: ref, domain: 'material',
    business_code: ref[0], label: '原料 ' + ref[0], status: 'attention', issue_count: 1, relation_count: 0,
    rule: 'arrival', title, evidence: title, action: '核对到料', target: masterEntity(ref).target });
  const masterListeners = {};
  const masterWindow = { ResourceControls: { Button: 'button', ErrorBox: 'error', MetricValue: 'metric' },
    MasterOverviewTable: { Table: 'master-table', Tabs: 'master-tabs', Pager: 'master-pager' }, MasterOverviewDetail: 'master-detail',
    WorkbenchPageContext: { useSnapshot() {} }, WorkbenchFormat: { dateTime: String },
    addEventListener(name, fn) { masterListeners[name] = fn; }, removeEventListener() {} };
  const masterContext = vm.createContext({ window: masterWindow, React: masterHooks.React, AbortController, URLSearchParams });
  load(masterContext, 'WorkbenchTerms.js'); load(masterContext, 'MasterOverviewContract.js');
  const masterDetail = (scope, ref, section, title) => ({ scope, entity: masterEntity(ref), section,
    counts: { issues: 1, relations: 0, fields: 0 }, rows: section === 'issues' ? [masterIssue(ref, title)] : [],
    page: { number: 1, pages: 1, size: 10, total: section === 'issues' ? 1 : 0 } });
  // Fetch-level answers: the real MasterOverviewAPI, transport and contract validate every response.
  const masterTokens = { list: 'M'.repeat(32), located: 'L'.repeat(32) };
  const masterAnswer = call => {
    const scope = JSON.parse(call.query.scope); masterRequests.push(call.url);
    if (call.path.includes('/entities/')) return envelope(masterDetail(scope, call.path.split('/').at(-1), call.query.section, '当前到料'), { snapshot_ref: call.query.snapshot_ref });
    const located = call.path.includes('/locate/'), ref = located ? call.path.split('/').at(-1) : masterRefs[0];
    const currentScope = located ? masterWindow.APSMasterOverviewContract.scope({ view: 'entities', domain: 'material', sort: 'business_code', direction: 'asc' }) : scope;
    return envelope({ scope: currentScope, rows: masterRefs.map(value => located ? masterEntity(value) : masterIssue(value, '捕获到料')),
      page: { number: 1, pages: 1, size: 20, total: 2 }, selected_detail: masterDetail(currentScope, ref, 'issues', '捕获到料'),
      ...(located ? { selected: { domain: 'material', entity_ref: ref } } : {}),
      overview: { complete: true, basis: '基础资料', gaps: [], stats: { entities: 2, issues: 2, affected: 2, relations: 0, known_relation_pairs: 0 },
        domains: masterWindow.APSMasterOverviewContract.domains.map(([id]) => ({ id, loaded: true,
          count: id === 'material' ? 2 : 0, attention: id === 'material' ? 2 : 0, unknown: 0 })) } }, { snapshot_ref: located ? masterTokens.located : masterTokens.list });
  };
  browser(masterContext, routeFetch({ 'GET /api/workbench/v1/master-overview': masterAnswer, 'GET /api/workbench/v1/master-overview/entities/*/*': masterAnswer,
    'GET /api/workbench/v1/master-overview/locate/*/*': masterAnswer })); loadTransport(masterContext);
  load(masterContext, 'MasterOverviewAPI.js'); load(masterContext, 'MasterOverviewWorkspace.jsx');
  let masterTree;
  async function settleMaster() {
    for (let index = 0; index < 4; index++) { masterTree = masterHooks.render(() => masterWindow.MasterOverviewWorkspace({ initialContext: {} })); masterHooks.flush(); await turns(); }
  }
  const masterDetailReads = () => masterRequests.filter(url => url.pathname.includes('/entities/')).length;
  await settleMaster();
  assert.equal(masterRequests.length, 1); assert.equal(masterDetailReads(), 0);
  assert.equal(find(masterTree, 'master-detail').result.data.entity.ref, masterRefs[0]);
  find(masterTree, 'master-table').onSelect(find(masterTree, 'master-table').data.rows[1], null); await settleMaster();
  assert.equal(masterDetailReads(), 1); assert.equal(find(masterTree, 'master-detail').result.data.rows[0].title, '当前到料');
  find(masterTree, 'master-detail').onLocate({ domain: 'material', entity_ref: masterRefs[1] }); await settleMaster();
  assert.equal(masterRequests.filter(url => url.pathname.includes('/locate/')).length, 1); assert.equal(masterDetailReads(), 1);
  assert.equal(find(masterTree, 'master-detail').result.data.entity.ref, masterRefs[1]);
  assert.equal(find(masterTree, 'master-detail').result.data.rows[0].title, '捕获到料');
  find(masterTree, 'master-detail').onSection('fields'); await settleMaster();
  find(masterTree, 'master-table').onSelect(find(masterTree, 'master-table').data.rows[0], null);
  masterTree = masterHooks.render(() => masterWindow.MasterOverviewWorkspace({ initialContext: {} }));
  assert.equal(find(masterTree, 'master-detail').section, 'issues');
  assert.equal(find(masterTree, 'master-detail').result, null);
  assert.equal(find(masterTree, 'master-detail').loading, true);
  await settleMaster();
  assert.equal(masterDetailReads(), 3); assert.equal(find(masterTree, 'master-detail').result.data.rows[0].title, '当前到料');
  find(masterTree, 'master-detail').onBack();
  masterListeners.focus();
  masterTree = masterHooks.render(() => masterWindow.MasterOverviewWorkspace({ initialContext: {} }));
  assert.equal(find(masterTree, 'master-detail').selected, null);
  find(masterTree, 'button', props => Array.isArray(props.children) && props.children.includes('刷新本页')).onClick();
  await settleMaster();
  assert.equal(find(masterTree, 'master-detail').selected, null);
  assert.equal(find(masterTree, 'master-detail').result, null);
  masterHooks.unmount();

  // The current issue batch owns the comparison scope across analysis changes and page restoration.
  let dashboardHooks = hooks(); const dashboardRequests = [], dashboardStates = [];
  const dashboardRun = '1'.repeat(48), dashboardCandidate = '2'.repeat(48), batchOne = '3'.repeat(48), batchTwo = '4'.repeat(48);
  const dashboardChoice = { run_ref: dashboardRun, candidate_ref: dashboardCandidate,
    range_start: '2026-10-13T00:00:00', range_end: '2026-10-31T00:00:00' };
  const dashboardApi = {
    catalog: async () => ({ data: { candidates: [{ candidate_ref: dashboardCandidate, label: '原算法', status: 'completed', task_count: 2 }],
      candidate_count: 1, page: { has_more: false } }, meta: { snapshot_ref: 'dashboard-directory' } }),
    workspace: (candidateRef, scope, signal) => new Promise(resolve => dashboardRequests.push({ kind: 'workspace', candidateRef, scope, signal, resolve }))
  };
  const dashboardWindow = { RunCandidateAPI: { ...dashboardApi, time: value => typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(value) },
    DashboardCandidatePanels: { Metrics: 'dashboard-metrics', Batches: 'dashboard-batches', Summary: 'dashboard-summary' },
    ResourceControls: { Button: 'button', ErrorBox: 'error', Issues: 'issues' }, WorkbenchReference: 'reference',
    WorkbenchFormat: { dateTime: String, compactRange: (start, end) => start + ' / ' + end, compactDateTime: String },
    WorkbenchTerms: { candidate_statuses: { completed: '计算完成' }, hold_window: () => '未设置', material_strategy: () => '全部齐套' } };
  const dashboardContext = vm.createContext({ window: dashboardWindow, React: dashboardHooks.React, AbortController });
  load(dashboardContext, 'DashboardContract.js'); load(dashboardContext, 'DashboardAnalysisAPI.js'); load(dashboardContext, 'DashboardCandidateComparisonAPI.js');
  // Component-ownership check: the comparison read itself is covered by its own contract, so only its answer timing is held here.
  dashboardWindow.DashboardCandidateComparisonAPI.read = (scope, signal) => new Promise(resolve =>
    dashboardRequests.push({ kind: 'comparison', candidateRef: scope.candidate_ref, scope, signal, resolve }));
  load(dashboardContext, 'DashboardCandidates.jsx');
  let dashboardProps = { catalog: { runs: [{ run_ref: dashboardRun, candidate_count: 1, accepted_at: dashboardChoice.range_start }] },
    initialContext: { run_ref: dashboardRun, candidate_ref: dashboardCandidate, batch_ref: batchTwo }, issueBatchRef: batchOne, selectedBatch: batchOne,
    onSelectBatch() {}, onState: state => dashboardStates.push(JSON.parse(JSON.stringify(state))) };
  const renderDashboard = () => { const tree = dashboardHooks.render(() => dashboardWindow.DashboardCandidates(dashboardProps)); dashboardHooks.flush(); return tree; };
  const completeDashboard = async request => {
    const data = { candidate: { candidate_ref: request.candidateRef, run_ref: dashboardRun, label: '原算法' }, batch_ref: request.scope.batch_ref || null,
      generation: { run_ref: dashboardRun, input: { start_date: '2026-10-13', end_date: '2026-10-30', ready_check: true, missing_resource_policy: 'exclude', hold_window: null } } };
    if (request.kind === 'comparison') {
      const batchRefs = request.scope.batch_ref ? [request.scope.batch_ref] : [batchOne, batchTwo];
      Object.assign(data, { baseline: { available: false }, batch_refs: batchRefs,
        batches: batchRefs.map(batch_ref => ({ batch_ref, batch_id: batch_ref === batchOne ? 'DC-01' : 'DC-02' })) });
    }
    request.resolve({ data }); await turns(); await turns();
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
  assert.deepEqual(dashboardRequests.map(request => request.kind), ['workspace', 'comparison']);
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
  assert.equal(dashboardRequests.length, 6, 'Each known-range read issues one complete comparison request');
  assert.equal(dashboardRequests.filter(request => request.kind === 'workspace').length, 1, 'Only the initial missing range reads the workspace');
  assert.equal(Object.prototype.hasOwnProperty.call(wholeDashboardRequest.scope, 'batch_ref'), false);
  assert.equal(find(dashboardTree, 'reference', props => props.entries && '原问题批次编号' in props.entries), null);
  assert.deepEqual(Array.from(find(dashboardTree, 'dashboard-batches').data.batches, row => row.batch_id), ['DC-01', 'DC-02']);
  assert.equal(find(dashboardTree, 'dashboard-batches').selected, batchOne, 'General catalog highlighting keeps its parent selection without narrowing the request');
  assert.deepEqual(dashboardStates.at(-1).context, dashboardChoice); dashboardHooks.unmount();

  // A narrower plan scope starts on its first analysis page; stale remembered pages still show available rows.
  const planHooks = hooks(), timeScope = { range_start: '2026-10-12T08:00:00', range_end: '2026-10-14T18:00:00' };
  const planData = { plan: { plan_ref: planA, display_name: '正式计划', kind: 'official', version: 1, is_current_official: true },
    scope: { range_start: null }, time_scope: timeScope, plan_span: { start: timeScope.range_start, end: timeScope.range_end, end_inclusive: true },
    task_count: 0, tasks: [], resources: [], provenance: {}, gantt_graph: unavailableGraph(), projections: { calendar: { resources: [] }, occupancy: { resources: [] }, baseline: { state: 'unavailable' }, delivery_risks: { state: 'available', issues: [], items: [] } } };
  const planRead = { result: { data: planData, warnings: [], meta: { snapshot_ref: 'plan-snapshot' } }, loading: false, error: null, reload() {} };
  const planWindow = { APSResourceContract: { failure: text => new Error(text) }, APSPlanContract: { workspaceScope: (_, value) => value },
    APSResourceSession: { useQuery: () => planRead }, ResourceControls: { Button: 'button', ErrorBox: 'error', Issues: 'issues' },
    PlanCatalogUI: { Catalog: 'catalog' },
    WorkbenchFormat: { compactRange: () => '时间范围', dateTime: String }, WorkbenchDatePickerModel: { factoryTime: value => value },
    WorkbenchTerms: { current_official: '当前正式计划', plan_version: String },
    PlanDetailsUI: { TaskDetail: 'task-detail', ProjectionTables: 'projection-tables', Conflicts: 'conflicts' },
    WorkbenchPageContext: { useSnapshot() {} }, WorkbenchCaption: { useCaption() {} }, WorkbenchControls: { Pager: 'pager', EmptyState: 'empty' } };
  const planContext = vm.createContext({ window: planWindow, React: planHooks.React });
  load(planContext, 'GanttGraph.js'); load(planContext, 'PlanGanttModel.js'); Object.assign(planWindow.PlanGanttModel, { names: () => new Map(), timeLabel: String, number: String });
  load(planContext, 'PlanWorkspace.jsx', source('PlanWorkspace.jsx').replace('window.PlanWorkspace = PlanWorkspace;', 'window.PlanWorkspaceSession = WorkspaceSession;'));
  const renderPlan = () => planHooks.render(() => planWindow.PlanWorkspaceSession({ initialContext: { plan_ref: planA, projection_page: 3 }, renderTrial: () => null }));
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
  const projection = planHooks.render(() => planWindow.PlanDetailsUI.ProjectionTables({ data: planData, prepared: planWindow.PlanGanttModel.prepare(planData), tab: 'risk', page: 3, onPage() {}, onTab() {}, onBatch() {} }));
  assert.equal(find(projection, 'pager').page, 1); assert(find(projection, 'button', props => props.children.includes('B-01')));
  assert.equal(find(projection, 'empty'), null);

  {
  // A route outside the loaded tasks uses the complete graph to perform one bounded read.
  const routeHooks = hooks(), requests = [], ref = number => number.toString(16).padStart(48, '0');
  const tasks = [
    { task_ref: ref(1), operation_ref: ref(11), start: '2026-10-12T08:00:00', end: '2026-10-12T09:00:00' },
    { task_ref: ref(2), operation_ref: ref(12), start: '2026-10-15T23:00:00.123456', end: '2026-10-16T00:00:00.654321' },
    { task_ref: ref(3), operation_ref: ref(13), start: '2026-12-31T23:59:59.999999', end: '2026-12-31T23:59:59.999999', event_kind: 'point', duration_seconds: 0, occupies_resources: false }
  ].map(task => ({ ...task, batch_id: 'ROUTE', piece_id: null, sequence: 1, process_label: '路线工序', machine_ref: null, operator_ref: null }));
  const graph = { state: 'available', reason: null, scope: 'full_plan', nodes: tasks.map(task => ({ ...task, predecessor_operation_refs: [] })), critical_task_refs: [], critical_edges: [] };
  const routeWindow = { APSResourceContract: { failure: text => new Error(text) }, APSPlanContract: { workspaceScope: (_, scope) => scope },
    ResourceControls: { Button: 'button', ErrorBox: 'error', Issues: 'issues' }, PlanCatalogUI: { Catalog: 'catalog' },
    PlanDetailsUI: { TaskDetail: 'task-detail', ProjectionTables: 'projection-tables', Conflicts: 'conflicts' }, PlanGantt: 'plan-gantt', PlanExportUI: 'plan-export',
    WorkbenchTerms: { current_official: '当前正式计划', plan_version: String }, WorkbenchPageContext: { useSnapshot() {} }, WorkbenchCaption: { useCaption() {} }, WorkbenchControls: { EmptyState: 'empty' } };
  const routeContext = vm.createContext({ window: routeWindow, React: routeHooks.React, AbortController, DOMException });
  for (const name of ['resource-session.js', 'WorkbenchFormat.js', 'WorkbenchDatePickerModel.js', 'PointContract.js', 'GanttGraph.js', 'PlanContract.js', 'PlanGanttModel.js']) load(routeContext, name);
  const createRouteGraph = routeWindow.GanttGraph.create; let routeGraphBuilds = 0;
  routeWindow.GanttGraph.create = graph => { routeGraphBuilds++; return createRouteGraph(graph); };
  load(routeContext, 'PlanWorkspace.jsx', source('PlanWorkspace.jsx').replace('window.PlanWorkspace = PlanWorkspace;', 'window.PlanWorkspaceSession = WorkspaceSession;'));
  // Workspace-ownership check: the plan read's own validation is covered by plan_transport_probe; here only its answers are counted.
  routeWindow.APSPlanAPI = { async workspace(_plan, scope) {
    requests.push(JSON.parse(JSON.stringify(scope)));
    const task = tasks.find(task => task.start === scope.range_start);
    return { warnings: [], meta: { snapshot_ref: 'route-' + requests.length }, data: { ...planData, scope,
      tasks: [task], task_count: 1, gantt_graph: graph, time_scope: scope } };
  } };
  const routeProps = { view: 'gantt', renderTrial: () => null, initialContext: { plan_ref: planA, selected_task_ref: tasks[0].task_ref, range_start: tasks[0].start, range_end: tasks[0].end } };
  const settleRoute = async () => { let tree; for (let index = 0; index < 4; index++) { tree = routeHooks.render(() => routeWindow.PlanWorkspaceSession(routeProps)); routeHooks.flush(); await turns(); } return tree; };
  let routeTree = await settleRoute(); assert.equal(requests.length, 1); assert.equal(routeGraphBuilds, 1);
  assert.strictEqual(find(routeTree, 'plan-gantt').prepared, find(routeTree, 'task-detail').prepared, 'Drawing and details receive the original preparation object');
  find(routeTree, 'task-detail').onRelated(tasks[1].task_ref); routeTree = await settleRoute();
  assert.equal(requests.length, 2); assert.equal(routeGraphBuilds, 2); assert.deepEqual(requests[1], { range_start: tasks[1].start, range_end: tasks[1].end });
  assert.equal(find(routeTree, 'task-detail').selected.task.task_ref, tasks[1].task_ref);
  find(routeTree, 'task-detail').onRelated(tasks[2].task_ref); routeTree = await settleRoute();
  assert.equal(requests.length, 3); assert.equal(routeGraphBuilds, 3); assert.deepEqual(requests[2], { range_start: tasks[2].start, range_end: '2027-01-01T00:00:00' });
  assert.equal(find(routeTree, 'task-detail').selected.task.task_ref, tasks[2].task_ref);
  const beforeLocal = requests.length; find(routeTree, 'task-detail').onRelated(tasks[2].task_ref); await settleRoute();
  assert.equal(requests.length, beforeLocal, 'Locating a loaded node uses its existing task without reading');
  assert.equal(routeGraphBuilds, 3, 'The workspace prepares the graph once per successful result; local selection reuses it'); routeHooks.unmount();
  }

  {
  const fileHooks = hooks(), command = { phase: 'idle', locked: false, clearRejection: () => false }, preview = { can_confirm: true, preview_ref: 'preview', write_context: {}, rows: [], summary: { total: 3, changed: 3 } };
  const fileWindow = { FieldContract: { query: value => value, blocked: () => '' }, FieldControls: { Button: 'button', Modal: 'modal', ErrorBox: 'error', Feedback: 'feedback' } };
  const fileContext = vm.createContext({ window: fileWindow, React: fileHooks.React, AbortController }); load(fileContext, 'FieldFiles.jsx');
  const fileProps = { adapter: { previewFile: async () => ({ data: preview }) }, command, scope: {}, snapshot: 'snapshot' };
  const renderFile = () => fileHooks.render(() => fileWindow.FieldFiles(fileProps));
  let fileTree = renderFile(); find(fileTree, 'input').onChange({ target: { files: [{ name: '报工.xlsx', size: 10 }] } }); fileTree = renderFile();
  await find(find(fileTree, 'modal').footer, 'button', props => props.children.includes('开始预检')).onClick(); fileTree = renderFile();
  assert(find(fileTree, 'p', props => props.children.includes('预检通过，尚未写入报工。')));
  command.phase = 'rejected'; fileTree = renderFile();
  const rejectedImport = find(find(fileTree, 'modal').footer, 'button', props => props.children.includes('确认导入'));
  assert.equal(rejectedImport.disabled, true, 'A rejected import must be prechecked again before another confirmation');
  assert.equal(rejectedImport.reason, '本次未导入，请重新预检后再确认。');
  assert.equal(find(fileTree, 'p', props => props.children.includes('预检通过，尚未写入报工。')), null);
  command.phase = 'done'; fileTree = renderFile();
  assert.equal(find(fileTree, 'p', props => props.children.includes('预检通过，尚未写入报工。')), null);
  assert(find(fileTree, 'div', props => props.className === 'field-files-summary')); assert(find(fileTree, 'table'));
  assert.strictEqual(find(fileTree, 'feedback').command, command); fileHooks.unmount();
  }

  // Result/constraint/preparation task selection uses the same guarded detail-opening action.
  const trialHooks = hooks(), trialData = { draft_ref: 'draft', base: {}, base_identity: {}, name: '试调', status: 'editing',
    baseline: { version: null }, time_scope: { start: timeScope.range_start, end: timeScope.range_end }, comparison: {}, tasks: [], validation: { constraints_status: 'valid' } };
  let mayLeave = true, guardCalls = 0, trialCommands = { blocked: false, clearError() {} };
  const trialWindow = { addEventListener() {}, removeEventListener() {}, TrialAPI: {}, TrialContract: {},
    TrialControls: { Button: 'button', ErrorBox: 'error', Modal: 'modal', Issues: 'issues', statusLabel: String, sourceLabel: () => '原安排' },
    TrialSession: { useRead: () => ({ result: { data: trialData, meta: {} }, busy: false, error: null }), useCommands: () => trialCommands },
    WorkbenchGuards: { useDirtyGuard() {}, confirmLeave: async () => { guardCalls++; return mayLeave; } }, WorkbenchReference: 'reference',
    WorkbenchCaption: { useCaption() {} }, WorkbenchFormat: { dateTime: String, compactRange: () => '时间范围' }, WorkbenchTerms: { delivery_coverage: () => '', actions: { query_result: '查询结果' } },
    TrialCatalog: { Directory: 'trial-directory', Create: 'trial-create' }, TrialGantt: 'trial-gantt', TrialDetails: 'trial-details', TrialResults: { Summary: 'trial-summary', Results: 'trial-results' } };
  const trialSource = source('TrialWorkspace.jsx').replace('window.WorkbenchTrialWorkspace = WorkbenchTrialWorkspace;', 'window.TrialWorkspaceSession = Session; window.TrialFinish = Finish;');
  const trialContext = vm.createContext({ window: trialWindow, React: trialHooks.React, document: { documentElement: {} } });
  load(trialContext, 'TrialWorkspace.jsx', trialSource);
  const renderTrial = () => trialHooks.render(() => trialWindow.TrialWorkspaceSession({ initialTarget: { draft_ref: 'draft' }, onTargetChange() {} }));
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

  // A pending trial submission has one visible owner: the rendered dialog, otherwise the page notice.
  const pendingKey = 'trial-' + 'a'.repeat(48), commandError = new Error('上次试调提交结果还没查到');
  trialCommands = { blocked: true, busy: false, key: pendingKey, note: '上次试调提交待确认。', error: commandError, lookup() {}, restore() {}, clearError() {} };
  const pendingNotice = tree => find(tree, 'section', props => props['aria-label'] === '待确认的试调提交');
  const commandErrorBox = tree => find(tree, 'error', props => props.error === commandError);
  trialTree = renderTrial(); assert(pendingNotice(trialTree) && commandErrorBox(trialTree), 'Without a dialog the page owns the pending submission');
  await find(trialTree, 'button', props => props.children.includes('保存试调方案')).onClick(); trialTree = renderTrial();
  const finishProps = find(trialTree, trialWindow.TrialFinish);
  assert(finishProps); assert.equal(pendingNotice(trialTree), null, 'The save dialog owns the pending submission'); assert.equal(commandErrorBox(trialTree), null);
  const finishHooks = hooks(), finishWindow = { ...trialWindow };
  load(vm.createContext({ window: finishWindow, React: finishHooks.React, document: { documentElement: {} } }), 'TrialWorkspace.jsx', trialSource);
  const finishModal = finishHooks.render(() => finishWindow.TrialFinish({ ...finishProps, data: { ...trialData, task_count: 0, unplanned_operations: [] } }));
  assert.equal(finishModal.props.locked, true);
  assert.strictEqual(find(finishModal.props.footer, 'button', props => props.children.includes('查询结果')).onClick, trialCommands.lookup, 'The locked dialog keeps result lookup reachable');
  assert(find(finishModal, 'reference', props => props.value === pendingKey)); assert(find(finishModal, 'p', props => props.children.includes(trialCommands.note)));
  finishProps.onClose(); trialTree = renderTrial(); assert(pendingNotice(trialTree));
  await find(trialTree, 'button', props => props.children.includes('新增试调')).onClick(); trialTree = renderTrial();
  assert(find(trialTree, 'trial-create')); assert.equal(pendingNotice(trialTree), null, 'The create dialog owns the pending submission'); assert.equal(commandErrorBox(trialTree), null);
  const catalogHooks = hooks(), catalogWindow = { ...trialWindow, TrialSession: { useRead: () => ({ result: null, busy: false, error: null }) } };
  load(vm.createContext({ window: catalogWindow, React: catalogHooks.React }), 'TrialCatalog.jsx');
  const catalogModal = commands => catalogHooks.render(() => catalogWindow.TrialCatalog.Create({ initialBase: { plan_ref: 'plan' }, commands, onClose() {} }));
  let createModal = catalogModal(trialCommands); assert.equal(createModal.props.locked, true);
  assert.strictEqual(find(createModal.props.footer, 'button', props => props.children.includes('查询结果')).onClick, trialCommands.lookup);
  assert(find(createModal, 'reference', props => props.value === pendingKey)); assert(find(createModal, 'p', props => props.children.includes(trialCommands.note)));
  createModal = catalogModal({ ...trialCommands, key: null, error: null, blocked: false });
  assert.equal(find(createModal.props.footer, 'button', props => props.children.includes('查询结果')), null);

  {
  // A server-confirmed outcome stays final when the local key cannot be cleared; lookup and restore retry only that cleanup.
  const sessionHooks = hooks(), storage = { key: null }, receipts = [];
  let clearFailure = null, lookups = 0, outcome = null;
  const sessionWindow = { addEventListener() {}, removeEventListener() {}, WorkbenchTerms: { outcomes: { pending: action => '上次' + action + '待确认' } },
    TrialAPI: { PENDING_KEY: 'pending', pending: () => storage.key, reserve: () => (storage.key = 'trial-' + 'b'.repeat(48)),
      clear() { if (clearFailure) throw clearFailure; storage.key = null; }, command: async () => outcome(), lookup: async () => { lookups++; return { state: 'not_observed', receipt: null }; } } };
  const sessionContext = vm.createContext({ window: sessionWindow, React: sessionHooks.React }); loadTransport(sessionContext); load(sessionContext, 'TrialSession.js');
  const useSession = () => sessionHooks.render(() => sessionWindow.TrialSession.useCommands(receipt => receipts.push(receipt)));
  let session = useSession(); sessionHooks.flush();
  const receipt = { data: { draft_ref: 'draft' } }, rejected = sessionWindow.APSWorkbenchTransport.failure({ ok: false, committed: false, error: { code: 'stale_write', message: '来源已变化', fields: [], retryable: false, request_ref: '1'.repeat(32) } }, 409);
  clearFailure = new Error('本机操作记录没清掉'); outcome = async () => receipt;
  assert.equal(await useSession().execute({ action: 'save' }, 'token'), true); session = useSession();
  assert.strictEqual(session.receipt, receipt); assert.deepEqual(receipts, [receipt], 'A failed local clear must not withhold the confirmed receipt');
  assert.equal(session.key, storage.key); assert.strictEqual(session.error, clearFailure); assert.equal(session.blocked, true);
  await session.lookup(); session = useSession();
  assert.equal(session.key, storage.key); assert.strictEqual(session.error, clearFailure); assert.equal(lookups, 0, 'A confirmed receipt only retries its local cleanup');
  clearFailure = null; await session.lookup(); session = useSession();
  assert.deepEqual([storage.key, session.key, session.error, session.note, lookups], [null, null, null, '', 0]); assert.deepEqual(receipts, [receipt], 'Cleanup does not replay the receipt');
  clearFailure = new Error('本机操作记录没清掉'); outcome = async () => { throw rejected; };
  assert.equal(await session.execute({ action: 'save' }, 'token'), false); session = useSession();
  assert.equal(session.key, storage.key); assert.strictEqual(session.error, clearFailure);
  assert.equal(session.note, '这次没有写入，但本机操作记录还没清掉。请点「查询结果」重试清理。');
  clearFailure = null; await session.lookup(); session = useSession();
  assert.deepEqual([storage.key, session.key, session.error, session.note, lookups], [null, null, null, '', 0], 'A rejected command must not wait on not_observed');
  clearFailure = new Error('本机操作记录没清掉'); await session.execute({ action: 'save' }, 'token'); clearFailure = null;
  session.restore(); session = useSession(); assert.deepEqual([storage.key, session.key, session.error], [null, null, null], 'Restore shares the same cleanup retry');
  storage.key = 'trial-' + 'c'.repeat(48); session.restore(); await session.lookup(); session = useSession();
  assert.deepEqual([session.key, session.note, lookups], [storage.key, '上次提交待确认', 1], 'An unconfirmed key still asks the server');
  sessionHooks.unmount();
  }

  // Related-resource editing keeps the current list on its displayed clamped page.
  const resourceHooks = hooks(), resourceRequests = [], resourceDetails = [], resourceSnapshots = [];
  const machineRef = '1'.repeat(48), operatorRef = '2'.repeat(48);
  const resourceForms = () => null; resourceForms.Detail = 'resource-detail'; resourceForms.Feedback = 'resource-feedback';
  const resourceTables = () => null; resourceTables.Pager = 'resource-pager';
  const resourceContract = { nodes: { machine: { kind: 'machine', label: '设备', chain: 'internal' }, operator: { kind: 'operator', label: '人员', chain: 'internal' } },
    statuses: { machine: [], operator: [] }, object: value => value !== null && typeof value === 'object' && !Array.isArray(value),
    own: (value, key) => Object.prototype.hasOwnProperty.call(value, key), query: value => value, failure: message => new Error(message),
    message: error => error.message, blocked: () => '', receipt: value => value && value.ok ? 'terminal' : 'pending',
    stale: error => !!error && ['stale_write', 'snapshot_stale'].includes(error.code), resultRef: (value, fallback) => value.data.entity_ref || fallback };
  const resourceAdapter = {
    readPending() { return null; }, savePending() {}, clearPending() {},
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
    ResourceTableFilterModel: { rules: filters => filters }, WorkbenchPageContext: { useSnapshot: (...args) => resourceSnapshots.push(args) },
    addEventListener() {}, removeEventListener() {} };
  const resourceContext = vm.createContext({ window: resourceWindow, React: resourceHooks.React, AbortController, DOMException });
  withTransport(resourceContext); load(resourceContext, 'resource-session.js'); resourceWindow.APSResourceSession.useCounts = () => ({ summary: { reload() {} } });
  load(resourceContext, 'ResourceWorkspace.jsx');
  const resourceContextInput = { source: 'production', kind: 'machine', read_view: { scope: { query: '', status: '', page: 3, size: 20, sort: 'business_code', direction: 'asc' },
    selected_refs: [], sort_active: false, detail: null } };
  const resourceRender = () => resourceHooks.render(() => resourceWindow.ResourceWorkspace({ adapter: resourceAdapter, initialContext: resourceContextInput, onNavigationReady() {} }));
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

  // Op-type entity membership can be both; command readback keeps the originating list.
  async function opTypeWorkspace(initialNode, existing = false) {
    const workspaceHooks = hooks(), localWindow = {
      ResourceControls: Object.fromEntries(['Button', 'Icon', 'ErrorBox', 'Issues', 'Status', 'Modal', 'Choice', 'Relation', 'Field'].map(name => [name, name])),
      ResourceRail: 'resource-rail', ResourceMetrics: 'resource-metrics',
      ResourceTableFilterModel: { rules: filters => filters }, WorkbenchPageContext: { useSnapshot() {} },
      WorkbenchGuards: { useDirtyGuard: () => 'op-type-form', confirmLeave: async () => true }, WorkbenchTerms: { refresh_latest: '刷新最新资料' },
      crypto: { getRandomValues: bytes => bytes.fill(1) }, addEventListener() {}, removeEventListener() {}
    };
    localWindow.ResourceControls.focusFirstInvalid = () => {};
    const tables = () => null; tables.Pager = 'resource-pager'; localWindow.ResourceTables = tables;
    const context = vm.createContext({ window: localWindow, React: workspaceHooks.React, AbortController, DOMException });
    withTransport(context); for (const name of ['resource-contract.js', 'resource-session.js', 'ResourceForms.jsx', 'ResourceWorkspace.jsx']) load(context, name);
    localWindow.APSResourceSession.useCounts = () => ({ summary: { reload() {} } });
    const ref = '3'.repeat(48), supplierRef = '4'.repeat(48), requests = [], details = [], saved = [], writes = [];
    const writeContext = { write_token: 'op-type-token', capabilities: { 'op_type.create': true, 'op_type.update': true, 'op_type.delete': true }, blocked_reasons: [] };
    const makeEntity = (kind, fields = {}) => ({ ref: kind === 'supplier' ? supplierRef : ref, business_code: kind === 'supplier' ? 'SUPPLIER' : 'F01-BOTH',
      label: kind === 'supplier' ? '供应商' : '两用工种', status: kind === 'supplier' ? 'active' : null, fields, relationships: {}, issues: [], write_context: writeContext });
    let entity = existing ? makeEntity('op_type', { category: 'both', default_merge_mode: 'separate', remark: '原备注' }) : null;
    const envelope = data => ({ ok: true, schema_version: 1, data, warnings: [], meta: { source: 'production', time_basis: 'factory_local',
      snapshot_ref: 'op-snapshot-' + requests.length, request_ref: 'op-request', as_of: '2026-10-18T08:00:00' } });
    const api = {
      async list(kind, scope) {
        requests.push({ kind, ...JSON.parse(JSON.stringify(scope)) });
        if (kind === 'op_type') assert(['internal', 'external'].includes(scope.category), 'List readback must use a real list category');
        const entities = kind === 'supplier' ? [makeEntity('supplier')] : entity && [scope.category, 'both'].includes(entity.fields.category) ? [entity] : [];
        return envelope({ entities, create_context: writeContext, page: { number: scope.page, size: scope.size, total: entities.length, pages: 1, sort: [] } });
      },
      async detail(kind, selectedRef) { details.push({ kind, ref: selectedRef }); assert.equal(selectedRef, kind === 'supplier' ? supplierRef : ref); return envelope(kind === 'supplier' ? makeEntity('supplier') : entity); },
      readPending() { return null; }, savePending(intent) { saved.push({ category: intent.category, input: JSON.parse(JSON.stringify(intent.input)) }); }, clearPending() {},
      async command(kind, action, selectedRef, body) {
        assert.equal(kind, 'op_type'); writes.push({ action, input: JSON.parse(JSON.stringify(body.input)) });
        if (action === 'create') entity = { ...makeEntity(kind), ...body.input, fields: body.input.fields };
        else if (action === 'update') entity = { ...entity, ...body.input, fields: { ...entity.fields, ...body.input.fields } };
        else { assert.equal(action, 'delete'); entity = null; }
        return { ok: true, result: 'committed', receipt_ref: 'op-receipt-' + writes.length, data: { entity_ref: ref }, warnings: [] };
      }
    };
    let tree, formHooks;
    const render = () => workspaceHooks.render(() => localWindow.ResourceWorkspace({ adapter: api, initialNode, onNavigationReady() {} }));
    async function settle() { for (let n = 0; n < 6; n++) { tree = render(); workspaceHooks.flush(); await turns(); } return tree; }
    const editor = () => find(tree, localWindow.ResourceForms);
    function form() { context.React = formHooks.React; const result = formHooks.render(() => localWindow.ResourceForms(editor())); formHooks.flush(); context.React = workspaceHooks.React; return result; }
    function change(name, value) { find(form(), name === 'category' ? 'select' : 'input', props => props.name === name).onChange({ target: { value } }); }
    async function submit() { await find(form(), 'form').onSubmit({ preventDefault() {}, currentTarget: { elements: [] } }); await settle(); assert.equal(editor().refreshState.done, true); assert.equal(editor().refreshState.error, undefined); }
    const anyProps = (node, matches) => { if (!node || !node.props) return null; if (matches(node.props)) return node.props; for (const child of node.props.children.flat(Infinity)) { const result = anyProps(child, matches); if (result) return result; } return null; };
    await settle();
    return { requests, details, saved, writes, editor, form, change, submit, settle,
      create: async () => { anyProps(tree, props => typeof props.onCreate === 'function').onCreate(); await settle(); formHooks = hooks(); },
      edit: async () => { find(tree, tables).onOpen(initialNode === 'supplier' ? supplierRef : ref); await settle();
        if (initialNode === 'supplier') { find(tree, localWindow.ResourceForms.Detail).onRelated('op_type', ref, 'external'); await settle(); }
        find(tree, localWindow.ResourceForms.Detail).onEdit(); await settle(); formHooks = hooks(); },
      remove: async () => { find(tree, tables).onOpen(ref); await settle(); find(tree, localWindow.ResourceForms.Detail).onDelete(); await settle(); formHooks = hooks();
        find(form(), 'input', props => props.type === 'checkbox').onChange({ target: { checked: true } }); },
      close: async () => { editor().onClose(); await settle(); }, dispose: () => { workspaceHooks.unmount(); if (formHooks) formHooks.unmount(); }
    };
  }
  for (const [node, category] of [['op_int', 'internal'], ['op_ext', 'external']]) {
    const both = await opTypeWorkspace(node);
    await both.create(); both.change('business_code', 'F01-BOTH'); both.change('label', '两用工种'); both.change('category', 'both'); await both.submit();
    assert.equal(both.saved.at(-1).category, category); assert.equal(both.saved.at(-1).input.fields.category, 'both');
    assert.equal(both.editor().refreshState.detail.data.fields.category, 'both'); await both.close();
    await both.edit(); assert.equal(both.editor().category, category, 'Entering edit preserves the source list for a both entity');
    await both.editor().onReloadContext(); await both.settle(); assert.equal(both.editor().category, category, 'Context reload preserves the source list');
    both.change('label', '已更新的两用工种'); await both.submit();
    assert.equal(both.saved.at(-1).category, category); assert.equal(both.editor().refreshState.detail.data.label, '已更新的两用工种'); await both.close();
    await both.remove(); await both.submit(); assert.equal(both.saved.at(-1).category, category); assert.equal(both.editor().refreshState.detail, null);
    assert.deepEqual(both.requests.map(request => request.category), Array(both.requests.length).fill(category));
    assert.deepEqual(both.writes.map(write => write.action), ['create', 'update', 'delete']); both.dispose();
  }
  const relatedBoth = await opTypeWorkspace('supplier', true);
  await relatedBoth.edit(); assert.equal(relatedBoth.editor().category, 'external'); relatedBoth.change('label', '供应商详情中的两用工种'); await relatedBoth.submit();
  assert.equal(relatedBoth.saved[0].category, 'external');
  assert.deepEqual(relatedBoth.requests.slice(-2).map(request => [request.kind, request.category || null]), [['op_type', 'external'], ['supplier', null]],
    'Saving a related both entity refreshes its source category and the parent list'); relatedBoth.dispose();

  {
    // A definite rejection stays rejected: a failed local cleanup is retried by reset(), never turned into a receipt lookup.
    const commandHooks = hooks(), rejectedForms = () => null, rejectedTables = () => null;
    rejectedForms.Detail = 'resource-detail'; rejectedForms.Feedback = 'resource-feedback'; rejectedTables.Pager = 'resource-pager';
    const commandWindow = { crypto: { getRandomValues: bytes => bytes.fill(2) }, addEventListener() {}, removeEventListener() {},
      ResourceControls: Object.fromEntries(['Button', 'Icon', 'ErrorBox', 'Issues', 'Modal'].map(name => [name, name.toLowerCase()])),
      ResourceForms: rejectedForms, ResourceTables: rejectedTables, ResourceRail: 'resource-rail', ResourceMetrics: 'resource-metrics',
      ResourceTableFilterModel: { rules: filters => filters }, WorkbenchPageContext: { useSnapshot() {} } };
    const commandContext = vm.createContext({ window: commandWindow, React: commandHooks.React, AbortController, DOMException });
    withTransport(commandContext); for (const name of ['resource-contract.js', 'resource-session.js', 'ResourceWorkspace.jsx']) load(commandContext, name);
    commandWindow.APSResourceSession.useCounts = () => ({ summary: { reload() {} } });
    // The resource adapter throws the transport's unified error; only a definite rejection (Q2-A) may release the intent.
    const T = commandWindow.APSWorkbenchTransport, refusal = (code, message, status) => T.failure({ ok: false, committed: false, error: { code, message, fields: [], retryable: status >= 500, request_ref: '1'.repeat(32) } }, status);
    const rejection = refusal('validation_failed', '编号重复。', 422), cleared = [], lookups = [];
    let clearFailure = new Error('上次操作记录没清掉');
    const commandAdapter = { readPending() { return null; }, savePending() {}, clearPending() { cleared.push(clearFailure ? 'failed' : 'cleared'); if (clearFailure) throw clearFailure; },
      async lookup(key) { lookups.push(key); return { ok: true, state: 'not_recorded', receipt: null, may_be_in_flight: true }; },
      async command() { throw rejection; } };
    const useRejected = () => commandHooks.render(() => commandWindow.APSResourceSession.useCommand(commandAdapter));
    useRejected(); commandHooks.flush();
    await useRejected().submit('machine', 'create', null, { write_token: 'token' }, { label: '设备' });
    const kept = useRejected();
    assert.equal(kept.phase, 'rejected', 'A failed cleanup after a definite rejection keeps the rejected state');
    assert.equal(kept.intent.action, 'create', 'The saved intent stays so reset() can retry the cleanup');
    assert.strictEqual(kept.error, clearFailure); assert.deepEqual(lookups, [], 'A rejection has no receipt to look up');
    assert.equal(kept.reset(), false); assert.equal(useRejected().phase, 'rejected'); assert.deepEqual(cleared, ['failed', 'failed']);
    commandHooks.unmount();

    // A remounted workspace shows the orphan rejection; closing it retries the cleanup.
    const workspaceHooks = hooks(); commandContext.React = workspaceHooks.React;
    const renderWorkspace = () => { const tree = workspaceHooks.render(() => commandWindow.ResourceWorkspace({ adapter: commandAdapter, initialNode: 'machine', onNavigationReady() {} })); workspaceHooks.flush(); return tree; };
    const orphan = find(renderWorkspace(), 'modal', props => props.title === '上次操作结果');
    assert(orphan && !orphan.locked, 'A rejected command without its dialog still offers a closable previous result');
    clearFailure = null; orphan.onClose(); await turns();
    assert.equal(find(renderWorkspace(), 'modal', props => props.title === '上次操作结果'), null); assert.deepEqual(cleared, ['failed', 'failed', 'cleared']);
    workspaceHooks.unmount();

    // A successful cleanup drops the saved intent, so reset() has nothing left to clear.
    const clearedHooks = hooks(); commandContext.React = clearedHooks.React;
    const useCleared = () => clearedHooks.render(() => commandWindow.APSResourceSession.useCommand(commandAdapter));
    useCleared(); clearedHooks.flush();
    await useCleared().submit('machine', 'create', null, { write_token: 'token' }, { label: '设备' });
    const dropped = useCleared();
    assert.equal(dropped.phase, 'rejected'); assert.strictEqual(dropped.intent, null, 'A cleared rejection no longer carries the saved intent');
    assert.strictEqual(dropped.error, rejection); assert.deepEqual(cleared, ['failed', 'failed', 'cleared', 'cleared']);
    assert.equal(dropped.reset(), true); assert.deepEqual(cleared, ['failed', 'failed', 'cleared', 'cleared']); assert.deepEqual(lookups, []);
    clearedHooks.unmount();

    // Editing input clears an ordinary rejection; a stale one waits for refreshed data unless a fresh preview replaces the write basis.
    const staleRejection = refusal('stale_write', '本页数据已过期。', 409);
    for (const [response, stale] of [[rejection, false], [staleRejection, true]]) {
      const editHooks = hooks(), editAdapter = { ...commandAdapter, async command() { throw response; } }; commandContext.React = editHooks.React;
      const useEdited = () => editHooks.render(() => commandWindow.APSResourceSession.useCommand(editAdapter));
      useEdited(); editHooks.flush();
      assert.equal(useEdited().clearRejection(), false, 'An idle command has no rejection to clear');
      await useEdited().submit('machine', 'create', null, { write_token: 'token' }, { label: '设备' });
      assert.equal(useEdited().phase, 'rejected'); assert.equal(useEdited().stale, stale);
      assert.equal(useEdited().clearRejection(), !stale); assert.equal(useEdited().phase, stale ? 'rejected' : 'idle');
      if (stale) { assert.equal(useEdited().clearRejection({ includeStale: true }), true); assert.equal(useEdited().phase, 'idle'); }
      editHooks.unmount();
    }
    const downtimeHooks = hooks(); commandContext.React = downtimeHooks.React;
    commandWindow.ResourceControls.Field = 'field';
    commandWindow.WorkbenchGuards = { useDirtyGuard: () => 'guard', confirmLeave: async () => true };
    load(commandContext, 'MachineDowntimePanel.jsx');
    const downtimeAdapter = { ...commandAdapter, readPending() { throw new Error('outer pending must not be read by downtime panel'); }, downtimes: async () => ({ data: { rows: [], reasons: {}, write_context: { write_token: 't', capabilities: {}, blocked_reasons: [] } } }) };
    const downtimeTree = downtimeHooks.render(() => commandWindow.MachineDowntimePanel({ adapter: downtimeAdapter, entity: { ref: '1'.repeat(48), business_code: 'M-01' }, source: 'production', onClose() {} }));
    downtimeHooks.flush();
    assert.equal(find(downtimeTree, 'modal').locked, false, 'MachineDowntimePanel overrides readPending with a null-returning function so useCommand starts idle and unlocked');
    downtimeHooks.unmount();
  }

  const modelContext = vm.createContext({ window: { WorkbenchFormat: {}, FieldContract: { quantityReasons: {}, states: {} } } });
  load(modelContext, 'PlanGanttModel.js'); load(modelContext, 'ActualGanttModel.js'); let reads = 0;
  const data = { availability: { state: 'available' }, execution_summary: { scope: 'full_response_cohort', complete: 334, pending: 333, reported: 333, average_finish_deviation_minutes: 30, known_finish_count: 334 }, items: Array.from({ length: 1000 }, (_, n) => ({ task: { end: '2026-09-09T08:00:00' },
    execution: { get execution_state() { reads++; return ['complete', 'unreported', 'partial'][n % 3]; }, confirmed_finish: '2026-09-09T08:30:00' } })) };
  assert.deepEqual(JSON.parse(JSON.stringify(modelContext.window.ActualGanttModel.metrics(data))), { complete: 334, pending: 333, reported: 333, average: 30 }); assert.equal(reads, 0, 'Actual metrics consume the shared full cohort summary without recomputing execution rows');

  {
  // Prepared Gantt facts survive local filtering, collapse and geometric width changes.
  let timeReads = 0;
  class CountingDate extends Date { static parse(value) { timeReads++; return Date.parse(value); } }
  const preparedContext = vm.createContext({ window: { WorkbenchFormat: {}, FieldContract: { quantityReasons: {}, states: {} } }, Date: CountingDate });
  for (const name of ['PointContract.js', 'PointGanttModel.js', 'GanttGraph.js', 'PlanGanttModel.js', 'ActualGanttModel.js']) load(preparedContext, name);
  const PM = preparedContext.window.PlanGanttModel, AM = preparedContext.window.ActualGanttModel, stamp = hour => '2026-10-12T' + String(hour).padStart(2, '0') + ':00:00';
  const createGraph = preparedContext.window.GanttGraph.create; let graphBuilds = 0;
  preparedContext.window.GanttGraph.create = value => { graphBuilds++; return createGraph(value); };
  const task = (id, start, end) => ({ task_ref: id, operation_ref: 'op-' + id, batch_id: id, process_label: id, sequence: 1, piece_id: null,
    machine_ref: 'machine', operator_ref: null, start: stamp(start), end: stamp(end) });
  const firstTask = task('first', 8, 10), secondTask = task('second', 9, 11), resources = [{ ref: 'machine', label: '设备' }];
  const sharedData = { tasks: [firstTask, secondTask], resources, plan_span: { start: stamp(8), end: stamp(12) },
    projections: { calendar: { resources: [] }, occupancy: { resources: [] }, baseline: { state: 'unavailable' } } };
  const sharedFacts = PM.prepare(sharedData);
  assert.equal(graphBuilds, 0, 'Shared task, time and mark preparation does not require or build a process graph');
  assert.equal(sharedFacts.taskIndex.get('first').start, PM.instant(firstTask.start));
  const planFacts = sharedFacts;
  const preparedTimes = timeReads, planGroup = PM.groupPrepared(planFacts, 'machine');
  const selectedPlan = PM.selectPrepared(planGroup, 'second'), narrowPlan = PM.layoutPrepared(selectedPlan, 640), widePlan = PM.layoutPrepared(selectedPlan, 2000);
  PM.selectPrepared(planGroup, 'first'); PM.groupPrepared(planFacts, 'operator');
  assert.equal(timeReads, preparedTimes, 'Plan local filters, resource grouping and width reuse parsed time facts');
  assert.equal(narrowPlan.tasks.length, 1); assert.equal(narrowPlan.rows[0].tasks.length, 1);
  assert.strictEqual(narrowPlan.locations.get('second').item, widePlan.locations.get('second').item);
  assert.equal(graphBuilds, 0); assert.strictEqual(selectedPlan.taskIndex, planFacts.taskIndex);
  const execution = reports => ({ execution_state: 'complete', reports, data_gaps: [], remaining_quantity: 0, remaining_plan: null });
  const report = (id, start, end, hours) => ({ report_ref: id, report_no: id, actual_start: stamp(start), actual_end: stamp(end),
    actual_machine_ref: 'machine', actual_operator_ref: null, effective_processing_hours: hours });
  const actualData = { resources, gantt_graph: unavailableGraph(), axis_span: { start: stamp(8), end: stamp(12) }, availability: { state: 'available' }, items: [
    { task: firstTask, deviation: { finish_late: true }, execution: execution([report('known', 8, 10, 2), report('unknown', 9, 11, null)]) },
    { task: secondTask, deviation: { finish_late: false }, execution: execution([report('other', 10, 11, 1)]) }
  ] };
  const actualFacts = AM.prepare(actualData, stamp(12)), actualTimes = timeReads, actualGroup = AM.groupPrepared(actualFacts, 'machine');
  const fullView = { query: '', late: 'all', onlySelected: false, selected: null, collapsed: {} };
  const allSelected = AM.selectPrepared(actualGroup, fullView), firstSelected = AM.selectPrepared(actualGroup, { ...fullView, query: 'first' });
  assert.equal(graphBuilds, 0); assert.strictEqual(firstSelected.taskIndex, actualFacts.taskIndex);
  const allActual = AM.layoutPrepared(allSelected, {}), firstActual = AM.layoutPrepared(firstSelected, {});
  assert.deepEqual([allActual.groups[0].reportCount, allActual.groups[0].knownHours, allActual.groups[0].unknownHours], [3, 3, 1]);
  assert.deepEqual([firstActual.groups[0].reportCount, firstActual.groups[0].knownHours, firstActual.groups[0].unknownHours], [2, 2, 1]);
  const firstRow = firstActual.rows.find(row => row.kind === 'actual');
  assert.strictEqual(firstRow.marks, allActual.rows.find(row => row.key === firstRow.key).marks, 'Visible layouts share prepared marks');
  const collapsedActual = AM.layoutPrepared(allSelected, { machine: true });
  assert.equal(collapsedActual.locations.size, 0); assert.equal(AM.graphLocations(collapsedActual).size, 0);
  assert.equal(AM.graphLocations(firstActual).get('first').reported, true); assert.equal(timeReads, actualTimes);

  load(preparedContext, 'ActualGanttWindow.js');
  const actualWindow = preparedContext.window.ActualGanttWindow;
  const initialActual = actualWindow.initial(allActual); assert(Number.isFinite(initialActual.zoom));
  assert.equal(actualWindow.anchor(allActual, 'first', 'known'), ((actualFacts.facts[0].reports[0].start + actualFacts.facts[0].reports[0].end) / 2 - allActual.start) / (allActual.end - allActual.start));
  actualWindow.anchor(firstActual, null, null); assert.equal(timeReads, actualTimes, 'Default windows and zoom anchors reuse the model time facts');

  // Candidate and baseline search share their fixed facts, including hide/show of the same baseline.
  preparedContext.window.WorkbenchTerms = {};
  load(preparedContext, 'RunCandidateModel.js'); load(preparedContext, 'RunBaselineModel.js');
  const CM = preparedContext.window.RunCandidateModel, BM = preparedContext.window.RunBaselineModel;
  const candidateTasks = [firstTask, secondTask].map(value => ({ ...value, row_ref: value.task_ref, batch_ref: value.batch_id,
    batch_label: value.batch_id, machine: { ref: 'machine', label: '设备' }, operator: null, data_gaps: [] }));
  const candidateFacts = CM.prepare({ tasks: candidateTasks, unplanned_operations: [], gantt_graph: { ...unavailableGraph(), scope: 'full_candidate' }, task_span: { start: stamp(8), end: stamp(12) } });
  const baselineFacts = BM.prepare({ comparisons: [{ ...candidateTasks[0], baseline_segments: [{ ...candidateTasks[0], row_ref: 'baseline-first', interval_comparable: true, start: stamp(7), end: stamp(9) }] }] });
  const candidateTimes = timeReads, candidateGroups = CM.groupPrepared(candidateFacts, 'machine'), baselineGroups = BM.groupPrepared(baselineFacts, 'machine');
  const selectedCandidate = CM.selectPrepared(candidateGroups, 'first', null, null), withBaseline = BM.selectPrepared(selectedCandidate, baselineGroups, 'first', null, true);
  assert.equal(graphBuilds, 0); assert.strictEqual(selectedCandidate.taskIndex, candidateFacts.taskIndex);
  const narrowCandidate = BM.layoutPrepared(withBaseline, 640), wideCandidate = BM.layoutPrepared(withBaseline, 2000);
  assert.strictEqual(narrowCandidate.locations.get('first').item, wideCandidate.locations.get('first').item);
  CM.matching(candidateFacts, 'second', null); CM.selectPrepared(candidateGroups, 'second', null, null);
  const hiddenBaseline = BM.layoutPrepared(BM.selectPrepared(selectedCandidate, baselineGroups, 'first', null, false), 640);
  assert.equal(hiddenBaseline.baselineLocations.size, 0); assert.equal(BM.layoutPrepared(withBaseline, 640).baselineLocations.size, 1);
  assert.equal(timeReads, candidateTimes, 'Candidate filters, baseline hide/show and width consume the same parsed facts');

  // Canvas listeners belong to the mount; redraws reuse the buffer and consume the latest paint.
  const paintHooks = hooks(), paintFrames = new Map(), paintEvents = new Map(); let frameId = 0, themes = 0, resizes = 0, disconnects = 0, buffers = 0, paints = [];
  let canvasWidth = 100, pixelRatio = 1, paintVersion = 1, dependency = 1, paintPrinting = false, visualScale = 1, canvasBufferWidth = 0, canvasBufferHeight = 0;
  const paintCanvas = { get clientWidth() { return canvasWidth; }, clientHeight: 20, getBoundingClientRect: () => ({ width: canvasWidth * visualScale, height: 20 * visualScale }), getContext: () => ({ setTransform() {}, clearRect() {} }),
    get width() { return canvasBufferWidth; }, set width(value) { buffers++; canvasBufferWidth = value; },
    get height() { return canvasBufferHeight; }, set height(value) { buffers++; canvasBufferHeight = value; } };
  const paintWindow = { get devicePixelRatio() { return pixelRatio; }, addEventListener(name, fn) { paintEvents.set(name, fn); }, removeEventListener(name) { paintEvents.delete(name); },
    matchMedia: () => ({ addEventListener() {}, removeEventListener() {} }) };
  const paintContext = vm.createContext({ window: paintWindow, React: paintHooks.React, document: { documentElement: {} },
    MutationObserver: class { constructor(fn) { themes++; this.update = fn; } observe() {} disconnect() { disconnects++; } },
    ResizeObserver: class { constructor(fn) { resizes++; this.update = fn; } observe() {} disconnect() { disconnects++; } },
    requestAnimationFrame(fn) { const id = ++frameId; paintFrames.set(id, fn); return id; }, cancelAnimationFrame(id) { paintFrames.delete(id); } });
  load(paintContext, 'GanttPresentation.js'); const paintRef = { current: paintCanvas }, palette = () => ({});
  const renderPaint = () => paintHooks.render(() => paintWindow.GanttPresentation.useCanvasPaint(paintRef, () => paints.push(paintVersion), palette, [dependency], paintPrinting));
  const drawFrames = () => { const queued = Array.from(paintFrames.values()); paintFrames.clear(); queued.forEach(fn => fn()); };
  renderPaint(); paintHooks.flush(); assert.equal(paintFrames.size, 1); drawFrames(); assert.equal(buffers, 2);
  paintVersion = 2; renderPaint(); paintHooks.flush(); assert.equal(paintFrames.size, 0, 'Hover-only renders do not request a canvas repaint');
  dependency = 2; renderPaint(); paintHooks.flush(); dependency = 3; paintVersion = 3; renderPaint(); paintHooks.flush();
  assert.equal(paintFrames.size, 1); drawFrames(); assert.equal(paints.at(-1), 3); assert.equal(buffers, 2); assert.deepEqual([themes, resizes], [1, 1]);
  canvasWidth = 120; pixelRatio = 2; paintEvents.get('resize')(); drawFrames(); assert.equal(canvasBufferWidth, 240); assert.equal(canvasBufferHeight, 40);
  dependency = 4; paintVersion = 4; renderPaint(); paintHooks.flush(); assert.equal(paintFrames.size, 1);
  paintPrinting = true; visualScale = .5; paintVersion = 5; renderPaint(); paintHooks.flush();
  assert.equal(paints.at(-1), 5, 'The beforeprint flushSync update paints its print content before returning');
  assert.equal(paintFrames.size, 0, 'Print painting cancels the pending screen frame');
  assert.equal(canvasBufferWidth, 240); assert.equal(canvasBufferHeight, 40, 'Print pagination scale cannot halve the layout-sized drawing buffer');
  paintHooks.unmount(); assert.equal(disconnects, 2); assert.equal(paintEvents.size, 0);
  const printMountHooks = hooks(); paintContext.React = printMountHooks.React; const beforePrintMount = paints.length;
  printMountHooks.render(() => paintWindow.GanttPresentation.useCanvasPaint(paintRef, () => paints.push('new-print-row'), palette, [], true)); printMountHooks.flush();
  assert.equal(paints.length, beforePrintMount + 1, 'A row newly mounted by the print layout is painted in its layout effect');
  assert.equal(paints.at(-1), 'new-print-row'); assert.equal(paintFrames.size, 0); printMountHooks.unmount();

  // The handler hint reads on mount, then consumes the actual local write result.
  const hintHooks = hooks(); let hintReads = 0, savedHandler = '甲', failHandlerWrite = false;
  const hintWindow = { localStorage: { getItem() { hintReads++; return savedHandler; }, setItem(_, value) { if (failHandlerWrite) throw Error('disk'); savedHandler = value; } }, addEventListener() {}, removeEventListener() {} };
  const hintContext = vm.createContext({ window: hintWindow, React: hintHooks.React }); load(hintContext, 'WorkbenchHandlerMemory.js');
  const hintMemory = hintWindow.WorkbenchHandlerMemory, renderHint = value => hintHooks.render(() => hintMemory.useHint(value));
  assert(renderHint('甲').includes('预填')); hintHooks.flush(); assert.equal(renderHint('乙'), ''); assert.equal(hintReads, 1);
  assert.equal(hintMemory.write('乙').saved, true); assert(renderHint('乙').includes('预填')); assert.equal(hintReads, 1);
  failHandlerWrite = true; assert.equal(hintMemory.write('丙').saved, false); assert(renderHint('丙').includes('无法写入')); assert.equal(hintReads, 1); hintHooks.unmount();

  }

  {
  // Column typing stays local until Enter or the existing search button submits it.
  const filterHooks = hooks(), facetRequests = [], filterModel = { rule: () => ({ mode: 'exclude', values: [] }), signature: JSON.stringify,
    toolbarScope: () => ({}), facets: value => value, selection: value => value, groupState: () => ({ all: false, mixed: false }) };
  const facetResponse = () => ({ meta: { snapshot_ref: 'facet' }, warnings: [], data: { options: [], page: { number: 1, pages: 1, total: 0 } } });
  const filterAdapter = { async facets(_, query) { facetRequests.push(query); return facetResponse(); }, async facetSelection() { return { warnings: [], data: { keys: [] } }; } };
  const filterWindow = { ResourceTableFilterModel: filterModel, APSResourceContract: { failure: message => Error(message) }, ResourceControls: { Button: 'button', ErrorBox: 'error' } };
  const filterContext = vm.createContext({ window: filterWindow, React: { ...filterHooks.React, useLayoutEffect() {} }, ReactDOM: { createPortal: tree => tree }, document: { body: {} }, AbortController });
  load(filterContext, 'ResourceTableFilter.jsx');
  const filterProps = { column: { key: 'label', title: '名称' }, kind: 'machine', scope: {}, adapter: filterAdapter, owner: { closest: () => null }, onFilter() {}, onClose() {} };
  const renderFilter = () => filterHooks.render(() => filterWindow.ResourceTableFilter(filterProps));
  let filterTree = renderFilter(); filterHooks.flush(); await turns(); filterTree = renderFilter();
  assert.equal(facetRequests.length, 1);
  find(filterTree, 'input', props => props['aria-label'] === '搜索名称列值').onChange({ target: { value: '待提交' } });
  filterTree = renderFilter(); filterHooks.flush(); await turns(); assert.equal(facetRequests.length, 1);
  for (const composition of [{ isComposing: true }, { keyCode: 229 }, { nativeEvent: { isComposing: true } }, { nativeEvent: { keyCode: 229 } }]) {
    find(filterTree, 'input', props => props['aria-label'] === '搜索名称列值').onKeyDown({ key: 'Enter', ...composition,
      preventDefault() { assert.fail('IME confirmation keeps its default input behavior'); }, stopPropagation() { assert.fail('IME confirmation is not intercepted as search submission'); } });
    filterTree = renderFilter(); filterHooks.flush(); await turns(); assert.equal(facetRequests.length, 1, 'IME confirmation does not submit the unconfirmed query');
  }
  find(filterTree, 'input', props => props['aria-label'] === '搜索名称列值').onKeyDown({ key: 'Enter', preventDefault() {}, stopPropagation() {} });
  filterTree = renderFilter(); filterHooks.flush(); await turns(); filterTree = renderFilter();
  assert.equal(facetRequests.length, 2); assert.equal(facetRequests.at(-1).query, '待提交');
  find(filterTree, 'input', props => props['aria-label'] === '搜索名称列值').onChange({ target: { value: '按钮提交' } }); filterTree = renderFilter();
  find(filterTree, 'button', props => props['aria-label'] === '搜索列值').onClick(); renderFilter(); filterHooks.flush(); await turns();
  assert.equal(facetRequests.length, 3); assert.equal(facetRequests.at(-1).query, '按钮提交'); filterHooks.unmount();

  // New operation types read the saved entity only; the create context was already loaded.
  const createHooks = hooks(); let savedDetails = 0, savedLists = 0, committed = 0;
  const createCommand = { phase: 'done', locked: false, reset: () => true, intent: { kind: 'op_type', action: 'create' }, result: { result: 'committed', receipt_ref: 'created' } };
  const createWindow = { APSResourceContract: { query: value => value, resultRef: () => 'new-type', failure: message => Error(message) },
    APSResourceSession: { useCommand: () => createCommand, useQuery: () => ({ result: { data: { create_context: {} }, meta: {} } }) },
    ResourceControls: { Button: 'button', Modal: 'modal', ErrorBox: 'error' }, ResourceForms: 'resource-form' };
  const createContext = vm.createContext({ window: createWindow, React: createHooks.React, AbortController }); load(createContext, 'ProcessOpTypeCreate.jsx');
  const createProps = { adapter: { async detail() { savedDetails++; return { data: { ref: 'new-type' } }; }, async list() { savedLists++; } }, onClose() {}, onCommitted() { committed++; } };
  const renderCreate = () => createHooks.render(() => createWindow.ProcessOpTypeCreate(createProps));
  renderCreate(); createHooks.flush(); renderCreate(); createHooks.flush(); await turns();
  const created = renderCreate(); assert.equal(created.props.refreshState.done, true); assert.deepEqual([savedDetails, savedLists, committed], [1, 0, 1]); createHooks.unmount();
  }

  {
  // Actual read failures retain the existing range form and its selected resource.
  const actualHooks = hooks(), rangeHooks = hooks(), actualReads = [], actualPlan = '4'.repeat(48), actualResource = '5'.repeat(48), otherResource = '6'.repeat(48);
  let actualGraphBuilds = 0;
  const actualFailure = Object.assign(Error('现场实际甘特数据超过读取容量，请缩小范围。'), { code: 'query_too_large', status: 413 });
  const actualWindow = { APSResourceContract: { failure: message => Error(message) }, FieldContract: { quantityReasons: {}, states: {}, date: String },
    ResourceControls: { Button: 'button', ErrorBox: 'error', Modal: 'modal' }, ActualGanttAPI: {},
    WorkbenchTerms: { current_official: '当前正式计划', data_as_of: String, plan_version: String }, WorkbenchPageContext: { useSnapshot() {} }, WorkbenchCaption: { useCaption() {} },
    WorkbenchControls: { EmptyState: 'empty' }, GanttPresentation: { axis: () => ({ ticks: [] }) }, GanttPresentationUI: { Axis: 'axis' },
    GanttGraph: { create: () => { actualGraphBuilds++; return {}; }, selection: () => ({ critical: new Set(), related: new Set() }), locationIndex: () => ({}), paths: () => ({}) },
    GanttGraphLayer: { Controls: 'graph-controls', Lines: 'graph-lines' }, ActualGanttRows: 'actual-rows' };
  const actualContext = vm.createContext({ window: actualWindow, React: actualHooks.React, AbortController, cancelAnimationFrame() {} });
  for (const name of ['WorkbenchFormat.js', 'PointContract.js', 'PointGanttModel.js', 'PlanGanttModel.js', 'ActualGanttModel.js', 'ActualGanttWindow.js', 'ActualGanttContract.js', 'ActualGanttControls.jsx']) load(actualContext, name);
  load(actualContext, 'ActualGanttWorkspace.jsx', source('ActualGanttWorkspace.jsx').replace('window.ActualGanttWorkspace = ActualGanttWorkspace;', 'window.ActualGanttSession = Content;'));
  // Workspace-ownership check: ActualGanttAPI's own validation is covered by the actual Gantt contracts; the workspace hands it the scope state.
  const actualProps = { initialContext: { plan_ref: actualPlan, scope: { resource_type: 'machine', resource_ref: actualResource, batch_ids: ['OLD'] } } };
  actualWindow.ActualGanttAPI.load = async input => {
      actualReads.push(JSON.parse(JSON.stringify(input)));
      if (!input.plan_finish_date_from) throw actualFailure;
      return { meta: { as_of: '2026-10-12T12:00:00', snapshot_ref: 'actual-range' }, data: { scope: input,
        plan: { plan_ref: actualPlan, display_name: '正式计划', kind: 'official', is_current_official: true, version: 1 },
        resources: [{ ref: otherResource, kind: 'machine', label: 'M1' }, ...(input.batch_ids.includes('ONLY-M1') ? [] : [{ ref: actualResource, kind: 'machine', label: 'M2' }])], items: [], task_count: 0,
        availability: { state: 'available' }, axis_span: { start: '2026-10-12T08:00:00', end: '2026-10-12T16:00:00' },
        execution_summary: { complete: 0, reported: 0, pending: 0, average_finish_deviation_minutes: null }, gantt_graph: {} } };
  };
  let actualTree, rangeTree;
  const renderActual = async () => {
    for (let index = 0; index < 4; index++) {
      actualContext.React = actualHooks.React;
      actualTree = actualHooks.render(() => actualWindow.ActualGanttSession(actualProps)); actualHooks.flush(); await turns();
    }
    const props = find(actualTree, actualWindow.ActualGanttControls.Range);
    assert(props, 'A selected plan keeps its range form after the first read fails');
    actualContext.React = rangeHooks.React;
    rangeTree = rangeHooks.render(() => actualWindow.ActualGanttControls.Range(props)); rangeHooks.flush();
  };
  await renderActual(); assert.equal(actualReads.length, 1); assert.equal(actualGraphBuilds, 0);
  assert.strictEqual(find(actualTree, 'error').error, actualFailure); assert.equal(find(actualTree, 'actual-rows'), null);
  let resourceSelect = find(rangeTree, 'select');
  assert.equal(resourceSelect.disabled, true); assert.equal(resourceSelect.value, actualResource);
  assert.equal(find(rangeTree, 'option').value, actualResource);
  assert(find(rangeTree, 'option').children.join('').includes('已选资源'));
  find(rangeTree, 'input', props => props['aria-label'] === '计划完工开始日').onChange({ target: { value: '2026-10-12' } });
  find(rangeTree, 'input', props => props['aria-label'] === '计划完工结束日').onChange({ target: { value: '2026-10-13' } });
  find(rangeTree, 'input', props => props['aria-label'] === '批次范围').onChange({ target: { value: 'B1，B2' } });
  await renderActual(); assert.equal(actualReads.length, 1, 'Editing dates and batches does not read or retry');
  find(rangeTree, 'form').onSubmit({ preventDefault() {} }); await renderActual();
  assert.equal(actualReads.length, 2, 'Applying the manual scope performs one new read'); assert.equal(actualGraphBuilds, 1);
  assert.deepEqual(actualReads[1], { plan_ref: actualPlan, resource_type: 'machine', resource_ref: actualResource,
    batch_ids: ['B1', 'B2'], plan_finish_date_from: '2026-10-12', plan_finish_date_to: '2026-10-13' });
  assert.equal(find(actualTree, 'error').error, null); assert(find(actualTree, 'actual-rows'));
  resourceSelect = find(rangeTree, 'select'); assert.equal(resourceSelect.disabled, false); assert.equal(resourceSelect.value, actualResource);
  find(rangeTree, 'input', props => props['aria-label'] === '计划完工开始日').onChange({ target: { value: '2026-10-13' } });
  find(rangeTree, 'input', props => props['aria-label'] === '计划完工结束日').onChange({ target: { value: '2026-10-14' } });
  find(rangeTree, 'input', props => props['aria-label'] === '批次范围').onChange({ target: { value: 'ONLY-M1' } });
  await renderActual(); assert.equal(actualReads.length, 2);
  find(rangeTree, 'form').onSubmit({ preventDefault() {} }); await renderActual(); assert.equal(actualReads.length, 3); assert.equal(actualGraphBuilds, 2);
  const narrowedResources = find(actualTree, actualWindow.ActualGanttControls.Range).resources;
  assert.deepEqual(Array.from(narrowedResources, row => row.ref), [otherResource]);
  resourceSelect = find(rangeTree, 'select'); assert.equal(resourceSelect.disabled, false); assert.equal(resourceSelect.value, actualResource);
  const selectedOption = find(rangeTree, 'option', props => props.value === resourceSelect.value);
  assert(selectedOption, 'A resource absent from a successful narrowed result remains a real selected option');
  assert.equal(selectedOption.children.join(''), '已选资源（当前范围无记录）');
  find(rangeTree, 'form').onSubmit({ preventDefault() {} }); await renderActual(); assert.equal(actualReads.length, 4); assert.equal(actualGraphBuilds, 3);
  assert.deepEqual(actualReads[3], { plan_ref: actualPlan, resource_type: 'machine', resource_ref: actualResource,
    batch_ids: ['ONLY-M1'], plan_finish_date_from: '2026-10-13', plan_finish_date_to: '2026-10-14' });
  actualHooks.unmount(); rangeHooks.unmount();

  // Field navigation carries a locator only when the current cohort and field query can contain it.
  let navigationHooks = hooks(); const navigationEvents = [], navigationSnapshots = [], selectedRef = '7'.repeat(48);
  const plannedOperator = '9'.repeat(48), reportedMachine = 'a'.repeat(48), reportedOperator = 'b'.repeat(48);
  actualWindow.WorkbenchPageContext.useSnapshot = value => { if (value) navigationSnapshots.push(value); };
  const navigationTask = { task_ref: selectedRef, operation_ref: '8'.repeat(48), batch_id: 'B1', sequence: 10, process_label: '加工', piece_id: 27,
    start: '2026-10-12T08:00:00', end: '2026-10-12T10:00:00', machine_ref: actualResource, operator_ref: plannedOperator, quantity: 10, batch_quantity: 10 };
  const navigationItem = { task: navigationTask, deviation: { complete: false, finish_late: false, unclosed: false, forecast_late: false },
    execution: { execution_state: 'partial', known_completed_quantity: 0, remaining_quantity: 10, confirmed_finish: null, data_gaps: [],
      reports: [{ report_ref: 'e'.repeat(48), report_no: 'RG-SEARCH-42', actual_start: navigationTask.start, actual_end: navigationTask.end,
        actual_machine_ref: reportedMachine, actual_operator_ref: reportedOperator, effective_processing_hours: 1 }],
      remaining_plan: { start: '2026-10-12T12:00:00', end: '2026-10-12T14:00:00', machine_ref: otherResource, operator_ref: null } } };
  actualWindow.ActualGanttAPI.load = async input => ({ meta: { as_of: '2026-10-12T12:00:00', snapshot_ref: 'navigation-snapshot' }, data: {
      scope: input, plan: { plan_ref: actualPlan, display_name: '正式计划', kind: 'official', is_current_official: true, version: 1 },
      resources: [{ ref: actualResource, label: '当前设备' }, { ref: plannedOperator, label: '计划人员' }, { ref: otherResource, label: '剩余设备专名' },
        { ref: reportedMachine, label: '实报设备' }, { ref: reportedOperator, label: '实报人员' }],
      items: input.batch_ids.includes('NONE') ? [] : [navigationItem], task_count: input.batch_ids.includes('NONE') ? 0 : 1, availability: { state: 'available' },
      axis_span: { start: navigationTask.start, end: '2026-10-12T16:00:00' }, execution_summary: { complete: 0, reported: 1, pending: 0, average_finish_deviation_minutes: null }, gantt_graph: {} } });
  const navigationProps = { initialContext: { plan_ref: actualPlan, task_ref: selectedRef, scope: { batch_ids: [], plan_finish_date_from: '2026-10-12', plan_finish_date_to: '2026-10-13' } },
    onNavigate: (target, context) => navigationEvents.push({ target, context }) };
  const renderNavigation = async () => {
    let tree;
    for (let index = 0; index < 4; index++) {
      actualContext.React = navigationHooks.React;
      tree = navigationHooks.render(() => actualWindow.ActualGanttSession(navigationProps)); navigationHooks.flush(); await turns();
    }
    return tree;
  };
  let navigationTree = await renderNavigation();
  const goField = () => { find(navigationTree, 'button', props => props.children.includes('现场记录')).onClick(); return navigationEvents.at(-1).context; };
  let fieldTarget = goField(); assert.equal(fieldTarget.task_ref, selectedRef); assert.equal(fieldTarget.operation_ref, navigationTask.operation_ref);
  assert.equal(fieldTarget.scope.batch_ids, undefined); assert.deepEqual(Array.from(fieldTarget.return_to.context.scope.batch_ids), []);
  find(navigationTree, actualWindow.ActualGanttControls.Toolbar).patch({ late: 'finishLate' }); navigationTree = await renderNavigation();
  assert.equal(find(navigationTree, 'actual-rows').model.items.length, 0); assert.equal(goField().task_ref, selectedRef,
    'A local late-only filter is not sent to field and must not discard a valid locator');
  find(navigationTree, actualWindow.ActualGanttControls.Toolbar).patch({ query: '剩余设备专名', late: 'all' }); navigationTree = await renderNavigation();
  assert.equal(find(navigationTree, 'actual-rows').model.items.length, 1);
  fieldTarget = goField();
  assert.equal(Object.prototype.hasOwnProperty.call(fieldTarget, 'task_ref'), false); assert.equal(Object.prototype.hasOwnProperty.call(fieldTarget, 'operation_ref'), false);
  assert.equal(fieldTarget.scope.query, '剩余设备专名'); assert.equal(fieldTarget.return_to.context.task_ref, selectedRef);
  for (const query of [' B1 ', '10', '加工', '27', '当前设备', '计划人员', '实报设备', '实报人员', ' rg-search-42 ']) {
    find(navigationTree, actualWindow.ActualGanttControls.Toolbar).patch({ query }); navigationTree = await renderNavigation();
    assert.equal(find(navigationTree, 'actual-rows').model.items.length, 1, query + ' matches the selected task');
    fieldTarget = goField();
    assert.equal(fieldTarget.task_ref, selectedRef, query + ' preserves the task locator');
    assert.equal(fieldTarget.operation_ref, navigationTask.operation_ref, query + ' preserves the operation locator');
    assert.equal(fieldTarget.scope.query, query);
  }
  find(navigationTree, actualWindow.ActualGanttControls.Range).onApply({ plan_ref: actualPlan, batch_ids: ['NONE'],
    plan_finish_date_from: '2026-10-13', plan_finish_date_to: '2026-10-14' }); navigationTree = await renderNavigation();
  fieldTarget = goField(); assert.equal(Object.prototype.hasOwnProperty.call(fieldTarget, 'task_ref'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(fieldTarget, 'operation_ref'), false);
  assert.equal(fieldTarget.return_to.context.task_ref, selectedRef); assert.equal(fieldTarget.scope.plan_finish_date_from, '2026-10-13');
  navigationHooks.unmount(); navigationHooks = hooks();
  navigationProps.initialContext = fieldTarget.return_to.context;
  load(actualContext, 'ActualGanttWorkspace.jsx', source('ActualGanttWorkspace.jsx').replace('window.ActualGanttWorkspace = ActualGanttWorkspace;', 'window.ActualGanttSession = Content;'));
  navigationTree = await renderNavigation();
  assert.equal(navigationSnapshots.at(-1).task_ref, selectedRef, 'A page reload drops the session cache but preserves the original return selection');
  assert.equal(goField().return_to.context.task_ref, selectedRef); navigationHooks.unmount();
  }

  // R19's actual parent retains overview facts while print/fit unmount the child.
  const overviewParentHooks = hooks(), overviewThemes = [], overviewResizes = [], fills = [], pointXs = [], planWidths = [], overviewSteps = [];
  let overviewHooks = null, cssWidth = 200.2, cssHeight = 16, binBuilds = 0, overviewTimeReads = 0, printChange, primary = 'light', printing = false;
  const overviewCtx = { clearRect() {}, setTransform() {}, fillRect(...args) { fills.push({ args, color: this.fillStyle }); }, strokeRect() {} };
  const canvas = { get clientWidth() { return Math.round(cssWidth); }, get clientHeight() { return Math.round(cssHeight); }, getBoundingClientRect: () => ({ width: cssWidth, height: cssHeight }), getContext: () => overviewCtx };
  const overviewWindow = { addEventListener() {}, removeEventListener() {}, devicePixelRatio: 1, PointContract: { isPoint: task => task.event_kind === 'point' }, PointGanttModel: { paint: (_, x) => pointXs.push(x) },
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
  const overviewPalette = overviewWindow.GanttPresentation.palette; load(overviewContext, 'GanttPresentation.js'); overviewWindow.GanttPresentation.palette = overviewPalette;
  load(overviewContext, 'PlanGanttCanvas.jsx');
  const overviewTasks = [{ start: '2026-10-12T08:00:00', end: '2026-10-12T09:00:00' },
    { start: '2026-10-12T08:30:00', end: '2026-10-12T09:30:00' },
    { start: '2026-10-12T10:00:00', end: '2026-10-12T10:00:00', event_kind: 'point' }];
  const planStart = overviewInstant(overviewTasks[0].start), planEnd = overviewInstant(overviewTasks[2].end);
  const planBoard = { scrollLeft: 0, scrollTop: 0, clientWidth: 1000, clientHeight: 440 };
  Object.assign(overviewWindow.PlanGanttModel, { prepare: () => ({ items: overviewTasks.map(task => ({ task, point: overviewWindow.PointContract.isPoint(task), start: overviewInstant(task.start), end: overviewInstant(task.end) })) }), groupPrepared: value => value, selectPrepared: value => value, layoutPrepared(_, width) { planWidths.push(width); return { start: planStart, end: planEnd, rows: [], tasks: [],
    groupCount: 0, height: 0, locations: new Map(), baselineLocations: new Map(), conflicts: new Set(), labels: {}, shownRefs: new Set(), taskOrder: new Map() }; }, visibleRows: rows => rows });
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
    const tree = overviewParentHooks.render(() => {
      const prepared = overviewParentHooks.React.useMemo(() => {
        const facts = overviewWindow.PlanGanttModel.prepare(overviewParentData); facts.graph = overviewWindow.GanttGraph.create(overviewParentData.gantt_graph); return facts;
      }, [overviewParentData]);
      return overviewWindow.PlanGantt({ data: overviewParentData, prepared, asOf: planAsOf, selected: null, onSelect() {}, query: '', onQuery() {} });
    });
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
  assert.equal(binBuilds, 1); assert.equal(overviewTimeReads, 0); assert.equal(pointXs.at(-1), canvas.clientWidth);
  overviewSteps.push({ phase: 'first_display', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  planBoard.scrollLeft += 20; find(overviewParentTree, 'div', props => props.className === 'plan-board').onScroll();
  overviewParentTree = planRender(); primary = 'dark'; overviewThemes.at(-1).draw(); printChange();
  assert.equal(overviewProps.left, planBoard.scrollLeft);
  overviewWindow.devicePixelRatio = 2; printChange(); find(overviewParentTree, 'plan-zoom').onZoom(4); overviewParentTree = planRender();
  assert.equal(binBuilds, 1); assert.equal(overviewTimeReads, 0); assert.equal(fills.at(-1).color, 'dark');
  printing = true; overviewParentTree = planRender(); assert.equal(overviewProps, null); assert.equal(overviewHooks, null); assert.equal(planWidths.at(-1), 640);
  printing = false; overviewParentTree = planRender(); assert.strictEqual(overviewProps.cache, parentOverviewCache);
  assert.equal(overviewMounts, 2); assert.deepEqual({ date_reads: overviewTimeReads, histogram_builds: binBuilds }, { date_reads: 0, histogram_builds: 1 },
    'A freshly mounted Overview after print reuses the parent-owned date facts and histogram');
  overviewSteps.push({ phase: 'after_print_remount', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  find(overviewParentTree, 'plan-zoom').onFit(); overviewParentTree = planRender(); assert.equal(overviewHooks, null);
  find(overviewParentTree, 'plan-zoom').onZoom(2); overviewParentTree = planRender(); assert.strictEqual(overviewProps.cache, parentOverviewCache);
  assert.equal(overviewMounts, 3); assert.equal(overviewTimeReads, 0); assert.equal(binBuilds, 1);
  overviewSteps.push({ phase: 'after_fit_remount', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  cssWidth = 200.8; overviewResizes.at(-1).draw(); assert.equal(binBuilds, 2); assert.equal(overviewTimeReads, 0); assert.equal(pointXs.at(-1), canvas.clientWidth);
  cssHeight = 24; overviewResizes.at(-1).draw(); assert.equal(binBuilds, 2);
  overviewSteps.push({ phase: 'after_actual_css_resize', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  printing = true; planRender(); overviewParentData = { ...overviewParentData, tasks: overviewTasks.slice() }; planRender();
  assert.equal(overviewTimeReads, 0, 'Overview consumes the data preparation even while hidden');
  overviewSteps.push({ phase: 'hidden_new_tasks', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  printing = false; planRender(); assert.equal(overviewMounts, 4); assert.equal(overviewTimeReads, 0); assert.equal(binBuilds, 3);
  overviewSteps.push({ phase: 'display_new_tasks', date_reads: overviewTimeReads, histogram_builds: binBuilds });
  overviewHooks.unmount(); overviewHooks = null; overviewParentHooks.unmount();

  // Conflict membership is prepared only for the displayed page, in original task order.
  const conflictHooks = hooks(); let conflictSegmentReads = 0, conflictMemberChecks = 0;
  const conflictWindow = { ResourceControls: { Button: 'button', Issues: 'issues', ErrorBox: 'error' }, WorkbenchTerms: { delivery_risks: {} },
    WorkbenchFormat: { dateTime: String, compactRange: (start, end) => start + ' / ' + end },
    WorkbenchControls: { Pager: 'pager', EmptyState: 'empty' }, PointContract: { isPoint: task => task.start === task.end } };
  const conflictContext = vm.createContext({ window: conflictWindow, React: conflictHooks.React });
  load(conflictContext, 'PlanGanttModel.js'); load(conflictContext, 'PlanDetailsUI.jsx');
  const conflictTask = (id, start, end, machine = 'machine') => ({ task_ref: id, batch_id: id, process_label: id, sequence: 1,
    machine_ref: machine, operator_ref: null, start: '2026-10-12T' + start, end: '2026-10-12T' + end });
  const conflictTasks = [conflictTask('late-source-first', '08:50:00', '09:02:00'), conflictTask('ends-at-start', '08:00:00', '08:30:00.125'),
    conflictTask('starts-at-end', '09:00:00.500', '09:30:00'), conflictTask('early-source-later', '08:00:00', '09:05:00'),
    conflictTask('point-inside', '08:45:00', '08:45:00'), conflictTask('other-resource', '08:00:00', '10:00:00', 'other-machine')];
  const conflictScope = { range_start: '2026-10-12T08:00:00', range_end: '2026-10-12T10:00:00', selection: 'overlap', boundary: 'half_open', time_basis: 'factory_local' };
  const conflictSegments = Array.from({ length: 25 }, (_, index) => ({ start: '2026-10-12T08:30:00.125',
    end: '2026-10-12T09:00:' + String(index).padStart(2, '0') + '.500', concurrent_operations: 2 }));
  const conflictResource = { kind: 'machine', resource_ref: 'machine', label: 'M1', metric_version: 'decision-resource-v4', has_overlap: true, segments: [],
    get conflict_segments() { conflictSegmentReads++; return conflictSegments; } };
  const conflictData = { plan: { plan_ref: 'plan' }, tasks: conflictTasks, resources: [{ ref: 'machine', label: 'M1' }, { ref: 'other-machine', label: 'M2' }],
    plan_span: { start: conflictScope.range_start, end: conflictScope.range_end }, time_scope: conflictScope,
    projections: { baseline: { state: 'unavailable' }, calendar: { resources: [] }, occupancy: { state: 'available', basis: 'selected_plan_only', plan_ref: 'plan', time_scope: conflictScope, resources: [conflictResource], issues: [] } } };
  const conflictFacts = conflictWindow.PlanGanttModel.prepare(conflictData);
  assert.equal(conflictSegmentReads, 0, 'Ordinary plan preparation does not inspect conflict-detail segments');
  const resourceMembers = conflictFacts.resourceMembers.get('machine'), memberFilter = resourceMembers.filter;
  resourceMembers.filter = predicate => memberFilter.call(resourceMembers, item => { conflictMemberChecks++; return predicate(item); });
  const renderConflicts = () => conflictHooks.render(() => conflictWindow.PlanDetailsUI.Conflicts({ data: conflictData, prepared: conflictFacts }));
  let conflictTree = renderConflicts(); assert.equal(conflictMemberChecks, 20 * 5); assert.equal(conflictSegmentReads, 1);
  const conflictRows = find(conflictTree, 'tbody').children.flat(Infinity), firstConflictTasks = conflictRows[0].props.children[1].props.children.flat(Infinity);
  assert.deepEqual(Array.from(firstConflictTasks, node => node.props.key), ['late-source-first', 'early-source-later', 'point-inside'],
    'Conflict membership keeps source order, exact fractional boundaries and the original point predicate');
  renderConflicts(); assert.equal(conflictMemberChecks, 20 * 5, 'Unchanged conflict pages reuse their members');
  find(conflictTree, 'pager').onPage(2); conflictTree = renderConflicts();
  assert.equal(find(conflictTree, 'tbody').children.flat(Infinity).length, 5); assert.equal(conflictMemberChecks, 25 * 5);
  conflictHooks.unmount();

  // The dashboard picker reuses all labels and options while the timeline scrolls or zooms.
  const timelineHooks = hooks(); let timelineLabels = 0, timelineSelected = 'batch-first';
  const timelineData = { tasks: [{ task_ref: 'first', batch_ref: 'batch-first', batch_id: 'B1', sequence: 1, process_label: '加工', start: 'start-one' },
    { task_ref: 'second', batch_ref: 'batch-second', batch_id: 'B2', sequence: 2, process_label: '检查', start: 'start-two', point: true }] };
  const timelineWindow = { ResourceControls: { TimelineZoom: 'zoom' }, WorkbenchListControls: { EmptyState: 'empty' },
    GanttPresentation: { axis: () => ({ ticks: [] }) }, GanttPresentationUI: { Axis: 'axis' },
    PointContract: { isPoint: task => !!task.point }, WorkbenchFormat: { dateTime: String, compactRange: () => 'range' },
    DashboardTimelineModel: { prepare: value => value, groupPrepared: value => value,
      layoutPrepared: value => ({ tasks: value.tasks, rows: [], start: 0, end: 3600000, height: 100, locations: new Map() }),
      visibleRows: () => [], wire: String, timeLabel: value => { timelineLabels++; return value; } } };
  const timelineContext = vm.createContext({ window: timelineWindow, React: timelineHooks.React }); load(timelineContext, 'DashboardTimeline.jsx');
  const renderTimeline = () => timelineHooks.render(() => timelineWindow.DashboardTimeline({ data: timelineData, selectedBatch: timelineSelected, onSelect: batch => { timelineSelected = batch; } }));
  let timelineTree = renderTimeline(), timelinePicker = find(timelineTree, 'select'), timelineOptions = timelinePicker.children[1];
  assert.equal(timelineLabels, 2); assert.deepEqual(timelineOptions.map(option => option.props.value), ['first', 'second']);
  const timelineBoard = find(timelineTree, 'div', props => props.className === 'dy-timeline-board');
  timelineBoard.ref.current = { scrollLeft: 100, scrollTop: 50, clientWidth: 900, clientHeight: 330 };
  timelineBoard.onScroll(); timelineTree = renderTimeline(); assert.equal(timelineLabels, 2);
  assert.strictEqual(find(timelineTree, 'select').children[1], timelineOptions);
  find(timelineTree, 'zoom').onZoom(2); timelineTree = renderTimeline(); assert.equal(timelineLabels, 2);
  assert.strictEqual(find(timelineTree, 'select').children[1], timelineOptions);
  find(timelineTree, 'select').onChange({ target: { value: 'second' } }); timelineTree = renderTimeline();
  assert.equal(timelineSelected, 'batch-second'); assert.equal(find(timelineTree, 'select').value, 'second');
  timelineSelected = 'batch-first'; timelineTree = renderTimeline(); assert.equal(find(timelineTree, 'select').value, '');
  timelineData.tasks = timelineData.tasks.map(task => ({ ...task, process_label: task.process_label + '更新' }));
  // A new source data identity restarts model preparation, as the real workspace does after refresh.
  const refreshedTimelineData = { ...timelineData };
  timelineTree = timelineHooks.render(() => timelineWindow.DashboardTimeline({ data: refreshedTimelineData, selectedBatch: timelineSelected, onSelect() {} }));
  assert.equal(timelineLabels, 4); assert.notStrictEqual(find(timelineTree, 'select').children[1], timelineOptions);
  assert.equal(find(timelineTree, 'select').children[1][0].props.children[4], '加工更新'); timelineHooks.unmount();

  // A selected batch resolves its original timeline page; manual paging leaves that page.
  const sectionHooks = hooks(), sectionRequests = [], sectionWindow = { APSResourceContract: {}, WorkbenchTerms: { delivery_risks: {} },
    ResourceControls: { Button: 'button', ErrorBox: 'error' }, DashboardPanels: { Pager: 'pager' } };
  sectionWindow.DashboardSession = { useRead: (...args) => sectionWindow.APSResourceSession.useQuery(...args) };
  sectionWindow.DashboardAnalysisAPI = { read: async (plan, signal, query) => {
    sectionRequests.push({ ...query });
    return { meta: { snapshot_ref: 'same-timeline-snapshot' }, data: {
      tasks: query.page === 2 && !query.locate_batch_ref ? [{ batch_ref: 'in-page-batch', source: 'internal', machine_ref: 'machine' }] : [], pagination: {
      number: query.locate_batch_ref ? Math.floor(40 / query.size) + 1 : query.page, size: query.size, total: 60, pages: Math.ceil(60 / query.size) } } };
  } };
  const sectionContext = vm.createContext({ window: sectionWindow, React: sectionHooks.React, AbortController, DOMException });
  load(sectionContext, 'resource-session.js'); load(sectionContext, 'DashboardAnalysisPanels.jsx');
  let sectionBatch = null;
  const renderSection = () => sectionHooks.render(() => sectionWindow.DashboardAnalysisPanels.Section({ section: 'timeline', planRef: 'plan',
    locateBatchRef: sectionBatch, label: '计划时间轴工序', render: data => sectionHooks.React.createElement('timeline-data', { data }) }));
  const settleSection = async () => { renderSection(); sectionHooks.flush(); await turns(); const node = renderSection(); sectionHooks.flush(); return node; };
  let sectionTree = await settleSection(); assert.equal(find(sectionTree, 'pager').page.number, 1);
  sectionBatch = 'later-batch'; sectionTree = await settleSection();
  assert.equal(sectionRequests.at(-1).locate_batch_ref, sectionBatch); assert.equal(find(sectionTree, 'pager').page.number, 3);
  find(sectionTree, 'pager').onPage(1); sectionTree = await settleSection();
  assert.equal(sectionRequests.at(-1).locate_batch_ref, undefined); assert.equal(sectionRequests.at(-1).snapshot_ref, 'same-timeline-snapshot');
  assert.equal(find(sectionTree, 'pager').page.number, 1, '普通翻页移除locator，沿用原snapshot并能离开定位页');
  find(sectionTree, 'pager').onPage(2); sectionTree = await settleSection();
  const inPageSource = find(sectionTree, 'timeline-data').data, inPageReads = sectionRequests.length;
  sectionBatch = 'in-page-batch'; sectionTree = renderSection(); sectionHooks.flush(); await turns();
  assert.strictEqual(find(sectionTree, 'timeline-data').data, inPageSource, '本页具体工序切换批次时保留原数据和已挂载时间轴，不丢具体focus');
  assert.equal(find(sectionTree, 'pager').page.number, 2); assert.equal(sectionRequests.length, inPageReads, '当前页已有目标批次，不跳到该批首工序页');
  find(sectionTree, 'pager').onSize(50); sectionTree = await settleSection();
  sectionBatch = 'another-batch'; sectionTree = await settleSection();
  assert.equal(sectionRequests.at(-1).size, 50); assert.equal(sectionRequests.at(-1).locate_batch_ref, sectionBatch);
  assert.equal(sectionRequests.at(-1).snapshot_ref, undefined, '换批次重置定位请求，不沿用旧页码');
  const settledSectionReads = sectionRequests.length; await settleSection();
  assert.equal(sectionRequests.length, settledSectionReads, '定位范围稳定后普通重渲染不重复读取');
  const workspace = sectionWindow.DashboardAnalysisPanels.Workspace({ data: { plan: { plan_ref: 'plan' } }, category: 'delivery', selected: sectionBatch });
  assert.equal(find(workspace, sectionWindow.DashboardAnalysisPanels.Section, props => props.section === 'timeline').locateBatchRef, sectionBatch);
  sectionHooks.unmount();

  // Keep a pending selection until its task arrives, then retain user scrolling on new data/zoom/resize.
  const locateHooks = hooks(); let locateSelected = 'first-batch', onLocateResize;
  let locateData = { tasks: [{ task_ref: 'first', batch_ref: 'first-batch', batch_id: 'B1', top: 260 }] };
  const locateWindow = { ...timelineWindow, DashboardTimelineModel: { ...timelineWindow.DashboardTimelineModel, timeLabel: String,
    layoutPrepared: value => ({ tasks: value.tasks, rows: [], start: 0, end: 3600000, height: 800,
      locations: new Map(value.tasks.map(task => [task.task_ref, { top: task.top, item: { start: 1800000 } }])) }) } };
  const locateContext = vm.createContext({ window: locateWindow, React: locateHooks.React,
    ResizeObserver: class { constructor(fn) { onLocateResize = fn; } observe() {} disconnect() {} } });
  load(locateContext, 'DashboardTimeline.jsx');
  const renderLocate = () => locateHooks.render(() => locateWindow.DashboardTimeline({ data: locateData, selectedBatch: locateSelected, onSelect() {} }));
  let locateTree = renderLocate();
  const locateBoard = { scrollLeft: 0, scrollTop: 0, clientWidth: 900, clientHeight: 330 };
  find(locateTree, 'div', props => props.className === 'dy-timeline-board').ref.current = locateBoard;
  locateHooks.flush(); locateTree = renderLocate(); locateHooks.flush(); assert.equal(locateBoard.scrollTop, 200);
  locateSelected = 'late-batch'; locateTree = renderLocate(); locateHooks.flush(); assert.equal(locateBoard.scrollTop, 200);
  locateData = { tasks: [...locateData.tasks, { task_ref: 'late', batch_ref: 'late-batch', batch_id: 'B2', top: 640 }] };
  locateTree = renderLocate(); locateHooks.flush(); assert.equal(locateBoard.scrollTop, 580, '选择不变，目标页稍后到达也完成定位');
  locateBoard.scrollLeft = 123; locateBoard.scrollTop = 777;
  find(locateTree, 'div', props => props.className === 'dy-timeline-board').onScroll();
  locateData = { tasks: locateData.tasks.map(task => ({ ...task })) };
  locateTree = renderLocate(); locateHooks.flush();
  assert.equal(locateBoard.scrollLeft, 123); assert.equal(locateBoard.scrollTop, 777, '相同选择收到重复数据不抢滚动');
  find(locateTree, 'zoom').onZoom(2); locateTree = renderLocate(); locateHooks.flush(); assert.equal(locateBoard.scrollTop, 777);
  locateBoard.clientWidth = 1100; onLocateResize(); renderLocate(); locateHooks.flush(); assert.equal(locateBoard.scrollTop, 777, '缩放和尺寸变化保留用户垂直滚动');
  locateHooks.unmount();

  // An unrestricted trial keeps its scope, resource names and row preparation on hover/scroll.
  const trialGanttHooks = hooks(); let trialFilters = 0, trialNames = 0, trialBatchSets = 0, trialBatchChecks = 0;
  class TrialBatchSet extends Set { constructor(values) { super(values); trialBatchSets++; } has(value) { trialBatchChecks++; return super.has(value); } }
  const trialTasks = [8, 9].map((hour, index) => ({ task_ref: 'task-' + index, batch_ref: 'batch', batch_id: 'B1', sequence: index + 1, process_label: '加工',
    start: '2026-10-12T0' + hour + ':00:00', end: '2026-10-12T' + String(hour + 1).padStart(2, '0') + ':00:00', machine_ref: 'machine', operator_ref: null, issues: [], quantity: 1, batch_quantity: 1, piece_id: null }));
  trialTasks.push({ ...trialTasks[1], task_ref: 'point', start: trialTasks[1].end, event_kind: 'point' });
  trialTasks.forEach(task => { task.original = { start: task.start, end: task.end, machine_ref: task.machine_ref, operator_ref: task.operator_ref }; });
  trialTasks.filter = function (...args) { trialFilters++; return Array.prototype.filter.apply(this, args); };
  const trialMachines = [{ ref: 'machine', business_code: 'M1', label: '机床' }];
  trialMachines.forEach = function (...args) { trialNames++; return Array.prototype.forEach.apply(this, args); };
  const trialGanttData = { tasks: trialTasks, task_count: 3, scope: { batch_refs: ['batch'] }, resources: { machines: trialMachines, operators: [] } };
  const trialValues = { mode: 'machine', baseline: false, only_changed: false, query: '' }, trialPreferencePatches = [];
  const trialGanttWindow = { TrialControls: { Button: 'button', Tabs: 'tabs', Pager: 'pager', timeLabel: String, number: String },
    ResourceControls: { TimelineZoom: 'zoom' }, TrialViewState: { useView: () => ({ value: trialValues, change(patch) { trialPreferencePatches.push(patch); Object.assign(trialValues, patch); return true; } }), Notice: 'notice' },
    GanttPresentationUI: { useExpanded: () => ({ expanded: false }), Axis: 'axis' }, GanttPresentation: { axis: () => ({ ticks: [] }), taskLines: () => ({ primary: '加工', secondary: '' }) },
    PointContract: { isPoint: task => task.event_kind === 'point' }, PointGantt: { Marker: 'point' }, trialRowSorts: 0 };
  const trialGanttContext = vm.createContext({ window: trialGanttWindow, React: trialGanttHooks.React, Set: TrialBatchSet, innerWidth: 1280, innerHeight: 800,
    ResizeObserver: class { observe() {} disconnect() {} } });
  load(trialGanttContext, 'PlanGanttModel.js'); load(trialGanttContext, 'TrialGantt.jsx');
  vm.runInContext(`const rowSort = Array.prototype.sort; Array.prototype.sort = function (compare) {
    if (this[0] && this[0].t) window.trialRowSorts++; return rowSort.call(this, compare);
  };`, trialGanttContext);
  let trialSelected = 'point';
  const trialGanttRender = () => trialGanttHooks.render(() => trialGanttWindow.TrialGantt({ data: trialGanttData, selected: trialSelected, onSelect() {} }));
  let trialGanttTree = trialGanttRender();
  assert.equal(trialBatchSets, 1); assert.equal(trialBatchChecks, 3);
  find(trialGanttTree, 'div', props => props.className === 'tt-board').ref.current = { scrollLeft: 100, clientWidth: 1000, querySelector: () => ({ getBoundingClientRect: () => ({ width: 100 }) }) };
  find(trialGanttTree, 'div', props => props.className === 'tt-ticks').ref.current = { clientWidth: 1000 };
  trialGanttHooks.flush(); trialGanttTree = trialGanttRender();
  find(trialGanttTree, 'input', props => props.type === 'checkbox' && props.checked).onChange({ target: { checked: false } }); trialGanttTree = trialGanttRender();
  const preparedTrialFilters = trialFilters, preparedTrialRows = trialGanttWindow.trialRowSorts;
  find(trialGanttTree, 'point').onHover({ clientX: 200, clientY: 200 }); trialGanttTree = trialGanttRender();
  assert(find(trialGanttTree, 'div', props => props.role === 'tooltip'));
  find(trialGanttTree, 'div', props => props.className === 'tt-board').onScroll(); trialGanttTree = trialGanttRender();
  assert.equal(trialFilters, preparedTrialFilters); assert.equal(trialGanttWindow.trialRowSorts, preparedTrialRows); assert.equal(trialNames, 1);
  const trialLimitLabel = find(trialGanttTree, 'label', props => props.children.includes('原显示范围'));
  trialLimitLabel.children.find(child => child && child.type === 'input').props.onChange({ target: { checked: true } }); trialGanttTree = trialGanttRender();
  assert.equal(trialBatchSets, 2); const scopedTrialChecks = trialBatchChecks;
  trialValues.query = ' 加工 '; trialGanttTree = trialGanttRender();
  assert.equal(trialBatchSets, 2, 'Typing a search reuses the batch membership set'); assert.equal(trialBatchChecks, scopedTrialChecks + 3);
  trialGanttData.scope = { batch_refs: [] }; trialGanttTree = trialGanttRender();
  assert.equal(find(trialGanttTree, 'div', props => props['data-trial-task'] !== undefined), null, 'An explicit empty batch scope still matches no task');
  assert(find(trialGanttTree, 'div', props => props.role === 'status' && props.className === 'tt-notice'), 'A selected task filtered out of the rows has explicit feedback');
  const patchesBeforeLimitReveal = trialPreferencePatches.length;
  find(trialGanttTree, 'button', props => props.children.includes('显示并定位选中工序')).onClick();
  trialGanttTree = trialGanttRender(); trialGanttHooks.flush(); trialGanttTree = trialGanttRender();
  assert.equal(trialPreferencePatches.length, patchesBeforeLimitReveal, 'Releasing only a blocking original scope does not write empty preferences');
  assert.equal(trialValues.query, ' 加工 ', 'A search which already matches the selection stays in place');
  assert(find(trialGanttTree, 'div', props => props['data-trial-task'] === trialSelected));
  trialGanttData.scope = { batch_refs: ['batch'] }; trialGanttTree = trialGanttRender();
  find(trialGanttTree, 'label', props => props.children.includes('原显示范围')).children.find(child => child && child.type === 'input').props.onChange({ target: { checked: true } });
  trialGanttTree = trialGanttRender(); trialValues.only_changed = true; trialGanttTree = trialGanttRender();
  find(trialGanttTree, 'button', props => props.children.includes('显示并定位选中工序')).onClick();
  trialGanttTree = trialGanttRender(); trialGanttHooks.flush(); trialGanttTree = trialGanttRender();
  assert.deepEqual(JSON.parse(JSON.stringify(trialPreferencePatches.at(-1))), { only_changed: false });
  assert.equal(find(trialGanttTree, 'label', props => props.children.includes('原显示范围')).children.find(child => child && child.type === 'input').props.checked, true,
    'Revealing an unchanged selected task does not discard a scope that already includes it');
  trialValues.query = 'no-match'; trialGanttTree = trialGanttRender();
  find(trialGanttTree, 'button', props => props.children.includes('显示并定位选中工序')).onClick();
  trialGanttTree = trialGanttRender(); trialGanttHooks.flush(); trialGanttTree = trialGanttRender();
  assert.deepEqual(JSON.parse(JSON.stringify(trialPreferencePatches.at(-1))), { query: '' });
  trialGanttData.tasks = Array.from({ length: 35 }, (_, index) => ({ ...trialTasks[0], task_ref: 'page-' + String(index).padStart(2, '0'), changed: index < 30 }));
  trialGanttData.task_count = 35; trialSelected = 'page-34'; trialValues.only_changed = true; trialGanttTree = trialGanttRender();
  find(trialGanttTree, 'button', props => props.children.includes('显示并定位选中工序')).onClick();
  trialGanttTree = trialGanttRender(); trialGanttHooks.flush(); trialGanttTree = trialGanttRender();
  assert.equal(find(trialGanttTree, 'pager').page.number, 2, 'The unchanged selection is located across the page boundary once filters release it');
  assert(find(trialGanttTree, 'div', props => props['data-trial-task'] === trialSelected));
  trialSelected = 'absent-task'; trialGanttTree = trialGanttRender();
  assert.equal(find(trialGanttTree, 'div', props => props.role === 'status' && props.className === 'tt-notice'), null, 'A missing task is not mislabeled as filtered out');
  trialGanttHooks.unmount();

  // The three overdue flags share one pass and remain frozen with the data identity.
  const toolbarHooks = hooks(); let deadlineVisits = 0;
  const toolbarData = { task_count: 3, availability: { state: 'available' }, items: [{ task: { task_ref: 'one' }, deviation: { finish_late: true, unclosed: false, forecast_late: false } },
    { task: { task_ref: 'two' }, deviation: { finish_late: false, unclosed: true, forecast_late: true } },
    { task: { task_ref: 'three' }, deviation: { finish_late: false, unclosed: true, forecast_late: false } }] };
  const toolbarWindow = { ResourceControls: { Button: 'button', Icon: 'icon', TimelineZoom: 'zoom' }, WorkbenchTerms: { overdue: '超期' },
    ActualGanttModel: { ...modelContext.window.ActualGanttModel, deadlines(item) { deadlineVisits++; return modelContext.window.ActualGanttModel.deadlines(item); },
      wire() { assert.fail('Deadlines no longer convert an unused date'); }, tickStep: () => 1, tickLabel: String } };
  const toolbarContext = vm.createContext({ window: toolbarWindow, React: toolbarHooks.React }); load(toolbarContext, 'ActualGanttControls.jsx');
  const toolbarProps = { data: toolbarData, model: { groups: [], items: toolbarData.items, shownRefs: new Set(toolbarData.items.map(item => item.task.task_ref)) }, view: { mode: 'machine', query: '', late: 'all', collapsed: {}, selected: null }, width: 640, zoom: 1 };
  const toolbar = toolbarHooks.render(() => toolbarWindow.ActualGanttControls.Toolbar(toolbarProps));
  toolbarHooks.render(() => toolbarWindow.ActualGanttControls.Toolbar({ ...toolbarProps, width: 1000 })); assert.equal(deadlineVisits, 3);
  assert.deepEqual(find(toolbar, 'select').children.flat().map(option => option.props.children.join('')), ['全部工序 (3)', '已晚完成 (1)', '到期未确认完成 (2)', '剩余安排预计晚完成 (1)']);
  // A first historical supplement preserves the selected original scope's
  const fieldContext = vm.createContext({ window: { APSResourceContract: { failure: message => new Error(message) },
    WorkbenchTerms: { execution_states: {}, report_actions: {} }, WorkbenchFormat: {} } });
  load(fieldContext, 'WorkbenchFormat.js'); load(fieldContext, 'FieldContract.js'); load(fieldContext, 'FieldDraftModel.js');
  const field = fieldContext.window.FieldDraftModel, contract = fieldContext.window.FieldContract;
  const currentTask = { task_ref: 'current-task', operation_ref: 'current-operation', plan_ref: 'current-plan',
    start: '2026-09-08T08:00:00', end: '2026-09-09T10:00:00', machine_ref: 'original-machine', operator_ref: 'original-operator',
    execution: { write_context: { write_token: null, capabilities: {}, blocked_reasons: [] }, first_actual_start: '2026-09-01T00:00:00',
      known_completed_quantity: 10, target_quantity: 10, remaining_quantity: 0, unknown_record_count: 0, data_gaps: [],
      reports: [{ recorded_against_task_ref: 'current-task', report_no: 'R1', actual_start: '2026-09-08T08:00:00', actual_end: '2026-09-09T10:00:00' }] } };
  const initialized = field.initialize({ task: currentTask, record: null, action: 'create', now: new Date('2030-01-01T00:00:00Z') });
  assert.equal(initialized.draft.actual_start, '2026-09-09T10:00:00');
  assert.equal(initialized.draft.actual_end, '2030-01-01T08:00:00');
  assert.equal(initialized.draft.actual_machine_ref, '');
  assert.equal(initialized.draft.actual_operator_ref, '');
  assert.equal(contract.input(initialized.draft, null, 'create').actual_end, '2030-01-01T08:00:00');
  const fieldHooks = hooks(); fieldContext.React = fieldHooks.React;
  fieldContext.window.FieldControls = { Button: 'button', ErrorBox: 'error', Feedback: 'feedback' };
  fieldContext.window.ResourceControls = { Field: 'field', Choice: 'choice' };
  load(fieldContext, 'FieldEditorFields.jsx'); load(fieldContext, 'FieldEditor.jsx');
  const renderFieldInputs = (overrides = {}) => fieldContext.window.FieldEditorFields({
    task: currentTask, record: null, action: 'create', adapter: {}, draft: initialized.draft, suggestions: {}, disabled: false, first: {}, change() {}, ...overrides
  });
  const fieldInput = (tree, label) => find(tree, 'input', props => props['aria-label'] === label);
  const regularRecord = { completed_quantity: 0, actual_start: initialized.draft.actual_start, actual_end: initialized.draft.actual_end,
    effective_processing_hours: 1, actual_machine_ref: 'original-machine', actual_operator_ref: 'original-operator', remark: '原备注' };
  assert.equal(fieldInput(renderFieldInputs({ record: regularRecord, action: 'correct', draft: contract.draft(regularRecord) }), '本次完成数量').disabled, false);
  assert.equal(fieldInput(renderFieldInputs({ record: regularRecord, action: 'supplement', draft: contract.draft(regularRecord) }), '本次完成数量').disabled, true,
    'Supplement still protects an ordinary report whose known quantity is zero');
  fieldHooks.unmount();

  // Closing a completed file command consumes it once and refreshes without the old snapshot.
  const fieldWorkspaceHooks = hooks(), fieldWorkspaceReads = []; let fieldResets = 0;
  const fileCommand = { phase: 'idle', locked: false, reset() { fieldResets++; this.phase = 'idle'; return true; } };
  const fieldWorkspaceWindow = { APSResourceContract: {}, FieldControls: { Button: 'button', ErrorBox: 'error', Feedback: 'feedback' },
    WorkbenchGuards: { useDirtyGuard: () => ({}), confirmLeave: async () => true }, WorkbenchPageContext: { useSnapshot() {} }, WorkbenchCaption: { useCaption() {} },
    WorkbenchTerms: { current_official: '当前正式计划', plan_version: String }, WorkbenchListControls: { Pager: 'field-pager' },
    FieldFilters: 'field-filters', FieldTable: 'field-table', FieldDetail: 'field-detail', FieldFiles: 'field-files' };
  const fieldWorkspaceContext = vm.createContext({ window: fieldWorkspaceWindow, React: fieldWorkspaceHooks.React, AbortController, DOMException });
  // FieldAPI binds its execution namespace at load; this workspace check replaces only its readView answer.
  fieldWorkspaceWindow.APSResourceAPI = { create: () => ({}) };
  load(fieldWorkspaceContext, 'resource-session.js'); load(fieldWorkspaceContext, 'FieldAPI.js');
  fieldWorkspaceWindow.APSResourceSession.useCommand = () => fileCommand;
  fieldWorkspaceWindow.FieldAPI.readView = async input => {
    fieldWorkspaceReads.push({ ...input });
    const { page, size, task_ref, operation_ref, snapshot_ref, ...scope } = input;
    return { meta: { snapshot_ref: 'field-snapshot' }, data: { scope,
      plan: { plan_ref: scope.plan_ref, display_name: '正式计划', kind: 'official', is_current_official: true, version: 1 },
      tasks: [{ task_ref: 'field-task', operation_ref: 'field-operation' }], page: { number: page || 1, size, total: 30, pages: 2 }, summary: {} } };
  };
  load(fieldWorkspaceContext, 'FieldWorkspace.jsx');
  const fieldWorkspaceProps = { initialContext: { plan_ref: 'field-plan', task_ref: 'field-task', operation_ref: 'field-operation', scope: { query: 'old-query' } } };
  const renderFieldWorkspace = () => fieldWorkspaceHooks.render(() => fieldWorkspaceWindow.FieldWorkspace(fieldWorkspaceProps));
  const settleFieldWorkspace = async () => {
    let tree;
    for (let index = 0; index < 4; index++) { tree = renderFieldWorkspace(); fieldWorkspaceHooks.flush(); await turns(); }
    return tree;
  };
  let fieldWorkspaceTree = await settleFieldWorkspace();
  find(fieldWorkspaceTree, 'field-pager').onPage(2); fieldWorkspaceTree = await settleFieldWorkspace();
  assert.equal(fieldWorkspaceReads.at(-1).snapshot_ref, 'field-snapshot');
  find(fieldWorkspaceTree, 'button', props => props.children.includes('报工文件')).onClick(); fieldWorkspaceTree = renderFieldWorkspace();
  assert(find(fieldWorkspaceTree, 'field-files'));
  fileCommand.phase = 'done'; fileCommand.result = { result: 'committed' }; fieldWorkspaceTree = renderFieldWorkspace();
  const readsBeforeFileClose = fieldWorkspaceReads.length, resetsBeforeFileClose = fieldResets;
  find(fieldWorkspaceTree, 'field-files').onClose(); fieldWorkspaceTree = await settleFieldWorkspace();
  assert.equal(fieldResets, resetsBeforeFileClose + 1); assert.equal(fieldWorkspaceReads.length, readsBeforeFileClose + 1);
  assert.equal(fieldWorkspaceReads.at(-1).snapshot_ref, undefined); assert.equal(find(fieldWorkspaceTree, 'field-files'), null);
  find(fieldWorkspaceTree, 'button', props => props.children.includes('报工文件')).onClick(); fieldWorkspaceTree = renderFieldWorkspace();
  const readsBeforeFileCancel = fieldWorkspaceReads.length;
  find(fieldWorkspaceTree, 'field-files').onClose(); fieldWorkspaceTree = await settleFieldWorkspace();
  assert.equal(fieldWorkspaceReads.length, readsBeforeFileCancel, 'Closing an uncommitted file dialog does not refresh');
  find(fieldWorkspaceTree, 'field-filters').onChange({ plan_ref: 'field-plan', query: 'new-query', task_ref: 'stale-task', operation_ref: 'stale-operation' });
  fieldWorkspaceTree = await settleFieldWorkspace();
  assert.equal(fieldWorkspaceReads.at(-1).task_ref, undefined); assert.equal(fieldWorkspaceReads.at(-1).operation_ref, undefined);
  assert.equal(fieldWorkspaceReads.at(-1).page, 1); assert.equal(fieldWorkspaceReads.at(-1).query, 'new-query'); assert.equal(find(fieldWorkspaceTree, 'field-table').opened, null);
  find(fieldWorkspaceTree, 'field-table').onClear(); fieldWorkspaceTree = await settleFieldWorkspace();
  assert.equal(fieldWorkspaceReads.at(-1).query, undefined, 'Clearing field filters still replaces the old filter scope');
  assert.equal(fieldWorkspaceReads.at(-1).task_ref, undefined); assert.equal(fieldWorkspaceReads.at(-1).operation_ref, undefined); fieldWorkspaceHooks.unmount();

  // Only the actual CSV export gets the longer transport deadline; other downloads keep 20 seconds.
  // Every download runs through APSWorkbenchTransport.download: attachment, CSV magic bytes and a backend filename with its .csv suffix.
  const downloadDeadlines = [], downloadTimers = new Map(); let downloadTimerId = 0;
  const actualCsvName = '现场实际甘特-2026-10-26T101500.csv', csvBytes = [0xef, 0xbb, 0xbf, 0x61];
  const downloadWindow = { ActualGanttContract: { scope: value => value, transport: value => value } };
  const downloadContext = vm.createContext({ window: downloadWindow,
    setTimeout(fn, delay) { downloadDeadlines.push(delay); const id = ++downloadTimerId; downloadTimers.set(id, fn); return id; },
    clearTimeout(id) { downloadTimers.delete(id); } });
  const downloadFetch = withTransport(downloadContext, call => file(Uint8Array.from(csvBytes), 'text/csv',
    { 'Content-Disposition': "attachment; filename*=UTF-8''" + encodeURIComponent(call.path.endsWith('/actual-gantt/export') ? actualCsvName : 'export.csv') }));
  load(downloadContext, 'resource-contract.js'); load(downloadContext, 'resource-api.js'); load(downloadContext, 'ActualGanttAPI.js');
  const resourceDownloads = downloadWindow.APSResourceAPI.create(), exportController = new AbortController();
  await resourceDownloads.download('plans/plan/export', {}, exportController.signal);
  await resourceDownloads.download('execution/files/export', {}, exportController.signal, { timeout: 35000 });
  const actualExport = await downloadWindow.ActualGanttAPI.export({ format: 'csv' }, exportController.signal);
  assert.equal(actualExport.filename, actualCsvName, 'The saved name is the backend Content-Disposition name');
  assert.deepEqual([...new Uint8Array(await actualExport.blob.arrayBuffer())], csvBytes);
  assert.deepEqual(downloadDeadlines, [20000, 35000, 60000]); assert.equal(downloadTimers.size, 0);
  assert.equal(downloadFetch.calls.at(-1).url.href, 'http://127.0.0.1:8080/api/workbench/v1/actual-gantt/export?format=csv');
  assert.equal(downloadFetch.calls.some(call => call.signal.aborted), false);
  console.log(JSON.stringify({ read_identity_and_cancellation: true, same_identity_reopen_loads: reopenLoads, error_retry_and_hidden_snapshot_loads: retryLoads, unmount_refresh_waiters_cancelled: outcomes.length, unstarted_refresh_loads: queuedLoads,
    baseline_reopen_reads: 1, baseline_refresh_and_identity_reads: baselineLoads,
    resource_related_save_requests: resourceRequests.map(value => ({ kind: value.kind, page: value.page, snapshot_ref: value.snapshot_ref || null })),
    resource_related_save_detail_reads: resourceDetails, overview_time_reads: overviewTimeReads, overview_bin_builds: binBuilds,
    overview_mounts: overviewMounts, overview_preparation_steps: overviewSteps,
    trial_filter_calls: trialFilters, trial_row_sorts: trialGanttWindow.trialRowSorts, trial_resource_name_passes: trialNames, actual_deadline_visits: deadlineVisits,
    conflict_prepare_segment_reads: 0, conflict_current_page_member_checks: 20 * 5, conflict_two_page_member_checks: conflictMemberChecks,
    dashboard_picker_initial_labels: 2, dashboard_picker_scroll_zoom_extra_labels: 0, dashboard_picker_refreshed_labels: timelineLabels,
    trial_search_batch_set_rebuilds: 0, trial_search_membership_checks: 3,
    scroll_scans: scans, unrelated_scroll_refreshes: 0, context_updates: 60,
    trailing_history_writes: 1, immediate_navigation_and_history_restore: true, restoring_pagehide_preserved: true,
    forward_branch_plan_bound: true, history_help_chapters: true, dashboard_issue_scope_and_return: true, dashboard_late_request_isolated: true,
    dashboard_whole_run_preserves_highlight: true, plan_range_resets_analysis_page: true, stale_plan_page_clamped: true,
    same_plan_range_keeps_analysis_page: true, trial_task_opens_details: true, gantt_selection_keeps_details_closed: true,
    trial_edit_guard_preserved: true, metric_task_visits: reads }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
