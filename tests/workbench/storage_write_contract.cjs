'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const { routeFetch, envelope, failure, json: respond, deferred, browser } = require('./route_fetch.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const names = ['WorkbenchTerms.js', 'transport.js', 'resource-contract.js', 'resource-api.js', 'resource-session.js',
  'ProcessContract.js', 'ProcessAPI.js', 'BatchContract.js', 'BatchAPI.js',
  'DashboardContract.js', 'OutsourcingContract.js', 'TrialContract.js', 'TrialAdoptionAPI.js', 'CalibrationAdoptionAPI.js',
  'DashboardSession.js', 'OutsourcingSession.js', 'TrialAdoptionState.js', 'CalibrationAdoptionState.js', 'RunAdoptionAPI.js', 'RunAdoptionAction.jsx',
  'TrialAdoptionControls.jsx', 'CalibrationAdoptionControls.jsx', 'RunAdoptionControls.jsx',
  'RunJobAPI.js', 'SystemMaintenanceAPI.js', 'TrialAPI.js', 'TrialViewState.js'];
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: names.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })), check_combined: true });
// Every pending intent carries its data_context_ref, itself a JSON string. Validating that field is counted apart from
// parsing stored records, so the read/parse budgets below keep describing storage access only.
const dataContext = JSON.stringify({ database_scope: '/plans/试调 & 正式.db', successful_restores: ['e'.repeat(32)] });
const listeners = new Map(), events = [], counters = { reads: 0, parses: 0, validations: 0 }; let contextParses = 0;
const counting = Object.create(JSON);
counting.parse = value => { if (value === dataContext) contextParses++; else counters.parses++; return JSON.parse(value); };
const w = vm.createContext({ console, JSON: counting, URLSearchParams, AbortController, setTimeout, clearTimeout,
  crypto: { getRandomValues: bytes => { bytes.fill(5); return bytes; } }, CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } } });
