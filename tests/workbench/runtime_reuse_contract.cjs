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
  const read = (id, load) => queryHooks.render(() => queryContext.window.TrialSession.useRead(load, [id]));
  read('old', signal => { oldSignal = signal; return new Promise(resolve => { first = resolve; }); }); queryHooks.flush(); await turns();
  assert.equal(read('new', () => new Promise(resolve => { second = resolve; })).result, null); queryHooks.flush(); await turns();
  assert.equal(oldSignal.aborted, true); first('stale'); await turns();
  assert.equal(read('new', () => {}).result, null); second('current'); await turns(); assert.equal(read('new', () => {}).result, 'current');
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
  const mainSource = source('main.jsx'), start = mainSource.indexOf('  function App() {'), end = mainSource.indexOf('  ReactDOM.createRoot(root).render(<App />);');
  load(appContext, 'App-test.jsx', mainSource.slice(start, end) + '\nwindow.TestApp = App;');
  const find = (node, type) => { if (!node || !node.props) return null; if (node.type === type) return node.props; for (const child of node.props.children.flat()) { const result = find(child, type); if (result) return result; } return null; };
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

  const modelContext = vm.createContext({ window: { WorkbenchFormat: {}, FieldContract: { quantityReasons: {}, states: {} } } });
  load(modelContext, 'ActualGanttModel.js'); let reads = 0;
  const data = { availability: { state: 'available' }, items: Array.from({ length: 1000 }, (_, n) => ({ task: { end: '2026-09-09T08:00:00' },
    execution: { get execution_state() { reads++; return ['complete', 'unreported', 'partial'][n % 3]; }, confirmed_finish: '2026-09-09T08:30:00' } })) };
  assert.deepEqual(JSON.parse(JSON.stringify(modelContext.window.ActualGanttModel.metrics(data))), { complete: 334, pending: 333, reported: 333, average: 30 }); assert.equal(reads, 1000);
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
  console.log(JSON.stringify({ read_identity_and_cancellation: true, unmount_refresh_waiters_cancelled: outcomes.length, unstarted_refresh_loads: queuedLoads,
    scroll_scans: scans, unrelated_scroll_refreshes: 0, context_updates: 60,
    trailing_history_writes: 1, immediate_navigation_and_history_restore: true, restoring_pagehide_preserved: true,
    forward_branch_plan_bound: true, metric_task_visits: reads }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