w.window = w;
// Only the network answer is stubbed: every request still runs through the real module, APSWorkbenchTransport and its validators.
// A request without a route fails loudly; the transport reports such a failure as an unanswered request.
const routes = {}, fetch = routeFetch(routes); browser(w, fetch);
w.WorkbenchHandlerMemory = { read: () => ({ value: '经办人' }), write() {}, useHint: () => '' }; w.WorkbenchGuards = { useDirtyGuard() {} };
w.ResourceControls = { Button: 'button', Modal: 'modal' };
w.CalibrationControls = { text: String, amount: String, unitHours: String };
w.WorkbenchFormat = { dateTime: String }; w.WorkbenchReference = 'reference';
w.RunAdoptionControls = { Button: 'button', Dialog: 'dialog' };
w.addEventListener = (type, fn) => { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); };
w.removeEventListener = (type, fn) => listeners.get(type)?.delete(fn);
w.dispatchEvent = event => { events.push(event); for (const fn of listeners.get(event.type) || []) fn(event); };
for (const item of compiled.outputs) vm.runInContext(item.code, w, { filename: item.path });
const realRunAdoptionControls = w.RunAdoptionControls;
const ref = value => value.toString(16).padStart(48, '0'), values = { confirm: true, reason: '核对实际安排', declared_operator: '经办人' };
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
// An unanswered write: the transport turns it into the single "result unknown" error.
const offline = log => call => { log.push(call.body); throw new Error('网络中断'); };
const unknownOutcome = w.WorkbenchTerms.outcomes.pending('操作');
function storage() {
  const data = new Map(), writes = [];
  return { data, writes, failGet: null, failSet: null, failRemove: null,
    getItem(key) { counters.reads++; if (this.failGet) throw this.failGet; return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { writes.push(['set', key]); if (this.failSet) throw this.failSet; data.set(key, value); },
    removeItem(key) { writes.push(['remove', key]); if (this.failRemove) throw this.failRemove; data.delete(key); } };
}
const reset = () => { counters.reads = counters.parses = counters.validations = 0; contextParses = 0; };
function hooks() {
  let cursor = 0; const slots = [], effects = [];
  const same = (a, b) => a && b && a.length === b.length && a.every((value, index) => value === b[index]);
  const memo = (fn, deps) => { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() }; return slots[i].value; };
  const React = { createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), Fragment: 'fragment',
    useId() { return 'id-' + cursor++; },
    useRef(value) { const i = cursor++; if (!slots[i]) slots[i] = { current: value }; return slots[i]; },
    useState(value) { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof value === 'function' ? value() : value };
      return [slots[i].value, next => { slots[i].value = typeof next === 'function' ? next(slots[i].value) : next; }]; },
    useReducer(reducer, initial) { const [value, setValue] = this.useState(initial); return [value, action => setValue(old => reducer(old, action))]; },
    useMemo: memo, useEffect(fn, deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) {
      const old = slots[i]; slots[i] = { deps }; effects.push(() => { if (old?.cleanup) old.cleanup(); slots[i].cleanup = fn(); }); } } };
  return { render(fn) { cursor = 0; w.React = React; return fn(); }, flush() { while (effects.length) effects.shift()(); },
    unmount() { for (const slot of slots) if (slot.cleanup) slot.cleanup(); } };
}
async function main() {
  // Run writes have one current-intent read; RECENT must succeed before PENDING is removed.
  const runStore = storage(), pending = w.RunJobAPI.pending(runStore), inputRef = 'i'.repeat(32);
  reset(); const intent = pending.begin(inputRef, null, dataContext); assert.equal(counters.reads, 1); assert.equal(counters.parses, 0);
  assert.equal(intent.schema_version, 2); assert.equal(intent.data_context_ref, dataContext); assert.equal(intent.request_key, 'run-' + '05'.repeat(24));
  reset(); const attached = pending.attach(intent, ref(1)); assert.equal(counters.reads, 1); assert.equal(counters.parses, 1);
  reset(); pending.finish(attached, 'found'); assert.equal(counters.reads, 1); assert.equal(counters.parses, 1);
  assert.deepEqual(runStore.writes.slice(-2), [['set', w.RunJobAPI.RECENT_KEY], ['remove', w.RunJobAPI.PENDING_KEY]]);
  assert.equal(pending.read(), null); assert.equal(pending.recent().resolution, 'found');
  // L07: a run cannot start without the preview's data source.
  assert.throws(() => pending.begin(inputRef, null), /读到的排产数据不完整/); assert.equal(pending.read(), null);
  const retry = pending.begin(inputRef, null, dataContext), quota = new Error('QuotaExceededError'); runStore.failSet = quota;
  assert.throws(() => pending.finish(retry, 'found'), error => error === quota);
  assert.equal(pending.read().request_key, retry.request_key, 'A failed RECENT write leaves PENDING intact');
  runStore.failSet = null; runStore.failRemove = new Error('removeItem unavailable');
  assert.throws(() => pending.finish(retry, 'found'), /removeItem unavailable/);
  assert.equal(pending.read().request_key, retry.request_key); assert.equal(pending.recent().intent.request_key, retry.request_key);
  assert.throws(() => pending.reject(retry), /无法更新/); runStore.failRemove = null;
  const late = Promise.resolve().then(() => pending.finish(retry, 'found'));
  const newer = { ...retry, request_key: 'run-' + 'f'.repeat(48) }; runStore.data.set(w.RunJobAPI.PENDING_KEY, JSON.stringify(newer));
  await assert.rejects(late, /记录已变化/); assert.equal(pending.read().request_key, newer.request_key);
  reset(); pending.reject(newer); assert.equal(counters.reads, 1); assert.equal(counters.parses, 1);
  // L07: a stored intent without schema_version 2 and data_context_ref is a damaged record, never restored.
  runStore.data.set(w.RunJobAPI.PENDING_KEY, JSON.stringify({ input_ref: inputRef, request_key: intent.request_key, run_ref: null }));
  assert.throws(() => pending.read(), /排产操作记录不完整/, 'A legacy pending intent is rejected');
  runStore.data.set(w.RunJobAPI.PENDING_KEY, JSON.stringify(intent)); assert.equal(pending.read().request_key, intent.request_key, 'A current pending intent restores');

  const maintenanceStore = storage(), maintenance = w.SystemMaintenanceAPI.pending(maintenanceStore);
  reset(); const maintenanceIntent = maintenance.begin('create'); assert.equal(counters.reads, 1); assert.equal(counters.parses, 0);
  assert.equal(maintenance.read().request_key, maintenanceIntent.request_key); maintenance.finish(maintenanceIntent);
  w.localStorage = storage(); reset(); const trialKey = w.TrialAPI.reserve(); assert.equal(counters.reads, 1);
  assert.equal(w.TrialAPI.pending(), trialKey); w.TrialAPI.clear(trialKey);
  w.localStorage.failSet = quota; assert.throws(() => w.TrialAPI.reserve(), /存不下/); w.localStorage.failSet = null;

  // Mount the actual owners: local EVENT consumes the same validated object, external storage still parses/validates.
  const handling = { status: 'new', ...Object.fromEntries(w.DashboardContract.fields.map(field => [field, null])) };
  const after = { sent: '2026-10-09T08:00:00', planned: '2026-10-11T08:00:00', returned: null, confirmedState: 'in_transit' };
  const target = { kind: 'single', batch_ref: ref(2), supplier_ref: ref(3), operation_refs: [ref(4)], grouping_basis: 'explicit_receipt_membership',
    batch: { ref: ref(2) }, supplier: { ref: ref(3) }, operations: [{ operation_ref: ref(4) }] };
  const scope = { scenario_ref: ref(5), draft_ref: ref(6), baseline: { plan_ref: null, version: null }, task_count: 1, scope_complete: true };
  const trialScope = { ...scope, data_context_ref: dataContext };
  const baseline = { template_operation_ref: ref(7), template_revision: 1, template_snapshot: 'captured-template', part_ref: ref(8), part_no: 'P1', part_name: '零件',
    sequence: 1, operation_label: '车削', source: 'internal', old_unit_hours: 1, suggested_unit_hours: 2, sample_count: 0, eligible_sample_count: 0,
    candidate_count: 0, excluded_count: 0, sample_refs: [], sample_revisions: [], exclusion_reasons: [], method_version: 'v1' };
  const sessions = [
    { name: 'DashboardSession', contract: 'DashboardContract', leaf: 'expected', contexts: 0, mount: module => module.useCommand(),
      value: { version: 1, request_key: 'dashboard-' + 'a'.repeat(48), phase: 'pending', item_ref: ref(9), action: 'transition', input: { target_status: 'following' }, before: handling, source: {}, risk: {} } },
    { name: 'OutsourcingSession', contract: 'OutsourcingContract', leaf: 'facts', contexts: 0, mount: module => module.useCommand(),
      value: { version: 1, request_key: 'outsourcing-' + 'a'.repeat(48), phase: 'pending', input: { ...after, target: w.OutsourcingContract.target(target), declared_operator: values.declared_operator, reason: values.reason }, after, target } },
    // The trial adoption intent always carries the preview's data source, so validating it parses that one field.
    { name: 'TrialAdoptionState', contract: 'TrialAdoptionAPI', leaf: 'overview', contexts: 1, mount: module => module.useSession({ disabled: true, onAdopted() {} }),
      value: { schema_version: 1, request_key: 'trial-adoption-' + 'a'.repeat(48), phase: 'pending', scenario_ref: scope.scenario_ref, preview: trialScope, input: values } },
    { name: 'CalibrationAdoptionState', contract: 'CalibrationAdoptionAPI', leaf: 'binding', contexts: 0, mount: module => module.useSession({ detail: null, stale: true }),
      value: { version: 1, request_key: 'calibration-' + 'a'.repeat(48), phase: 'pending', baseline, input: values } }
  ];
  const sessionCounts = {};
  for (const row of sessions) {
    const module = w[row.name], contract = w[row.contract], leaf = contract[row.leaf], host = hooks(); w.localStorage = storage();
    contract[row.leaf] = (...args) => { counters.validations++; return leaf(...args); };
    const session = host.render(() => row.mount(module)); host.flush(); reset();
    assert.equal(module.save(row.value, null), row.value); assert.equal(events.at(-1).detail, row.value);
    assert.deepEqual(counters, { reads: 1, parses: 0, validations: 1 }); assert.equal(contextParses, row.contexts); sessionCounts[row.name] = { ...counters };
    reset(); w.dispatchEvent(events.at(-1)); assert.deepEqual(counters, { reads: 0, parses: 0, validations: 0 }); assert.equal(contextParses, 0);
    w.dispatchEvent({ type: 'storage', key: module.KEY }); assert.deepEqual(counters, { reads: 1, parses: 1, validations: 1 }); assert.equal(contextParses, row.contexts);
    assert.equal(JSON.stringify(module.read()), JSON.stringify(row.value));
    if (row.name === 'DashboardSession' || row.name === 'OutsourcingSession') {
      const rejected = { ...row.value, phase: 'rejected' }; module.save(rejected, row.value); reset();
      assert.equal(session.finish(), true); assert.deepEqual(counters, { reads: 1, parses: 1, validations: 1 });
    }
    w.localStorage.data.set(module.KEY, '{broken'); assert.throws(() => module.read(), /损坏/);
    host.unmount(); contract[row.leaf] = leaf;
  }

  // Trial recovery carries the preview's data source; only a settled, replaced source releases PENDING.
  const trialAPI = w.TrialAdoptionAPI, trialState = w.TrialAdoptionState;
  assert.equal(trialAPI.overview(trialScope).data_context_ref, dataContext);
  // L09: an adoption scope without its data source is rejected instead of being saved with a null source.
  assert.throws(() => trialAPI.overview(scope), /采用数据不完整/);
  const trialIntent = sessions[2].value;
  assert.equal(trialState.KEY, w.TrialAdoptionState.KEY);
  let mayBeInFlight = true;
  const trialStatus = () => ({ state: 'not_observed', receipt: null, may_be_in_flight: mayBeInFlight, can_retry_automatically: false });
  routes['GET /api/workbench/v1/trial/scenarios/*/adoption-commands/*'] = () => envelope(trialStatus(), { as_of: '2026-10-22T09:00:00' });
  assert.equal(JSON.stringify(await trialAPI.lookup(trialIntent)), JSON.stringify(trialStatus()));
  let lookupCall = fetch.calls.at(-1);
  assert.equal(lookupCall.path, '/api/workbench/v1/trial/scenarios/' + scope.scenario_ref + '/adoption-commands/' + trialIntent.request_key);
  assert.equal(lookupCall.query.data_context_ref, dataContext); assert.equal(lookupCall.method, 'GET');
  mayBeInFlight = false;
  assert.equal(JSON.stringify(await trialAPI.lookup(trialIntent)), JSON.stringify(trialStatus()));

  const trialOverview = trialAPI.overview, recoveryHost = hooks(); w.localStorage = storage();
  const recovery = recoveryHost.render(() => trialState.useSession({ disabled: true, onAdopted() {} })); recoveryHost.flush();
  trialAPI.overview = (...args) => { counters.validations++; return trialOverview(...args); };
  trialState.save(trialIntent, null); const savedTrial = w.localStorage.data.get(trialState.KEY), savedEvents = events.length, savedWrites = w.localStorage.writes.length;
  mayBeInFlight = true; reset(); await recovery.lookup();
  assert.deepEqual(counters, { reads: 0, parses: 0, validations: 0 }, 'An in-flight lookup sends the already validated data source without touching storage');
  assert.equal(contextParses, 0);
  assert.equal(fetch.calls.at(-1).query.data_context_ref, dataContext);
  assert.equal(w.localStorage.data.get(trialState.KEY), savedTrial); assert.equal(w.localStorage.writes.length, savedWrites); assert.equal(events.length, savedEvents);
  reset(); w.dispatchEvent(events.at(-1)); assert.deepEqual(counters, { reads: 0, parses: 0, validations: 0 });
  mayBeInFlight = false; reset(); await recovery.lookup();
  assert.deepEqual(counters, { reads: 1, parses: 1, validations: 1 }, 'Clearing reads PENDING once and parses only the stored intent');
  assert.equal(contextParses, 1, 'The stored intent\'s data source is validated once');
  assert.equal(w.localStorage.data.has(trialState.KEY), false); assert.equal(events.at(-1).detail, null);
  assert.equal(recoveryHost.render(() => trialState.useSession({ disabled: true, onAdopted() {} })).saved, null);
  reset(); w.dispatchEvent(events.at(-1)); assert.deepEqual(counters, { reads: 0, parses: 0, validations: 0 });
  recoveryHost.unmount(); trialAPI.overview = trialOverview;

  w.localStorage = storage(); const adoptionHost = hooks();
  const element = w.RunAdoptionAction({ candidateRef: ref(10), candidateCatalog: [] });
  adoptionHost.render(() => element.type(element.props)); adoptionHost.flush();
  const candidate = { candidate_ref: ref(10), run_ref: ref(11), baseline: { plan_ref: null, version: null }, task_count: 1, scope_complete: true, data_context_ref: dataContext };
  const validIntent = w.RunAdoptionAPI.validIntent; let localValidations = 0;
  w.RunAdoptionAPI.validIntent = value => { localValidations++; return validIntent(value); };
  reset(); const adopted = w.RunAdoptionAPI.pending().begin(candidate, values, null);
  assert.equal(counters.reads, 1); assert.equal(counters.parses, 0); assert.equal(localValidations, 0, 'RunAdoptionAction consumes the verified local event');
  assert.equal(events.at(-1).detail, adopted); assert.equal(adopted.data_context_ref, dataContext);
  assert.equal(w.RunAdoptionAPI.pending().read().request_key, adopted.request_key); adoptionHost.unmount(); w.RunAdoptionAPI.validIntent = validIntent;
  // A definitive 404 non-commit (the candidate is gone) releases PENDING like the other adoption transports.
  routes['POST /api/workbench/v1/scheduling/candidates/*/adopt'] = () => respond(failure('entity_not_found', '所选候选方案已不存在。'), 404);
  const gone = await w.RunAdoptionAPI.adopt(adopted, 'w'.repeat(32)).then(() => assert.fail('A missing candidate is not adopted'), error => error);
  assert.equal(gone.message, '所选候选方案已不存在。'); assert.equal(w.APSWorkbenchTransport.rejected(gone), true);
  assert.equal(fetch.calls.at(-1).body.request_key, adopted.request_key);
  assert.equal(w.RunAdoptionAPI.pending().reject(adopted, gone).phase, 'rejected');
  // A record cleared elsewhere returns the draft to the remembered-handler default and drops the stale lookup error.
  routes['GET /api/workbench/v1/scheduling/candidates/*/adoption-commands/*'] = () => { throw new Error('网络中断'); };
  w.localStorage = storage(); const runHost = hooks(), runElement = w.RunAdoptionAction({ candidateRef: ref(10), candidateCatalog: [] });
  const renderRun = () => runHost.render(() => runElement.type(runElement.props)), runDialog = () => renderRun().props.children.find(child => child && child.type === 'dialog');
  renderRun(); runHost.flush(); w.RunAdoptionAPI.pending().begin(candidate, values, null);
  renderRun().props.children[0].props.onClick(); renderRun(); runHost.flush(); await tick();
  lookupCall = fetch.calls.at(-1);
  assert.equal(lookupCall.path, '/api/workbench/v1/scheduling/candidates/' + ref(10) + '/adoption-commands/' + adopted.request_key);
  assert.equal(lookupCall.query.run_ref, ref(11)); assert.equal(lookupCall.query.data_context_ref, dataContext);
  assert.equal(runDialog().props.error, '查询采用结果失败，采用可能已经生效。请点「查询结果」重试，不要重新采用。'); assert.equal(runDialog().props.draft.reason, values.reason);
  w.localStorage.data.delete(w.RunAdoptionAPI.PENDING_KEY); w.dispatchEvent({ type: 'storage', key: w.RunAdoptionAPI.PENDING_KEY });
  assert.equal(runDialog().props.intent, null); assert.equal(runDialog().props.error, '');
  assert.equal(JSON.stringify(runDialog().props.draft), JSON.stringify({ reason: '', declared_operator: '经办人' })); runHost.unmount();

  // Web Locks contention and a browser without Web Locks are operation errors, not damaged stored records:
  // nothing is written, storageError stays clear, and the same session submits once the other page releases the lock.
  const noLocks = {}, contended = { locks: { request: async (_key, options, fn) => { assert.equal(options.ifAvailable, true); return fn(null); } } },
    granted = { locks: { request: async (_key, _options, fn) => fn({}) } }, message = value => typeof value === 'string' ? value : value.message;
  async function refused(render, navigator, submit, expected, calls) {
    w.navigator = navigator; await submit(render()); const session = render();
    assert.equal(session.error && message(session.error), expected); assert(!session.storageError, expected + ' is not a damaged stored record');
    assert.equal(session.busy, false); assert.deepEqual(w.localStorage.writes, []); assert.equal(calls.length, 0);
  }
  const stale = (before = () => {}) => () => { before(); return respond(failure('stale_write', '来源资料已变化，请刷新后重试。'), 409); };
  const findButton = (node, label) => {
    if (!node || typeof node !== 'object') return null;
    if (Array.isArray(node)) { for (const child of node) { const found = findButton(child, label); if (found) return found; } return null; }
    if (node.type === 'button' && [node.props?.children].flat(Infinity).join('') === label) return node;
    return findButton(node.props?.footer, label) || findButton(node.props?.children, label);
  };
  const trialReceipt = () => ({ ok: true, result: 'committed', receipt_ref: 'd'.repeat(32), replayed: false, warnings: [],
    data: { scenario_ref: scope.scenario_ref, draft_ref: scope.draft_ref, row_count: scope.task_count,
      official_plan: { plan_ref: ref(99), version: 1, kind: 'official', is_current_official: true, display_name: '正式计划 v1',
        baseline_ref: scope.baseline.plan_ref, completeness: 'complete',
        capabilities: { view: true, edit_draft: false, adopt: false, report_actual: true },
        blocked_reasons: [], source_scenario_ref: scope.scenario_ref, source_draft_ref: scope.draft_ref } } });
  const trialAdopts = [], trialHost = hooks(), trialData = { ...scope, status: 'saved', tasks_complete: true, tasks: [{}] };
  w.localStorage = storage();
  routes['POST /api/workbench/v1/trial/scenarios/*/adopt-preview'] = () => envelope({ ...trialScope, validation: { status: 'valid', can_adopt: true, issues: [] },
    write_context: { write_token: 'w'.repeat(32), expires_at: '2026-10-22T10:00:00', capabilities: { 'trial.scenario.adopt': true }, blocked_reasons: [] } }, { as_of: '2026-10-22T09:00:00' });
  routes['POST /api/workbench/v1/trial/scenarios/*/adopt'] = offline(trialAdopts);
  const renderTrial = () => trialHost.render(() => w.TrialAdoptionState.useSession({ scenarioRef: scope.scenario_ref, data: trialData, disabled: false, onAdopted() {} }));
  renderTrial(); trialHost.flush(); renderTrial().change({ reason: values.reason, declared_operator: values.declared_operator });
  await renderTrial().inspect(); renderTrial().setConsent(true);
  assert.equal(renderTrial().preview.data_context_ref, dataContext);
  await refused(renderTrial, noLocks, session => session.submit(), '当前浏览器不支持这项操作，请用 Chrome 打开。', trialAdopts);
  await refused(renderTrial, contended, session => session.submit(), '另一个页面正在处理这次采用，请先在那个页面点「查询结果」。', trialAdopts);
  w.navigator = granted; await renderTrial().submit(); assert.equal(trialAdopts.length, 1);
  assert.equal(renderTrial().error, w.WorkbenchTerms.outcomes.unknown('采用')); assert.equal(renderTrial().saved.phase, 'pending');
  w.localStorage = storage(); renderTrial().sync();
  routes['POST /api/workbench/v1/trial/scenarios/*/adopt'] = stale(() => { w.localStorage.failSet = quota; });
  renderTrial().change({ reason: values.reason, declared_operator: values.declared_operator });
  await renderTrial().inspect(); renderTrial().setConsent(true); await renderTrial().submit();
  assert.equal(renderTrial().saved.phase, 'rejected'); assert.equal(renderTrial().storageError, '本次采用未通过，但本机没能保存这次操作记录。');
  {
    const remountHost = hooks(), remounted = remountHost.render(() => w.TrialAdoptionState.useSession({ scenarioRef: scope.scenario_ref, data: trialData, disabled: false, onAdopted() {} }));
    remountHost.flush();
    assert.equal(remounted.saved.phase, 'rejected'); assert.equal(remounted.storageError, '本次采用未通过，但本机没能保存这次操作记录。');
    const dialog = remountHost.render(() => w.TrialAdoptionControls.Dialog({ session: remounted, scenarioRef: scope.scenario_ref, onNavigate() {}, name: '试调' }));
    assert.equal(Boolean(findButton(dialog, '结束本次未采用').props.disabled), false);
    remountHost.unmount();
  }
  w.localStorage.failSet = null;
  renderTrial().sync(); assert.equal(renderTrial().storageError, ''); assert.equal(renderTrial().saved.phase, 'rejected');
  assert.equal(JSON.parse(w.localStorage.data.get(w.TrialAdoptionState.KEY)).phase, 'rejected');
  renderTrial().finish(); assert.equal(renderTrial().saved, null); assert.equal(renderTrial().storageError, '');
  routes['POST /api/workbench/v1/trial/scenarios/*/adopt'] = () => { w.localStorage.failSet = quota; return trialReceipt(); };
  renderTrial().change({ reason: values.reason, declared_operator: values.declared_operator });
  await renderTrial().inspect(); renderTrial().setConsent(true); await renderTrial().submit();
  assert.equal(renderTrial().saved.phase, 'committed'); assert.equal(renderTrial().storageError, '已收到采用结果，但本机没能保存这次操作记录。');
  {
    const remountHost = hooks(), remounted = remountHost.render(() => w.TrialAdoptionState.useSession({ scenarioRef: scope.scenario_ref, data: trialData, disabled: false, onAdopted() {} }));
    remountHost.flush();
    assert.equal(remounted.saved.phase, 'committed'); assert.equal(remounted.storageError, '已收到采用结果，但本机没能保存这次操作记录。');
    const dialog = remountHost.render(() => w.TrialAdoptionControls.Dialog({ session: remounted, scenarioRef: scope.scenario_ref, onNavigate() {}, name: '试调' }));
    assert.equal(Boolean(findButton(dialog, '完成').props.disabled), false);
    remountHost.unmount();
  }
  w.localStorage.failSet = null;
  renderTrial().sync(); assert.equal(renderTrial().storageError, ''); assert.equal(renderTrial().saved.phase, 'committed');
  renderTrial().finish(); assert.equal(renderTrial().saved, null); assert.equal(renderTrial().storageError, '');
  trialHost.unmount();
  {
    const lookupHost = hooks(), renderLookup = () => lookupHost.render(() => w.TrialAdoptionState.useSession({ disabled: true, onAdopted() {} }));
    const otherTrial = { ...trialIntent, request_key: 'trial-adoption-' + 'd'.repeat(48) };
    const thirdTrial = { ...trialIntent, request_key: 'trial-adoption-' + 'e'.repeat(48) };
    let lookupGate = deferred();
    routes['GET /api/workbench/v1/trial/scenarios/*/adoption-commands/*'] = () => lookupGate.promise;
    w.localStorage = storage(); w.TrialAdoptionState.save(trialIntent, null);
    renderLookup(); lookupHost.flush();
    w.localStorage.data.set(w.TrialAdoptionState.KEY, JSON.stringify(otherTrial));
    w.dispatchEvent({ type: 'storage', key: w.TrialAdoptionState.KEY });
    lookupGate.resolve(envelope({ state: 'not_observed', receipt: null, may_be_in_flight: true, can_retry_automatically: false }, { as_of: '2026-10-22T09:00:00' }));
    await tick();
    let current = renderLookup();
    assert.equal(current.saved.request_key, otherTrial.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, '');
    lookupGate = deferred();
    const pendingError = current.lookup();
    w.localStorage.data.set(w.TrialAdoptionState.KEY, JSON.stringify(thirdTrial));
    w.dispatchEvent({ type: 'storage', key: w.TrialAdoptionState.KEY });
    lookupGate.reject(new Error('网络中断'));
    await pendingError;
    current = renderLookup();
    assert.equal(current.saved.request_key, thirdTrial.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, '');
    lookupHost.unmount();
    routes['GET /api/workbench/v1/trial/scenarios/*/adoption-commands/*'] = () => envelope(trialStatus(), { as_of: '2026-10-22T09:00:00' });
  }

  // Calibration adoption runs its real preview validator, so the fixture is a complete five-sample suggestion.
  const generated = '2026-10-22T09:00:00', templateRef = baseline.template_operation_ref, sampleRefs = [21, 22, 23, 24, 25].map(ref);
  const suggestion = { ...baseline, sample_count: 5, eligible_sample_count: 5, candidate_count: 5, excluded_count: 0, sample_refs: sampleRefs,
    sample_revisions: sampleRefs.map(sample_ref => ({ sample_ref, sample_revision: 'revision-' + sample_ref.slice(-2), template_revision: 1, report_revision_refs: [ref(30)] })),
    suggestion_ref: templateRef, operation_ref: templateRef };
  const samples = suggestion.sample_revisions.map(row => ({ ...row, execution_operation_ref: row.sample_ref, template_operation_ref: templateRef,
    lineage_evidence_ref: ref(31), selected: true, eligible: true, effective_processing_hours: 20, completed_quantity: 10, unit_hours: 2,
    unknown_record_count: 0, exclusion_reasons: [], reports: [] }));
  const calibrationInput = { reason: values.reason, declared_operator: values.declared_operator }, calibrationDetail = { suggestion };
  const calibrationPreview = envelope({ template_operation_ref: templateRef, suggestion, generated_at: generated, input: calibrationInput,
    effect_scope: 'future_template_use_only', samples, latest_adoption: null, validation: { can_adopt: true, issues: [] },
    write_context: { write_token: 'fixture', expires_at: '2026-10-22T09:15:00', capabilities: { 'calibration.adopt': true }, blocked_reasons: [] } },
  { as_of: generated, snapshot_ref: null });
  const CALIBRATION = '/api/workbench/v1/calibration/*', PREVIEW = 'POST ' + CALIBRATION + '/adopt-preview', ADOPT = 'POST ' + CALIBRATION + '/adopt',
    RECEIPT = 'GET ' + CALIBRATION + '/adopt/receipts/*';
  const calibrationAdopts = [], calibrationHost = hooks();
  routes[PREVIEW] = () => calibrationPreview; routes[ADOPT] = offline(calibrationAdopts);
  w.localStorage = storage();
  const renderCalibration = () => calibrationHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
  renderCalibration(); calibrationHost.flush(); renderCalibration().change(calibrationInput);
  await renderCalibration().inspect(); renderCalibration().setConsent(true);
  assert.equal(renderCalibration().preview.validation.can_adopt, true);
  await refused(renderCalibration, noLocks, session => session.submit(), '当前浏览器不支持这一步，请用 Chrome 打开后重试。', calibrationAdopts);
  await refused(renderCalibration, contended, session => session.submit(), '另一个页面正在采用，请先在那边查询结果。', calibrationAdopts);
  w.navigator = granted; await renderCalibration().submit(); assert.equal(calibrationAdopts.length, 1);
  assert.equal(calibrationAdopts[0].request_key, 'calibration-' + '05'.repeat(24));
  calibrationHost.unmount();

  // A precheck that lands after another page wrote a pending record cannot submit over it; a cross-page release clears the draft and error;
  // a receipt whose local write fails belongs to storageError, not to the adopt request's error.
  const calibrationKey = w.CalibrationAdoptionState.KEY, raceAdopts = [], raceHost = hooks();
  const calibrationReceipt = body => ({ ok: true, result: 'committed', receipt_ref: 'c'.repeat(32), replayed: false, warnings: [],
    data: { adoption_ref: ref(14), template_operation_ref: templateRef, request_key: body.request_key, reason: body.input.reason,
      declared_operator: body.input.declared_operator, confirmed: true, application_operator: '本机', adopted_at: generated, generated_at: generated,
      old_unit_hours: 1, new_unit_hours: 2, template_revision_before: 1, template_revision_after: 2, method_version: 'v1', sample_count: 5,
      sample_refs: sampleRefs, sample_revisions: suggestion.sample_revisions, effect_scope: 'future_template_use_only' } });
  const gate = deferred();
  routes[PREVIEW] = () => gate.promise.then(() => calibrationPreview);
  routes[RECEIPT] = () => { throw new Error('网络中断'); };
  routes[ADOPT] = offline(raceAdopts);
  w.localStorage = storage();
  const renderRace = () => raceHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
  renderRace(); raceHost.flush(); renderRace().change(calibrationInput);
  const precheck = renderRace().inspect(), otherPage = { ...sessions[3].value, request_key: 'calibration-' + 'b'.repeat(48) };
  w.localStorage.data.set(calibrationKey, JSON.stringify(otherPage)); w.dispatchEvent({ type: 'storage', key: calibrationKey });
  gate.resolve(); await precheck; renderRace().setConsent(true);
  let calibration = renderRace(); assert(calibration.preview && calibration.consent, 'The late precheck still lands after the other page wrote');
  await calibration.submit(); calibration = renderRace();
  assert.equal(calibration.saved.request_key, otherPage.request_key); assert.equal(calibration.storageError, ''); assert.equal(raceAdopts.length, 0); assert.deepEqual(w.localStorage.writes, []);
  raceHost.flush(); await tick();
  assert.equal(fetch.calls.at(-1).path, '/api/workbench/v1/calibration/' + templateRef + '/adopt/receipts/' + otherPage.request_key);
  assert.equal(renderRace().error, '上次操作的结果还没确认。无法连接本机服务，请确认应用仍在运行后重试。');
  w.localStorage.data.delete(calibrationKey); w.dispatchEvent({ type: 'storage', key: calibrationKey }); calibration = renderRace();
  assert.equal(calibration.saved, null); assert.equal(calibration.error, ''); assert.equal(calibration.preview, null);
  assert.equal(JSON.stringify(calibration.draft), JSON.stringify({ reason: '', declared_operator: '' }));
  routes[PREVIEW] = () => calibrationPreview;
  routes[ADOPT] = call => { raceAdopts.push(call.body); w.localStorage.failSet = quota; return calibrationReceipt(call.body); };
  renderRace().change(calibrationInput); await renderRace().inspect(); renderRace().setConsent(true); await renderRace().submit();
  calibration = renderRace(); assert.equal(raceAdopts.length, 1);
  assert.equal(calibration.storageError, '已收到采用结果，但本机没能保存这次操作记录。'); assert.equal(calibration.error, ''); assert.equal(calibration.saved.phase, 'committed');
  {
    const remountHost = hooks(), remounted = remountHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
    remountHost.flush();
    assert.equal(remounted.saved.phase, 'committed'); assert.equal(remounted.storageError, '已收到采用结果，但本机没能保存这次操作记录。');
    const dialog = remountHost.render(() => w.CalibrationAdoptionControls.Dialog({ session: remounted, detail: calibrationDetail, stale: false, onRefresh() {} }));
    assert.equal(Boolean(findButton(dialog, '完成').props.disabled), false);
    remountHost.unmount();
  }
  w.localStorage.failSet = null;
  calibration.sync(); calibration = renderRace();
  assert.equal(calibration.storageError, ''); assert.equal(calibration.saved.phase, 'committed');
  assert.equal(JSON.parse(w.localStorage.data.get(calibrationKey)).phase, 'committed');
  calibration.finish(); calibration = renderRace();
  assert.equal(calibration.saved, null); assert.equal(calibration.storageError, ''); assert.equal(w.localStorage.data.has(calibrationKey), false);
  routes[ADOPT] = stale(() => { w.localStorage.failSet = quota; });
  renderRace().change(calibrationInput); await renderRace().inspect(); renderRace().setConsent(true); await renderRace().submit();
  calibration = renderRace();
  assert.equal(calibration.storageError, '本次采用未通过，但本机没能保存这次操作记录。'); assert.equal(calibration.saved.phase, 'rejected');
  {
    const remountHost = hooks(), remounted = remountHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
    remountHost.flush();
    assert.equal(remounted.saved.phase, 'rejected'); assert.equal(remounted.storageError, '本次采用未通过，但本机没能保存这次操作记录。');
    const dialog = remountHost.render(() => w.CalibrationAdoptionControls.Dialog({ session: remounted, detail: calibrationDetail, stale: false, onRefresh() {} }));
    assert.equal(Boolean(findButton(dialog, '放弃上次采用记录').props.disabled), false);
    remountHost.unmount();
  }
  w.localStorage.failSet = null;
  calibration.sync(); calibration = renderRace();
  assert.equal(calibration.storageError, ''); assert.equal(calibration.saved.phase, 'rejected');
  assert.equal(JSON.parse(w.localStorage.data.get(calibrationKey)).phase, 'rejected');
  calibration.finish(); calibration = renderRace();
  assert.equal(calibration.saved, null); assert.equal(calibration.storageError, '');
  raceHost.unmount();
  {
    const lookupHost = hooks(), renderLookup = () => lookupHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
    const otherCalibration = { ...sessions[3].value, request_key: 'calibration-' + 'd'.repeat(48) };
    const thirdCalibration = { ...sessions[3].value, request_key: 'calibration-' + 'e'.repeat(48) };
    let lookupGate = deferred();
    routes[RECEIPT] = () => lookupGate.promise;
    w.localStorage = storage(); w.CalibrationAdoptionState.save(sessions[3].value, null);
    renderLookup(); lookupHost.flush();
    w.localStorage.data.set(calibrationKey, JSON.stringify(otherCalibration));
    w.dispatchEvent({ type: 'storage', key: calibrationKey });
    lookupGate.resolve(respond(failure('receipt_not_found', '没查到'), 404));
    await tick();
    let current = renderLookup();
    assert.equal(current.saved.request_key, otherCalibration.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, '');
    lookupGate = deferred();
    lookupHost.flush();
    w.localStorage.data.set(calibrationKey, JSON.stringify(thirdCalibration));
    w.dispatchEvent({ type: 'storage', key: calibrationKey });
    lookupGate.reject(new Error('网络中断'));
    await tick();
    current = renderLookup();
    assert.equal(current.saved.request_key, thirdCalibration.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, '');
    lookupGate = deferred();
    renderLookup(); lookupHost.flush();
    assert.equal(renderLookup().busy, true);
    w.localStorage.data.delete(calibrationKey);
    w.dispatchEvent({ type: 'storage', key: calibrationKey });
    renderLookup(); lookupHost.flush();
    current = renderLookup();
    assert.equal(current.saved, null);
    assert.equal(current.busy, false);
    lookupGate.resolve(respond(failure('receipt_not_found', '没查到'), 404));
    await tick();
    assert.equal(renderLookup().busy, false);
    lookupHost.unmount();
  }
  {
    const backing = storage(), prevLocal = Object.getOwnPropertyDescriptor(w, 'localStorage');
    let failGetter = false;
    Object.defineProperty(w, 'localStorage', { configurable: true, get() { if (failGetter) throw new Error('SecurityError'); return backing; }, set() {} });
    w.navigator = granted;
    routes['POST /api/workbench/v1/scheduling/candidates/*/adopt-preview'] = () => envelope({
      ...candidate, validation: { status: 'valid', can_adopt: true, issues: [] },
      write_context: { write_token: 'w'.repeat(32), expires_at: '2026-10-22T10:00:00', capabilities: { 'scheduling.candidate.adopt': true }, blocked_reasons: [] }
    }, { as_of: '2026-10-22T09:00:00' });
    routes['POST /api/workbench/v1/scheduling/candidates/*/adopt'] = stale(() => { failGetter = true; });
    try {
      const getterHost = hooks(), getterElement = w.RunAdoptionAction({ candidateRef: ref(10), candidateCatalog: [] });
      const renderGetter = () => getterHost.render(() => getterElement.type(getterElement.props));
      const getterDialog = () => renderGetter().props.children.find(child => child && child.type === 'dialog');
      renderGetter(); getterHost.flush();
      renderGetter().props.children[0].props.onClick();
      await tick();
      assert.equal(getterDialog().props.preview.validation.can_adopt, true);
      getterDialog().props.onChange(values);
      getterDialog().props.onConsent(true);
      await getterDialog().props.onConfirm();
      assert.equal(getterDialog().props.intent.phase, 'rejected');
      assert.equal(getterDialog().props.storageError, '读不到上次采用的操作记录，不要重新采用。');
      failGetter = false;
      getterDialog().props.onReadStorage();
      assert.equal(getterDialog().props.storageError, '');
      assert.equal(getterDialog().props.intent.phase, 'rejected');
      assert.equal(JSON.parse(backing.data.get(w.RunAdoptionAPI.PENDING_KEY)).phase, 'rejected');
      getterDialog().props.onCancelRejected();
      assert.equal(getterDialog(), undefined);
      assert.equal(backing.data.has(w.RunAdoptionAPI.PENDING_KEY), false);
      getterHost.unmount();
    } finally {
      if (prevLocal) Object.defineProperty(w, 'localStorage', prevLocal);
    }
  }
  {
    w.localStorage = storage();
    let lookupGate = deferred();
    routes['GET /api/workbench/v1/scheduling/candidates/*/adoption-commands/*'] = () => lookupGate.promise;
    const firstAdopt = w.RunAdoptionAPI.pending().begin(candidate, values, null);
    const secondAdopt = { ...firstAdopt, request_key: 'adoption-' + 'd'.repeat(48) };
    const thirdAdopt = { ...firstAdopt, request_key: 'adoption-' + 'e'.repeat(48) };
    const raceRunHost = hooks(), raceRunElement = w.RunAdoptionAction({ candidateRef: ref(10), candidateCatalog: [] });
    const renderRaceRun = () => raceRunHost.render(() => raceRunElement.type(raceRunElement.props));
    const raceRunDialog = () => renderRaceRun().props.children.find(child => child && child.type === 'dialog');
    renderRaceRun(); raceRunHost.flush();
    renderRaceRun().props.children[0].props.onClick();
    renderRaceRun(); raceRunHost.flush();
    w.localStorage.data.set(w.RunAdoptionAPI.PENDING_KEY, JSON.stringify(secondAdopt));
    w.dispatchEvent({ type: 'storage', key: w.RunAdoptionAPI.PENDING_KEY });
    lookupGate.resolve({ ok: true, result: 'not_recorded', request_key: firstAdopt.request_key, may_be_in_flight: false,
      resolution: 'context_replaced', data_context_ref: dataContext, message: '旧来源记录' });
    await tick();
    assert.equal(raceRunDialog().props.intent.request_key, secondAdopt.request_key);
    assert.equal(raceRunDialog().props.replacedInfo, null);
    assert.equal(raceRunDialog().props.error, '');
    lookupGate = deferred();
    renderRaceRun(); raceRunHost.flush();
    w.localStorage.data.set(w.RunAdoptionAPI.PENDING_KEY, JSON.stringify(thirdAdopt));
    w.dispatchEvent({ type: 'storage', key: w.RunAdoptionAPI.PENDING_KEY });
    lookupGate.reject(new Error('网络中断'));
    await tick();
    assert.equal(raceRunDialog().props.intent.request_key, thirdAdopt.request_key);
    assert.equal(raceRunDialog().props.error, '');
    assert.equal(raceRunDialog().props.replacedInfo, null);
    raceRunHost.unmount();
  }
  {
    const runControlsHost = hooks();
    const rejectedDialog = runControlsHost.render(() => realRunAdoptionControls.Dialog({
      value: candidate, intent: { ...adopted, phase: 'rejected' }, result: null, preview: null, candidateDisplay: null,
      draft: values, consent: true, busy: false, error: '采用未通过', storageError: '无法保存', notice: '', replacedInfo: null,
      onReadStorage() {}, onChange() {}, onConsent() {}, onClose() {}, onPreview() {}, onConfirm() {}, onLookup() {}, onFinish() {}, onCancelRejected() {}, onDismissReplaced() {}, onNavigate() {}
    }));
    assert.equal(Boolean(findButton(rejectedDialog, '结束本次未采用').props.disabled), false);
    const replacedDialog = runControlsHost.render(() => realRunAdoptionControls.Dialog({
      value: candidate, intent: { ...adopted, phase: 'pending' }, result: null, preview: null, candidateDisplay: null,
      draft: values, consent: true, busy: false, error: '', storageError: '无法保存', notice: '', replacedInfo: { reason: 'replaced' },
      onReadStorage() {}, onChange() {}, onConsent() {}, onClose() {}, onPreview() {}, onConfirm() {}, onLookup() {}, onFinish() {}, onCancelRejected() {}, onDismissReplaced() {}, onNavigate() {}
    }));
    assert.equal(Boolean(findButton(replacedDialog, '结束旧来源待确认记录').props.disabled), false);
    runControlsHost.unmount();
  }
  {
    w.navigator = granted;
    for (const outcome of ['rejected', 'committed']) {
      let calGate = deferred();
      routes[PREVIEW] = () => calibrationPreview;
      routes[ADOPT] = call => calGate.promise.then(() => outcome === 'committed' ? calibrationReceipt(call.body) : stale()());
      w.localStorage = storage();
      const calUnmountHost = hooks();
      const renderCalUnmount = () => calUnmountHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
      renderCalUnmount(); calUnmountHost.flush(); renderCalUnmount().change(calibrationInput);
      await renderCalUnmount().inspect(); renderCalUnmount().setConsent(true);
      const calSubmit = renderCalUnmount().submit();
      calUnmountHost.unmount();
      calGate.resolve();
      await calSubmit;
      assert.equal(JSON.parse(w.localStorage.data.get(calibrationKey)).phase, outcome);

      let trialGate = deferred();
      routes['POST /api/workbench/v1/trial/scenarios/*/adopt'] = () => trialGate.promise.then(() => outcome === 'committed' ? trialReceipt() : stale()());
      w.localStorage = storage();
      const trialUnmountHost = hooks();
      const renderTrialUnmount = () => trialUnmountHost.render(() => w.TrialAdoptionState.useSession({ scenarioRef: scope.scenario_ref, data: trialData, disabled: false, onAdopted() {} }));
      renderTrialUnmount(); trialUnmountHost.flush(); renderTrialUnmount().change({ reason: values.reason, declared_operator: values.declared_operator });
      await renderTrialUnmount().inspect(); renderTrialUnmount().setConsent(true);
      const trialSubmit = renderTrialUnmount().submit();
      trialUnmountHost.unmount();
      trialGate.resolve();
      await trialSubmit;
      assert.equal(JSON.parse(w.localStorage.data.get(w.TrialAdoptionState.KEY)).phase, outcome);
    }

    let runGate = deferred();
    routes['POST /api/workbench/v1/scheduling/candidates/*/adopt-preview'] = () => envelope({
      ...candidate, validation: { status: 'valid', can_adopt: true, issues: [] },
      write_context: { write_token: 'w'.repeat(32), expires_at: '2026-10-22T10:00:00', capabilities: { 'scheduling.candidate.adopt': true }, blocked_reasons: [] }
    }, { as_of: '2026-10-22T09:00:00' });
    routes['POST /api/workbench/v1/scheduling/candidates/*/adopt'] = () => runGate.promise.then(() => stale()());
    w.localStorage = storage();
    const runUnmountHost = hooks(), runUnmountElement = w.RunAdoptionAction({ candidateRef: ref(10), candidateCatalog: [] });
    const renderRunUnmount = () => runUnmountHost.render(() => runUnmountElement.type(runUnmountElement.props));
    const runUnmountDialog = () => renderRunUnmount().props.children.find(child => child && child.type === 'dialog');
    renderRunUnmount(); runUnmountHost.flush();
    renderRunUnmount().props.children[0].props.onClick();
    await tick();
    runUnmountDialog().props.onChange(values);
    runUnmountDialog().props.onConsent(true);
    const runSubmit = runUnmountDialog().props.onConfirm();
    runUnmountHost.unmount();
    runGate.resolve();
    await runSubmit;
    assert.equal(JSON.parse(w.localStorage.data.get(w.RunAdoptionAPI.PENDING_KEY)).phase, 'rejected');

    const candidateA = { ...candidate, candidate_ref: ref(5) }, crossCandPosts = [];
    w.localStorage = storage();
    const rejectedA = w.RunAdoptionAPI.pending().reject(w.RunAdoptionAPI.pending().begin(candidateA, values, null), gone);
    routes['POST /api/workbench/v1/scheduling/candidates/*/adopt-preview'] = call => envelope({
      ...candidateA, candidate_ref: call.path.split('/').at(-2), validation: { status: 'valid', can_adopt: true, issues: [] },
      write_context: { write_token: 'w'.repeat(32), expires_at: '2026-10-22T10:00:00', capabilities: { 'scheduling.candidate.adopt': true }, blocked_reasons: [] }
    }, { as_of: '2026-10-22T09:00:00' });
    routes['POST /api/workbench/v1/scheduling/candidates/*/adopt'] = call => {
      crossCandPosts.push(call);
      return {
        ok: true, result: 'committed', receipt_ref: 'f'.repeat(32), replayed: false, warnings: [],
        data: {
          candidate_ref: candidateA.candidate_ref, run_ref: candidateA.run_ref, row_count: candidateA.task_count,
          official_plan: {
            plan_ref: ref(98), version: 1, kind: 'official', is_current_official: true, display_name: '正式计划 v1',
            source_run_ref: candidateA.run_ref, baseline_ref: candidateA.baseline.plan_ref, completeness: 'complete',
            capabilities: { view: true, edit_draft: false, adopt: false, report_actual: true }, blocked_reasons: []
          }
        }
      };
    };
    const crossCandHost = hooks(), crossCandElement = w.RunAdoptionAction({ candidateRef: ref(6), candidateCatalog: [] });
    const renderCrossCand = () => crossCandHost.render(() => crossCandElement.type(crossCandElement.props));
    const crossCandDialog = () => renderCrossCand().props.children.find(child => child && child.type === 'dialog');
    renderCrossCand(); crossCandHost.flush();
    renderCrossCand().props.children[0].props.onClick();
    await crossCandDialog().props.onPreview();
    assert.equal(crossCandDialog().props.preview.candidate_ref, ref(5));
    crossCandDialog().props.onConsent(true);
    await crossCandDialog().props.onConfirm();
    assert.equal(crossCandPosts.length, 1);
    assert.equal(crossCandPosts[0].path, '/api/workbench/v1/scheduling/candidates/' + ref(5) + '/adopt');
    assert.equal(crossCandPosts[0].body.request_key, rejectedA.request_key);
    assert.equal(crossCandDialog().props.result.result, 'committed');
    crossCandDialog().props.onFinish();
    assert.equal(w.localStorage.data.has(w.RunAdoptionAPI.PENDING_KEY), false);
    crossCandHost.unmount();
  }

  const ITEM_COMMAND = 'POST /api/workbench/v1/dashboard/items/*/*', COMMAND_RECEIPT = 'GET /api/workbench/v1/commands/*';
  const dashboardCommands = [], commandLookups = [], dashboardHost = hooks();
  routes[ITEM_COMMAND] = offline(dashboardCommands);
  // web/routes/workbench/materials.py command_receipt: a receipt not yet recorded is an HTTP 200 "not_recorded" answer.
  routes[COMMAND_RECEIPT] = call => { commandLookups.push(call.path.split('/').at(-1));
    return { ok: true, state: 'not_recorded', receipt: null, may_be_in_flight: true, message: w.WorkbenchTerms.outcomes.pending('保存') }; };
  const dashboardItem = { item_ref: ref(9), subject: '风险', handling, source: {}, risk: {}, write_context: { write_token: 'fixture', capabilities: { transition: true } } };
  const handle = item => session => session.submit(item, 'transition', { target_status: 'following' });
  w.localStorage = storage();
  const renderDashboard = () => dashboardHost.render(() => w.DashboardSession.useCommand());
  renderDashboard(); dashboardHost.flush();
  await refused(renderDashboard, noLocks, handle(dashboardItem), '当前浏览器不支持，请用 Chrome 打开。', dashboardCommands);
  await refused(renderDashboard, contended, handle(dashboardItem), '另一个页面正在处置，这里没有开始新的处置。请先完成那边的处置。', dashboardCommands);
  await refused(renderDashboard, granted, handle({ ...dashboardItem, write_context: { write_token: 'fixture', capabilities: { transition: false } } }),
    '这条记录现在不能处置，请刷新后重试。', dashboardCommands);
  await handle(dashboardItem)(renderDashboard()); assert.equal(dashboardCommands.length, 1);
  assert.equal(fetch.calls.find(call => call.method === 'POST' && call.path.startsWith('/api/workbench/v1/dashboard/')).path,
    '/api/workbench/v1/dashboard/items/' + ref(9) + '/transition');
  // An unanswered command follows up once; a null lookup keeps the submit failure, while a manual click (its event is no flag) clears it.
  const notFound = '还是没有查到结果。请稍后再点「查询结果」，不要重复提交。';
  let dashboard = renderDashboard();
  assert.equal(dashboard.error.message, unknownOutcome); assert.equal(dashboard.error.committed, 'unknown');
  assert.equal(dashboard.notice, notFound); assert.equal(dashboard.saved.phase, 'pending');
  assert.deepEqual(commandLookups, [dashboardCommands[0].request_key]);
  await dashboard.lookup({ currentTarget: {}, preventDefault() {} }); dashboard = renderDashboard();
  assert.equal(dashboard.error, null); assert.equal(dashboard.notice, notFound); assert.equal(commandLookups.length, 2);
  dashboardHost.unmount();
  // A receipt whose local write fails is a storage failure; an explicit rejection, even one whose local update fails, never looks the command up.
  async function dashboardRun(handler, clearFailSet = true) {
    const host = hooks(), render = () => host.render(() => w.DashboardSession.useCommand());
    routes[ITEM_COMMAND] = handler; w.localStorage = storage(); render(); host.flush(); await handle(dashboardItem)(render());
    if (clearFailSet) { w.localStorage.failSet = null; w.localStorage.failGet = null; }
    const session = render(); host.unmount(); return session;
  }
  const dashboardReceipt = call => ({ ok: true, result: 'committed', receipt_ref: 'b'.repeat(32), replayed: false, warnings: [],
    data: { item_ref: ref(9), refresh_required: true, handling: w.DashboardContract.expected({ action: 'transition', input: call.body.input, before: handling }),
      source: {}, risk: {}, history_ref: ref(13) } });
  dashboard = await dashboardRun(call => { w.localStorage.failSet = quota; return dashboardReceipt(call); }, false);
  assert.equal(dashboard.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。'); assert.equal(dashboard.error, null); assert.equal(dashboard.saved.phase, 'confirmed');
  const remountHost = hooks(), renderRemount = () => remountHost.render(() => w.DashboardSession.useCommand());
  let remounted = renderRemount(); remountHost.flush();
  assert.equal(remounted.saved.phase, 'confirmed'); assert.equal(remounted.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。');
  assert.equal(remounted.finish(), true); remounted = renderRemount();
  assert.equal(remounted.saved, null); assert.equal(remounted.storageError, null); assert.equal(w.localStorage.data.has(w.DashboardSession.KEY), false);
  w.localStorage.failSet = null; remountHost.unmount();
  dashboard = await dashboardRun(call => { w.localStorage.failSet = quota; return dashboardReceipt(call); });
  assert.equal(dashboard.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。'); assert.equal(dashboard.error, null); assert.equal(dashboard.saved.phase, 'confirmed');
  dashboard.sync(); assert.equal(JSON.parse(w.localStorage.data.get(w.DashboardSession.KEY)).phase, 'confirmed');
  assert.equal(dashboard.finish(), true); assert.equal(w.localStorage.data.has(w.DashboardSession.KEY), false);
  dashboard = await dashboardRun(stale());
  assert.equal(dashboard.saved.phase, 'rejected'); assert.equal(dashboard.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(dashboard.storageError, null);
  dashboard = await dashboardRun(stale(() => { w.localStorage.failSet = quota; }));
  assert.equal(dashboard.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。'); assert.equal(dashboard.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(dashboard.saved.phase, 'rejected');
  dashboard.sync(); assert.equal(JSON.parse(w.localStorage.data.get(w.DashboardSession.KEY)).phase, 'rejected');
  assert.equal(dashboard.finish(), true); assert.equal(w.localStorage.data.has(w.DashboardSession.KEY), false);
  dashboard = await dashboardRun(stale(() => { w.localStorage.failGet = new Error('getItem unavailable'); }), false);
  assert.equal(dashboard.storageError.message, '上次操作记录读不出来，不能开始新的处置。请重新打开页面。'); assert.equal(dashboard.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(dashboard.saved.phase, 'rejected');
  {
    const remountFailGetHost = hooks(), remountedFailGet = remountFailGetHost.render(() => w.DashboardSession.useCommand());
    remountFailGetHost.flush();
    assert.equal(remountedFailGet.saved.phase, 'rejected');
    assert.equal(remountedFailGet.storageError.message, '上次操作记录读不出来，不能开始新的处置。请重新打开页面。');
    remountFailGetHost.unmount();
  }
  w.localStorage.failGet = null;
  dashboard.sync(); assert.equal(JSON.parse(w.localStorage.data.get(w.DashboardSession.KEY)).phase, 'rejected');
  assert.equal(dashboard.finish(), true); assert.equal(w.localStorage.data.has(w.DashboardSession.KEY), false);
  {
    const backing = storage(), prevLocal = Object.getOwnPropertyDescriptor(w, 'localStorage');
    let failGetter = false;
    Object.defineProperty(w, 'localStorage', { configurable: true, get() { if (failGetter) throw new Error('SecurityError'); return backing; }, set() {} });
    try {
      const getterHost = hooks(), renderGetter = () => getterHost.render(() => w.DashboardSession.useCommand());
      routes[ITEM_COMMAND] = stale(() => { failGetter = true; });
      renderGetter(); getterHost.flush(); await handle(dashboardItem)(renderGetter());
      const getterSession = renderGetter();
      assert.equal(getterSession.saved.phase, 'rejected');
      assert.equal(getterSession.storageError.message, '上次操作记录读不出来，不能开始新的处置。请重新打开页面。');
      failGetter = false;
      getterSession.sync();
      assert.equal(JSON.parse(backing.data.get(w.DashboardSession.KEY)).phase, 'rejected');
      assert.equal(getterSession.finish(), true);
      assert.equal(backing.data.has(w.DashboardSession.KEY), false);
      getterHost.unmount();
    } finally {
      if (prevLocal) Object.defineProperty(w, 'localStorage', prevLocal);
    }
  }
  assert.equal(commandLookups.length, 2);
  // A late receipt or rejection after another tab replaced the pending record must not overwrite the newer tab's state in memory.
  const otherDashboard = { ...sessions[0].value, request_key: 'dashboard-' + 'd'.repeat(48) };
  dashboard = await dashboardRun(call => { w.localStorage.data.set(w.DashboardSession.KEY, JSON.stringify(otherDashboard)); return dashboardReceipt(call); });
  assert.equal(dashboard.saved.request_key, otherDashboard.request_key); assert.equal(dashboard.saved.phase, 'pending');
  assert.equal(dashboard.storageError.message, '上次操作已在另一个页面变化，这里没有覆盖它。请刷新后重试。');
  dashboard = await dashboardRun(stale(() => { w.localStorage.data.set(w.DashboardSession.KEY, JSON.stringify(otherDashboard)); }));
  assert.equal(dashboard.saved.request_key, otherDashboard.request_key); assert.equal(dashboard.saved.phase, 'pending');
  assert.equal(dashboard.error, null); assert.equal(dashboard.storageError.message, '上次操作已在另一个页面变化，这里没有覆盖它。请刷新后重试。');
  // Late lookup() null-result or error after another tab replaced request_key must not overwrite notice or error of the new request.
  {
    const lookupHost = hooks(), renderLookup = () => lookupHost.render(() => w.DashboardSession.useCommand());
    let lookupGate = deferred();
    routes[COMMAND_RECEIPT] = () => lookupGate.promise;
    w.localStorage = storage(); w.DashboardSession.save(sessions[0].value, null);
    renderLookup(); lookupHost.flush();
    w.localStorage.data.set(w.DashboardSession.KEY, JSON.stringify(otherDashboard));
    w.dispatchEvent({ type: 'storage', key: w.DashboardSession.KEY });
    lookupGate.resolve({ ok: true, state: 'not_recorded', receipt: null, may_be_in_flight: true, message: w.WorkbenchTerms.outcomes.pending('保存') });
    await tick();
    let current = renderLookup();
    assert.equal(current.saved.request_key, otherDashboard.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, null);
    lookupGate = deferred();
    const pendingLookup = current.lookup();
    const thirdDashboard = { ...sessions[0].value, request_key: 'dashboard-' + 'e'.repeat(48) };
    w.localStorage.data.set(w.DashboardSession.KEY, JSON.stringify(thirdDashboard));
    w.dispatchEvent({ type: 'storage', key: w.DashboardSession.KEY });
    lookupGate.reject(new Error('网络中断'));
    await pendingLookup;
    current = renderLookup();
    assert.equal(current.saved.request_key, thirdDashboard.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, null);
    lookupHost.unmount();
    routes[COMMAND_RECEIPT] = call => { commandLookups.push(call.path.split('/').at(-1));
      return { ok: true, state: 'not_recorded', receipt: null, may_be_in_flight: true, message: w.WorkbenchTerms.outcomes.pending('保存') }; };
  }

  // Outsourcing checks the lock before it reads the preview.
  const RECEIPT_COMMAND = 'POST /api/workbench/v1/outsourcing/receipts', outsourcingCommands = [], outsourcingHost = hooks();
  routes[RECEIPT_COMMAND] = offline(outsourcingCommands);
  w.localStorage = storage();
  const renderOutsourcing = () => outsourcingHost.render(() => w.OutsourcingSession.useCommand());
  renderOutsourcing(); outsourcingHost.flush();
  await refused(renderOutsourcing, noLocks, session => session.submit({}), '当前浏览器不支持，请用 Chrome 打开。', outsourcingCommands);
  await refused(renderOutsourcing, contended, session => session.submit({}), '另一个页面有还没确认的外协登记，请先在那里点「查询结果」。', outsourcingCommands);
  outsourcingHost.unmount();
  // The precheck validates the preview before the page holds any record: an unconfirmable answer writes and sends nothing.
  const outsourcingInput = sessions[1].value.input;
  const outsourcingPreview = envelope({ input: outsourcingInput, target, before: null, after, outsourcing_ref: null, can_confirm: true,
    write_context: { write_token: 'fixture', capabilities: { confirm: true } },
    execution: { automatically_reported: false, operation_refs: target.operation_refs, service: 'WorkbenchProductionReportService', reason: '回厂仍需报工' } },
  { snapshot_ref: null, as_of: '2026-10-10T08:00:00' });
  routes['POST /api/workbench/v1/outsourcing/receipts/preview'] = () => ({ ...outsourcingPreview, data: { ...outsourcingPreview.data, can_confirm: false } });
  w.localStorage = storage();
  const precheckFailure = await w.OutsourcingContract.preview(outsourcingInput).then(() => assert.fail('An unconfirmable preview is not accepted'), error => error);
  assert.equal(Object.prototype.toString.call(precheckFailure), '[object Error]');
  assert.deepEqual(w.localStorage.writes, []); assert.equal(outsourcingCommands.length, 0);
  routes['POST /api/workbench/v1/outsourcing/receipts/preview'] = () => outsourcingPreview;
  const checkedPreview = await w.OutsourcingContract.preview(outsourcingInput);
  assert.equal(JSON.stringify(checkedPreview), JSON.stringify(outsourcingPreview));
  assert.equal(JSON.stringify(fetch.calls.at(-1).body), JSON.stringify({ input: outsourcingInput }));
  // An unanswered registration follows up once and keeps its failure; a rejection whose local release fails is a storage failure without a lookup.
  commandLookups.length = 0; w.navigator = granted;
  async function outsourcingRun(handler) {
    const host = hooks(), render = () => host.render(() => w.OutsourcingSession.useCommand());
    routes[RECEIPT_COMMAND] = handler; w.localStorage = storage(); render(); host.flush(); await render().submit(checkedPreview);
    w.localStorage.failRemove = null; const session = render(); host.unmount(); return session;
  }
  let outsourcing = await outsourcingRun(offline(outsourcingCommands));
  assert.equal(outsourcing.error.message, unknownOutcome); assert.equal(outsourcing.notice, notFound); assert.equal(outsourcing.saved.phase, 'pending');
  assert.deepEqual(commandLookups, [outsourcing.saved.request_key]);
  outsourcing = await outsourcingRun(stale());
  assert.equal(outsourcing.saved, null); assert.equal(outsourcing.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(outsourcing.storageError, null);
  outsourcing = await outsourcingRun(stale(() => { w.localStorage.failRemove = new Error('removeItem unavailable'); }));
  assert.equal(outsourcing.storageError.message, '上次操作记录保存不了，不能开始登记。请重新打开页面。'); assert.equal(outsourcing.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(outsourcing.saved, null);
  outsourcing.sync(); assert.equal(w.localStorage.data.has(w.OutsourcingSession.KEY), false);
  assert.equal(commandLookups.length, 1); delete w.navigator;
  // Late lookup() null-result or error after another tab replaced request_key in OutsourcingSession must not overwrite notice or error.
  {
    const lookupHost = hooks(), renderLookup = () => lookupHost.render(() => w.OutsourcingSession.useCommand());
    const otherOutsourcing = { ...sessions[1].value, request_key: 'outsourcing-' + 'd'.repeat(48) };
    const thirdOutsourcing = { ...sessions[1].value, request_key: 'outsourcing-' + 'e'.repeat(48) };
    let lookupGate = deferred();
    routes[COMMAND_RECEIPT] = () => lookupGate.promise;
    w.localStorage = storage(); w.OutsourcingSession.save(sessions[1].value, null);
    renderLookup(); lookupHost.flush();
    w.localStorage.data.set(w.OutsourcingSession.KEY, JSON.stringify(otherOutsourcing));
    w.dispatchEvent({ type: 'storage', key: w.OutsourcingSession.KEY });
    lookupGate.resolve({ ok: true, state: 'not_recorded', receipt: null, may_be_in_flight: true, message: w.WorkbenchTerms.outcomes.pending('保存') });
    await tick();
    let current = renderLookup();
    assert.equal(current.saved.request_key, otherOutsourcing.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, null);
    lookupGate = deferred();
    const pendingLookup = current.lookup();
    w.localStorage.data.set(w.OutsourcingSession.KEY, JSON.stringify(thirdOutsourcing));
    w.dispatchEvent({ type: 'storage', key: w.OutsourcingSession.KEY });
    lookupGate.reject(new Error('网络中断'));
    await pendingLookup;
    current = renderLookup();
    assert.equal(current.saved.request_key, thirdOutsourcing.request_key);
    assert.equal(current.notice, ''); assert.equal(current.error, null);
    lookupHost.unmount();
  }
  {
    const outsourcingReceipt = () => ({ ok: true, result: 'committed', receipt_ref: 'e'.repeat(32), replayed: false, warnings: [],
      data: { ...after, outsourcing_ref: ref(15), fact_ref: ref(16), target, declared_operator: outsourcingInput.declared_operator,
        reason: outsourcingInput.reason, local_operator: '本机', confirmed_at: '2026-10-10T08:00:00', refresh_required: true,
        execution: outsourcingPreview.data.execution } });
    // Unmounting while waiting for navigator.locks.request does not send a POST or write a pending record when the lock callback runs.
    let lockGate;
    w.navigator = { locks: { request: (_key, _options, fn) => { lockGate = deferred(); return lockGate.promise.then(() => fn({})); } } };
    const lockPosts = [];
    routes[PREVIEW] = () => calibrationPreview;
    routes[ADOPT] = call => { lockPosts.push(call); return calibrationReceipt(call.body); };
    routes[ITEM_COMMAND] = call => { lockPosts.push(call); return dashboardReceipt(call); };
    routes[RECEIPT_COMMAND] = call => { lockPosts.push(call); return outsourcingReceipt(); };

    w.localStorage = storage();
    const calLockHost = hooks(), renderCalLock = () => calLockHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
    renderCalLock(); calLockHost.flush(); renderCalLock().change(calibrationInput);
    await renderCalLock().inspect(); renderCalLock().setConsent(true);
    const calLockSubmit = renderCalLock().submit();
    calLockHost.unmount();
    lockGate.resolve();
    await calLockSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);

    // Switching template or scenario while staying mounted and waiting for navigator.locks.request does not submit the old preview.
    w.localStorage = storage();
    let activeCalDetail = calibrationDetail;
    const calSwitchHost = hooks(), renderCalSwitch = () => calSwitchHost.render(() => w.CalibrationAdoptionState.useSession({ detail: activeCalDetail, stale: false }));
    renderCalSwitch(); calSwitchHost.flush(); renderCalSwitch().change(calibrationInput);
    await renderCalSwitch().inspect(); renderCalSwitch().setConsent(true);
    const calSwitchSubmit = renderCalSwitch().submit();
    activeCalDetail = { suggestion: { ...suggestion, template_operation_ref: ref(63), suggestion_ref: ref(63), operation_ref: ref(63) } };
    renderCalSwitch(); calSwitchHost.flush();
    assert.equal(renderCalSwitch().preview, null);
    lockGate.resolve();
    await calSwitchSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);
    calSwitchHost.unmount();

    routes['POST /api/workbench/v1/trial/scenarios/*/adopt'] = call => { lockPosts.push(call); return trialReceipt(); };
    w.localStorage = storage();
    let activeScenarioRef = scope.scenario_ref, activeTrialData = trialData;
    const trialSwitchHost = hooks(), renderTrialSwitch = () => trialSwitchHost.render(() => w.TrialAdoptionState.useSession({ scenarioRef: activeScenarioRef, data: activeTrialData, disabled: false, onAdopted() {} }));
    renderTrialSwitch(); trialSwitchHost.flush(); renderTrialSwitch().change({ reason: values.reason, declared_operator: values.declared_operator });
    await renderTrialSwitch().inspect(); renderTrialSwitch().setConsent(true);
    const trialSwitchSubmit = renderTrialSwitch().submit();
    activeScenarioRef = ref(64); activeTrialData = { ...trialData, scenario_ref: ref(64) };
    renderTrialSwitch(); trialSwitchHost.flush();
    assert.equal(renderTrialSwitch().preview, null);
    lockGate.resolve();
    await trialSwitchSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);
    trialSwitchHost.unmount();

    // Cross-tab storage updates arriving before React flushes a re-render while waiting for navigator.locks.request invalidate the pending submit.
    w.localStorage = storage();
    const otherCalRejected = { ...sessions[3].value, phase: 'rejected', request_key: 'calibration-' + 'c'.repeat(48),
      baseline: { ...baseline, template_operation_ref: ref(63) } };
    const calStorageHost = hooks(), renderCalStorage = () => calStorageHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false }));
    renderCalStorage(); calStorageHost.flush(); renderCalStorage().change(calibrationInput);
    await renderCalStorage().inspect(); renderCalStorage().setConsent(true);
    const calStorageSubmit = renderCalStorage().submit();
    w.localStorage.data.set(calibrationKey, JSON.stringify(otherCalRejected));
    w.dispatchEvent({ type: 'storage', key: calibrationKey });
    lockGate.resolve();
    await calStorageSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);
    assert.equal(JSON.parse(w.localStorage.data.get(calibrationKey)).request_key, otherCalRejected.request_key);
    calStorageHost.unmount();

    w.localStorage = storage();
    const otherTrialRejected = { ...trialIntent, phase: 'rejected', request_key: 'trial-adoption-' + 'c'.repeat(48) };
    const trialStorageHost = hooks(), renderTrialStorage = () => trialStorageHost.render(() => w.TrialAdoptionState.useSession({ scenarioRef: scope.scenario_ref, data: trialData, disabled: false, onAdopted() {} }));
    renderTrialStorage(); trialStorageHost.flush(); renderTrialStorage().change({ reason: values.reason, declared_operator: values.declared_operator });
    await renderTrialStorage().inspect(); renderTrialStorage().setConsent(true);
    const trialStorageSubmit = renderTrialStorage().submit();
    w.localStorage.data.set(w.TrialAdoptionState.KEY, JSON.stringify(otherTrialRejected));
    w.dispatchEvent({ type: 'storage', key: w.TrialAdoptionState.KEY });
    lockGate.resolve();
    await trialStorageSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);
    assert.equal(JSON.parse(w.localStorage.data.get(w.TrialAdoptionState.KEY)).request_key, otherTrialRejected.request_key);
    trialStorageHost.unmount();

    routes['POST /api/workbench/v1/scheduling/candidates/*/adopt'] = call => { lockPosts.push(call); return stale()(); };
    w.localStorage = storage();
    const otherRunRejected = { ...adopted, phase: 'rejected', request_key: 'adoption-' + 'c'.repeat(48) };
    const runStorageHost = hooks(), runStorageElement = w.RunAdoptionAction({ candidateRef: ref(10), candidateCatalog: [] });
    const renderRunStorage = () => runStorageHost.render(() => runStorageElement.type(runStorageElement.props));
    const runStorageDialog = () => renderRunStorage().props.children.find(child => child && child.type === 'dialog');
    renderRunStorage(); runStorageHost.flush();
    renderRunStorage().props.children[0].props.onClick();
    await tick();
    runStorageDialog().props.onChange(values);
    runStorageDialog().props.onConsent(true);
    const runStorageSubmit = runStorageDialog().props.onConfirm();
    w.localStorage.data.set(w.RunAdoptionAPI.PENDING_KEY, JSON.stringify(otherRunRejected));
    w.dispatchEvent({ type: 'storage', key: w.RunAdoptionAPI.PENDING_KEY });
    lockGate.resolve();
    await runStorageSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);
    assert.equal(JSON.parse(w.localStorage.data.get(w.RunAdoptionAPI.PENDING_KEY)).request_key, otherRunRejected.request_key);
    runStorageHost.unmount();

    w.localStorage = storage();
    const dashLockHost = hooks(), renderDashLock = () => dashLockHost.render(() => w.DashboardSession.useCommand());
    renderDashLock(); dashLockHost.flush();
    const dashLockSubmit = handle(dashboardItem)(renderDashLock());
    dashLockHost.unmount();
    lockGate.resolve();
    await dashLockSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);

    w.localStorage = storage();
    const outLockHost = hooks(), renderOutLock = () => outLockHost.render(() => w.OutsourcingSession.useCommand());
    renderOutLock(); outLockHost.flush();
    const outLockSubmit = renderOutLock().submit(checkedPreview);
    outLockHost.unmount();
    lockGate.resolve();
    await outLockSubmit;
    assert.deepEqual(w.localStorage.writes, []);
    assert.equal(lockPosts.length, 0);

    // Unmounting DashboardSession and OutsourcingSession while command is in flight still saves the terminal outcome to localStorage.
    w.navigator = granted;
    for (const outcome of ['confirmed', 'rejected']) {
      let dashGate = deferred();
      routes[ITEM_COMMAND] = call => dashGate.promise.then(() => outcome === 'confirmed' ? dashboardReceipt(call) : stale()());
      w.localStorage = storage();
      const dashUnmountHost = hooks(), renderDashUnmount = () => dashUnmountHost.render(() => w.DashboardSession.useCommand());
      renderDashUnmount(); dashUnmountHost.flush();
      const dashSubmit = handle(dashboardItem)(renderDashUnmount());
      assert.equal(JSON.parse(w.localStorage.data.get(w.DashboardSession.KEY)).phase, 'pending');
      dashUnmountHost.unmount();
      dashGate.resolve();
      await dashSubmit;
      assert.equal(JSON.parse(w.localStorage.data.get(w.DashboardSession.KEY)).phase, outcome);

      let outGate = deferred();
      routes[RECEIPT_COMMAND] = () => outGate.promise.then(() => outcome === 'confirmed' ? outsourcingReceipt() : stale()());
      w.localStorage = storage();
      const outUnmountHost = hooks(), renderOutUnmount = () => outUnmountHost.render(() => w.OutsourcingSession.useCommand());
      renderOutUnmount(); outUnmountHost.flush();
      const outSubmit = renderOutUnmount().submit(checkedPreview);
      assert.equal(JSON.parse(w.localStorage.data.get(w.OutsourcingSession.KEY)).phase, 'pending');
      outUnmountHost.unmount();
      outGate.resolve();
      await outSubmit;
      if (outcome === 'confirmed') assert.equal(JSON.parse(w.localStorage.data.get(w.OutsourcingSession.KEY)).phase, 'confirmed');
      else assert.equal(w.localStorage.data.has(w.OutsourcingSession.KEY), false);
    }
    delete w.navigator;
  }
  // APSResourceSession preserves terminal rejected state across APSResourceAPI.create(namespace) remounts when clearPending fails.
  {
    w.sessionStorage = storage();
    routes['POST /api/workbench/v1/entities/machine/*/update'] = stale(() => { w.sessionStorage.failRemove = new Error('removeItem unavailable'); });
    const resHost1 = hooks(), adapter1 = w.APSResourceAPI.create('resources');
    const renderRes1 = () => resHost1.render(() => w.APSResourceSession.useCommand(adapter1));
    renderRes1(); resHost1.flush();
    await renderRes1().submit('machine', 'update', ref(50), { write_token: 'w'.repeat(32) }, { fields: {} });
    const cmd1 = renderRes1();
    assert.equal(cmd1.phase, 'rejected');
    assert.equal(cmd1.error.message, '结果已确认，但上次操作记录没清掉；重新打开页面后可以再点「查询结果」。');
    resHost1.unmount();
    const resHost2 = hooks(), adapter2 = w.APSResourceAPI.create('resources');
    const renderRes2 = () => resHost2.render(() => w.APSResourceSession.useCommand(adapter2));
    let cmd2 = renderRes2(); resHost2.flush(); cmd2 = renderRes2();
    assert.equal(cmd2.phase, 'rejected');
    assert.equal(cmd2.intent.request_key, cmd1.intent.request_key);
    w.sessionStorage.failRemove = null;
    assert.equal(cmd2.reset(), true);
    cmd2 = renderRes2();
    assert.equal(cmd2.phase, 'idle');
    assert.equal(w.sessionStorage.data.has(adapter2.pendingKey), false);
    resHost2.unmount();

    routes['POST /api/workbench/v1/process/parts/create'] = stale(() => { w.sessionStorage.failRemove = new Error('removeItem unavailable'); });
    const procHost1 = hooks(), procAdapter1 = w.APSProcessAPI.create();
    const renderProc1 = () => procHost1.render(() => w.APSResourceSession.useCommand(procAdapter1));
    renderProc1(); procHost1.flush();
    await renderProc1().submit('process', 'create', null, { write_token: 'w'.repeat(32) }, { fields: {} });
    const procCmd1 = renderProc1();
    assert.equal(procCmd1.phase, 'rejected');
    procHost1.unmount();
    w.sessionStorage.failGet = new Error('getItem unavailable');
    const procHost2 = hooks(), procAdapter2 = w.APSProcessAPI.create();
    const renderProc2 = () => procHost2.render(() => w.APSResourceSession.useCommand(procAdapter2));
    let procCmd2 = renderProc2(); procHost2.flush(); procCmd2 = renderProc2();
    assert.equal(procCmd2.phase, 'rejected');
    assert.equal(procCmd2.intent.request_key, procCmd1.intent.request_key);
    w.sessionStorage.failGet = null; w.sessionStorage.failRemove = null;
    assert.equal(procCmd2.reset(), true);
    assert.equal(renderProc2().phase, 'idle');
    assert.equal(w.sessionStorage.data.has(procAdapter2.pendingKey), false);
    procHost2.unmount();

    routes['POST /api/workbench/v1/entities/batch/create'] = stale(() => { w.sessionStorage.failRemove = new Error('removeItem unavailable'); });
    const batchHost1 = hooks(), batchAdapter1 = w.APSBatchAPI.create();
    const renderBatch1 = () => batchHost1.render(() => w.APSResourceSession.useCommand(batchAdapter1));
    renderBatch1(); batchHost1.flush();
    await renderBatch1().submit('batch', 'create', null, { write_token: 'w'.repeat(32) }, { fields: {} });
    const batchCmd1 = renderBatch1();
    assert.equal(batchCmd1.phase, 'rejected');
    batchHost1.unmount();
    w.sessionStorage.failGet = new Error('getItem unavailable');
    const batchHost2 = hooks(), batchAdapter2 = w.APSBatchAPI.create();
    const renderBatch2 = () => batchHost2.render(() => w.APSResourceSession.useCommand(batchAdapter2));
    let batchCmd2 = renderBatch2(); batchHost2.flush(); batchCmd2 = renderBatch2();
    assert.equal(batchCmd2.phase, 'rejected');
    assert.equal(batchCmd2.intent.request_key, batchCmd1.intent.request_key);
    w.sessionStorage.failGet = null; w.sessionStorage.failRemove = null;
    assert.equal(batchCmd2.reset(), true);
    assert.equal(renderBatch2().phase, 'idle');
    assert.equal(w.sessionStorage.data.has(batchAdapter2.pendingKey), false);
    batchHost2.unmount();

    w.sessionStorage = storage();
    routes['POST /api/workbench/v1/entities/machine/*/update'] = offline([]);
    routes['GET /api/workbench/v1/commands/*'] = () => ({ ok: true, state: 'not_recorded', receipt: null, may_be_in_flight: true, message: w.WorkbenchTerms.outcomes.pending('保存') });
    const pendHost1 = hooks(), pendAdapter1 = w.APSResourceAPI.create('resources');
    const renderPend1 = () => pendHost1.render(() => w.APSResourceSession.useCommand(pendAdapter1));
    renderPend1(); pendHost1.flush();
    await renderPend1().submit('machine', 'update', ref(50), { write_token: 'w'.repeat(32) }, { fields: {} });
    const pendCmd1 = renderPend1();
    assert.equal(pendCmd1.phase, 'pending');
    assert.ok(pendCmd1.intent && pendCmd1.intent.request_key);
    pendHost1.unmount();
    w.sessionStorage.failGet = new Error('getItem unavailable');
    const pendHost2 = hooks(), pendAdapter2 = w.APSResourceAPI.create('resources');
    const renderPend2 = () => pendHost2.render(() => w.APSResourceSession.useCommand(pendAdapter2));
    let pendCmd2 = renderPend2(); pendHost2.flush(); pendCmd2 = renderPend2();
    assert.equal(pendCmd2.phase, 'pending');
    assert.equal(pendCmd2.intent.request_key, pendCmd1.intent.request_key);
    w.sessionStorage.failGet = null;
    routes['GET /api/workbench/v1/commands/*'] = call => ({ ok: true, result: 'committed', receipt_ref: 'b'.repeat(32), replayed: false, warnings: [],
      data: { ref: ref(50), request_key: call.path.split('/').at(-1) } });
    await pendCmd2.check();
    pendCmd2 = renderPend2();
    assert.equal(pendCmd2.phase, 'done');
    assert.equal(pendCmd2.reset(), true);
    pendHost2.unmount();

    const prevDesc = Object.getOwnPropertyDescriptor(w, 'sessionStorage');
    const backingSession = storage();
    let failSessionGetter = false;
    Object.defineProperty(w, 'sessionStorage', { configurable: true, get() { if (failSessionGetter) throw new Error('SecurityError'); return backingSession; }, set() {} });
    try {
      routes['POST /api/workbench/v1/entities/machine/*/update'] = stale(() => { failSessionGetter = true; });
      const secRejHost1 = hooks(), secRejAdapter1 = w.APSResourceAPI.create('resources');
      const renderSecRej1 = () => secRejHost1.render(() => w.APSResourceSession.useCommand(secRejAdapter1));
      renderSecRej1(); secRejHost1.flush();
      await renderSecRej1().submit('machine', 'update', ref(50), { write_token: 'w'.repeat(32) }, { fields: {} });
      const secRejCmd1 = renderSecRej1();
      assert.equal(secRejCmd1.phase, 'rejected');
      secRejHost1.unmount();

      const secRejHost2 = hooks(), secRejAdapter2 = w.APSResourceAPI.create('resources');
      const renderSecRej2 = () => secRejHost2.render(() => w.APSResourceSession.useCommand(secRejAdapter2));
      let secRejCmd2 = renderSecRej2(); secRejHost2.flush(); secRejCmd2 = renderSecRej2();
      assert.equal(secRejCmd2.phase, 'rejected');
      assert.equal(secRejCmd2.intent.request_key, secRejCmd1.intent.request_key);
      failSessionGetter = false;
      assert.equal(secRejCmd2.reset(), true);
      assert.equal(renderSecRej2().phase, 'idle');
      assert.equal(backingSession.data.has(secRejAdapter2.pendingKey), false);
      secRejHost2.unmount();

      failSessionGetter = true;
      const secHost = hooks(), secAdapter = w.APSResourceAPI.create('resources');
      const secCmd = secHost.render(() => w.APSResourceSession.useCommand(secAdapter));
      secHost.flush();
      assert.equal(secCmd.phase, 'pending');
      assert.equal(secCmd.error.message, '读不到上次操作记录，请重新打开页面；暂时不能继续保存。');
      secHost.unmount();
    } finally {
      if (prevDesc) Object.defineProperty(w, 'sessionStorage', prevDesc);
    }
  }

  // Viewing preferences merges the current stored patch once; reset publishes known defaults to peer hooks.
  w.localStorage = storage(); const V = w.TrialViewState, data = { draft_ref: ref(12), scope: {} }, viewTarget = V.identity(data), initial = V.defaults(data);
  reset(); const preference = V.write(viewTarget, initial, { query: '零件' }); assert.equal(counters.reads, 1); assert.equal(counters.parses, 0);
  reset(); V.write(viewTarget, initial, { mode: 'operator' }); assert.equal(counters.reads, 1); assert.equal(counters.parses, 1);
  assert.equal(V.read(viewTarget).query, preference.query); assert.equal(V.read(viewTarget).mode, 'operator');
  const first = hooks(), peer = hooks(); let view = first.render(() => V.useView(data)); first.flush();
  peer.render(() => V.useView(data)); peer.flush(); reset(); view.reset();
  assert.equal(counters.reads, 0); assert.equal(counters.parses, 0);
  assert.equal(JSON.stringify(first.render(() => V.useView(data)).value), JSON.stringify(initial));
  assert.equal(JSON.stringify(peer.render(() => V.useView(data)).value), JSON.stringify(initial));
  w.localStorage.failSet = quota; view = first.render(() => V.useView(data)); assert.equal(view.change({ query: '未保存' }), false);
  view = first.render(() => V.useView(data)); assert.equal(view.value.query, '未保存'); assert.equal(view.pending, true); assert.equal(view.error.code, 'write_unavailable');
  w.localStorage.failSet = null; view.reload(); assert.equal(V.read(viewTarget).query, '未保存');
  w.localStorage.failRemove = new Error('removeItem unavailable'); assert.throws(() => V.clear(viewTarget), error => error.code === 'clear_unavailable');
  assert.equal(V.read(viewTarget).query, '未保存'); w.localStorage.failRemove = null;
  w.localStorage.data.set(V.key(viewTarget), '{broken'); assert.throws(() => V.write(viewTarget, initial, {}), error => error.code === 'corrupt_preferences');
  first.unmount(); peer.unmount();
  console.log(JSON.stringify({ compiled_sources: names.length, sessions: sessionCounts, synchronous_write_post_reads: 0,
    local_event_reads_and_revalidation: 0, preference_reset_reads: 0, quota_remove_errors_and_late_pending_preserved: true }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
