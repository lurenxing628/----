'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const names = ['WorkbenchTerms.js', 'DashboardContract.js', 'OutsourcingContract.js', 'TrialContract.js', 'TrialAdoptionAPI.js', 'CalibrationAdoptionAPI.js',
  'DashboardSession.js', 'OutsourcingSession.js', 'TrialAdoptionState.js', 'CalibrationAdoptionState.js', 'RunAdoptionAPI.js', 'RunAdoptionAction.jsx',
  'RunJobAPI.js', 'SystemMaintenanceAPI.js', 'TrialAPI.js', 'TrialViewState.js'];
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: names.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })), check_combined: true });
const listeners = new Map(), events = [], counters = { reads: 0, parses: 0, validations: 0 };
const json = Object.create(JSON); json.parse = value => { counters.parses++; return JSON.parse(value); };
const w = vm.createContext({ console, JSON: json, URLSearchParams, AbortController, setTimeout, clearTimeout,
  crypto: { getRandomValues: bytes => { bytes.fill(5); return bytes; } }, CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } } });
w.window = w; w.fetch = () => { throw new Error('Unexpected network request'); };
w.WorkbenchHandlerMemory = { read: () => ({ value: '经办人' }), write() {} }; w.WorkbenchGuards = { useDirtyGuard() {} };
w.RunAdoptionControls = { Button: 'button', Dialog: 'dialog' };
w.addEventListener = (type, fn) => { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); };
w.removeEventListener = (type, fn) => listeners.get(type)?.delete(fn);
w.dispatchEvent = event => { events.push(event); for (const fn of listeners.get(event.type) || []) fn(event); };
for (const item of compiled.outputs) vm.runInContext(item.code, w, { filename: item.path });
const ref = value => value.toString(16).padStart(48, '0'), values = { confirm: true, reason: '核对实际安排', declared_operator: '经办人' };
function storage() {
  const data = new Map(), writes = [];
  return { data, writes, failSet: null, failRemove: null,
    getItem(key) { counters.reads++; return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { writes.push(['set', key]); if (this.failSet) throw this.failSet; data.set(key, value); },
    removeItem(key) { writes.push(['remove', key]); if (this.failRemove) throw this.failRemove; data.delete(key); } };
}
const reset = () => { counters.reads = counters.parses = counters.validations = 0; };
function hooks() {
  let cursor = 0; const slots = [], effects = [];
  const same = (a, b) => a && b && a.length === b.length && a.every((value, index) => value === b[index]);
  const memo = (fn, deps) => { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() }; return slots[i].value; };
  const React = { createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
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
  reset(); const intent = pending.begin(inputRef); assert.equal(counters.reads, 1); assert.equal(counters.parses, 0);
  reset(); const attached = pending.attach(intent, ref(1)); assert.equal(counters.reads, 1); assert.equal(counters.parses, 1);
  reset(); pending.finish(attached, 'found'); assert.equal(counters.reads, 1); assert.equal(counters.parses, 1);
  assert.deepEqual(runStore.writes.slice(-2), [['set', w.RunJobAPI.RECENT_KEY], ['remove', w.RunJobAPI.PENDING_KEY]]);
  assert.equal(pending.read(), null); assert.equal(pending.recent().resolution, 'found');
  const retry = pending.begin(inputRef), quota = new Error('QuotaExceededError'); runStore.failSet = quota;
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
  runStore.data.set(w.RunJobAPI.PENDING_KEY, JSON.stringify(intent)); assert.equal(pending.read().request_key, intent.request_key, 'Cold legacy pending restores');

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
  const baseline = { template_operation_ref: ref(7), template_revision: 1, template_snapshot: 'captured-template', part_ref: ref(8), part_no: 'P1', part_name: '零件',
    sequence: 1, operation_label: '车削', source: 'internal', old_unit_hours: 1, suggested_unit_hours: 2, sample_count: 0, eligible_sample_count: 0,
    candidate_count: 0, excluded_count: 0, sample_refs: [], sample_revisions: [], exclusion_reasons: [], method_version: 'v1' };
  const sessions = [
    { name: 'DashboardSession', contract: 'DashboardContract', leaf: 'expected', mount: module => module.useCommand({}),
      value: { version: 1, request_key: 'dashboard-' + 'a'.repeat(48), phase: 'pending', item_ref: ref(9), action: 'transition', input: { target_status: 'following' }, before: handling, source: {}, risk: {} } },
    { name: 'OutsourcingSession', contract: 'OutsourcingContract', leaf: 'facts', mount: module => module.useCommand({}),
      value: { version: 1, request_key: 'outsourcing-' + 'a'.repeat(48), phase: 'pending', input: { ...after, target: w.OutsourcingContract.target(target), declared_operator: values.declared_operator, reason: values.reason }, after, target } },
    { name: 'TrialAdoptionState', contract: 'TrialAdoptionAPI', leaf: 'overview', mount: module => module.useSession({ disabled: true, onAdopted() {} }),
      value: { schema_version: 1, request_key: 'trial-adoption-' + 'a'.repeat(48), phase: 'pending', scenario_ref: scope.scenario_ref, preview: scope, input: values } },
    { name: 'CalibrationAdoptionState', contract: 'CalibrationAdoptionAPI', leaf: 'binding', mount: module => module.useSession({ detail: null, stale: true, adapter: {} }),
      value: { version: 1, request_key: 'calibration-' + 'a'.repeat(48), phase: 'pending', baseline, input: values } }
  ];
  const sessionCounts = {};
  for (const row of sessions) {
    const module = w[row.name], contract = w[row.contract], leaf = contract[row.leaf], host = hooks(); w.localStorage = storage();
    contract[row.leaf] = (...args) => { counters.validations++; return leaf(...args); };
    const session = host.render(() => row.mount(module)); host.flush(); reset();
    assert.equal(module.save(row.value, null), row.value); assert.equal(events.at(-1).detail, row.value);
    assert.deepEqual(counters, { reads: 1, parses: 0, validations: 1 }); sessionCounts[row.name] = { ...counters };
    reset(); w.dispatchEvent(events.at(-1)); assert.deepEqual(counters, { reads: 0, parses: 0, validations: 0 });
    w.dispatchEvent({ type: 'storage', key: module.KEY }); assert.deepEqual(counters, { reads: 1, parses: 1, validations: 1 });
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
  const dataContext = JSON.stringify({ database_scope: '/plans/试调 & 正式.db', successful_restores: ['e'.repeat(32)] });
  const trialScope = trialAPI.overview({ ...scope, data_context_ref: dataContext });
  assert.equal(trialScope.data_context_ref, dataContext); assert.equal(trialAPI.overview(scope).data_context_ref, null);
  const trialIntent = { ...sessions[2].value, preview: trialScope }, trialRequests = [];
  let mayBeInFlight = true;
  const trialStatus = () => ({ state: 'not_observed', receipt: null, may_be_in_flight: mayBeInFlight, can_retry_automatically: false });
  const trialFetch = async (url, options) => {
    trialRequests.push({ url: new URL(url, 'http://localhost'), options });
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ ok: true, schema_version: 1,
      data: trialStatus(), warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local',
        snapshot_ref: 's'.repeat(32), as_of: '2026-10-22T09:00:00' } }) };
  };
  const trialTransport = trialAPI.create(trialFetch);
  assert.equal(JSON.stringify(await trialTransport.lookup(trialIntent, undefined, { data_context_ref: dataContext })), JSON.stringify(trialStatus()));
  assert.equal(trialRequests.at(-1).url.pathname, '/api/workbench/v1/trial/scenarios/' + scope.scenario_ref + '/adoption-commands/' + trialIntent.request_key);
  assert.equal(trialRequests.at(-1).url.searchParams.get('data_context_ref'), dataContext); assert.equal(trialRequests.at(-1).options.method, 'GET');
  await trialTransport.lookup(trialIntent); assert.equal(trialRequests.at(-1).url.searchParams.has('data_context_ref'), false);
  mayBeInFlight = false;
  assert.equal(JSON.stringify(await trialTransport.lookup(trialIntent, undefined, { data_context_ref: dataContext })), JSON.stringify(trialStatus()));

  const originalFetch = w.fetch, trialOverview = trialAPI.overview, recoveryHost = hooks(); w.localStorage = storage(); w.fetch = trialFetch;
  const recovery = recoveryHost.render(() => trialState.useSession({ disabled: true, onAdopted() {} })); recoveryHost.flush();
  trialAPI.overview = (...args) => { counters.validations++; return trialOverview(...args); };
  trialState.save(trialIntent, null); const savedTrial = w.localStorage.data.get(trialState.KEY), savedEvents = events.length, savedWrites = w.localStorage.writes.length;
  mayBeInFlight = true; reset(); await recovery.lookup();
  assert.deepEqual(counters, { reads: 0, parses: 1, validations: 0 }, 'An in-flight lookup only validates its outgoing data source');
  assert.equal(trialRequests.at(-1).url.searchParams.get('data_context_ref'), dataContext);
  assert.equal(w.localStorage.data.get(trialState.KEY), savedTrial); assert.equal(w.localStorage.writes.length, savedWrites); assert.equal(events.length, savedEvents);
  reset(); w.dispatchEvent(events.at(-1)); assert.deepEqual(counters, { reads: 0, parses: 0, validations: 0 });
  mayBeInFlight = false; reset(); await recovery.lookup();
  assert.deepEqual(counters, { reads: 1, parses: 3, validations: 1 }, 'Clearing reads PENDING once; JSON parsing covers the outgoing context, stored intent, and stored context');
  assert.equal(w.localStorage.data.has(trialState.KEY), false); assert.equal(events.at(-1).detail, null);
  assert.equal(recoveryHost.render(() => trialState.useSession({ disabled: true, onAdopted() {} })).saved, null);
  reset(); w.dispatchEvent(events.at(-1)); assert.deepEqual(counters, { reads: 0, parses: 0, validations: 0 });
  recoveryHost.unmount(); trialAPI.overview = trialOverview; w.fetch = originalFetch;

  w.localStorage = storage(); const adoptionHost = hooks();
  const element = w.RunAdoptionAction({ candidateRef: ref(10), adapter: {} });
  adoptionHost.render(() => element.type(element.props)); adoptionHost.flush();
  const candidate = { candidate_ref: ref(10), run_ref: ref(11), baseline: { plan_ref: null, version: null }, task_count: 1, scope_complete: true };
  const validIntent = w.RunAdoptionAPI.validIntent; let localValidations = 0;
  w.RunAdoptionAPI.validIntent = value => { localValidations++; return validIntent(value); };
  reset(); const adopted = w.RunAdoptionAPI.pending().begin(candidate, values);
  assert.equal(counters.reads, 1); assert.equal(counters.parses, 0); assert.equal(localValidations, 0, 'RunAdoptionAction consumes the verified local event');
  assert.equal(events.at(-1).detail, adopted);
  assert.equal(w.RunAdoptionAPI.pending().read().request_key, adopted.request_key); adoptionHost.unmount(); w.RunAdoptionAPI.validIntent = validIntent;
  // A definitive 404 non-commit (the candidate is gone) releases PENDING like the other adoption transports.
  const missingCandidate = w.RunAdoptionAPI.create(async () => ({ ok: false, status: 404, headers: { get: () => 'application/json' },
    json: async () => ({ ok: false, committed: false, error: { code: 'entity_not_found', message: '所选候选方案已不存在。', fields: [], retryable: false, request_ref: '1'.repeat(32) } }) }));
  const gone = await missingCandidate.adopt(adopted, 'w'.repeat(32)).then(() => assert.fail('A missing candidate is not adopted'), error => error);
  assert.equal(gone.message, '所选候选方案已不存在。'); assert.equal(w.RunAdoptionAPI.isRejected(gone), true);
  assert.equal(w.RunAdoptionAPI.pending().reject(adopted, gone).phase, 'rejected');
  // A record cleared elsewhere returns the draft to the remembered-handler default and drops the stale lookup error.
  w.localStorage = storage(); const runHost = hooks(), runElement = w.RunAdoptionAction({ candidateRef: ref(10), adapter: {} });
  const renderRun = () => runHost.render(() => runElement.type(runElement.props)), runDialog = () => renderRun().props.children.find(child => child && child.type === 'dialog');
  renderRun(); runHost.flush(); w.RunAdoptionAPI.pending().begin(candidate, values);
  renderRun().props.children[0].props.onClick(); renderRun(); runHost.flush();
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
  const trialAdopts = [], trialHost = hooks(), trialData = { ...scope, status: 'saved', tasks_complete: true, tasks: [{}] }, fetchBeforeLocks = w.fetch;
  w.localStorage = storage();
  w.fetch = async url => {
    if (url.endsWith('/adopt')) { trialAdopts.push(url); throw new Error('网络中断'); }
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ ok: true, schema_version: 1, warnings: [],
      meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: 's'.repeat(32), as_of: '2026-10-22T09:00:00' },
      data: { ...scope, validation: { status: 'valid', can_adopt: true, issues: [] },
        write_context: { write_token: 'w'.repeat(32), expires_at: '2026-10-22T10:00:00', capabilities: { 'trial.scenario.adopt': true }, blocked_reasons: [] } } }) };
  };
  const renderTrial = () => trialHost.render(() => w.TrialAdoptionState.useSession({ scenarioRef: scope.scenario_ref, data: trialData, disabled: false, onAdopted() {} }));
  renderTrial(); trialHost.flush(); renderTrial().change({ reason: values.reason, declared_operator: values.declared_operator });
  await renderTrial().inspect(); renderTrial().setConsent(true);
  await refused(renderTrial, noLocks, session => session.submit(), '当前浏览器不支持这项操作，请用 Chrome 打开。', trialAdopts);
  await refused(renderTrial, contended, session => session.submit(), '另一个页面正在处理这次采用，请先在那个页面点「查询结果」。', trialAdopts);
  w.navigator = granted; await renderTrial().submit(); assert.equal(trialAdopts.length, 1);
  trialHost.unmount(); w.fetch = fetchBeforeLocks;

  const calibrationAdopts = [], calibrationHost = hooks(), calibrationDetail = { suggestion: baseline };
  const calibrationInput = { reason: values.reason, declared_operator: values.declared_operator };
  const calibrationAdapter = { preview: async () => ({ suggestion: baseline, input: calibrationInput, validation: { can_adopt: true }, write_context: { write_token: 'fixture' } }),
    adopt: async intent => { calibrationAdopts.push(intent); throw new Error('网络中断'); } };
  w.localStorage = storage();
  const renderCalibration = () => calibrationHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false, adapter: calibrationAdapter }));
  renderCalibration(); calibrationHost.flush(); renderCalibration().change(calibrationInput);
  await renderCalibration().inspect(); renderCalibration().setConsent(true);
  await refused(renderCalibration, noLocks, session => session.submit(), '当前浏览器不支持这一步，请用 Chrome 打开后重试。', calibrationAdopts);
  await refused(renderCalibration, contended, session => session.submit(), '另一个页面正在采用，请先在那边查询结果。', calibrationAdopts);
  w.navigator = granted; await renderCalibration().submit(); assert.equal(calibrationAdopts.length, 1);
  calibrationHost.unmount();

  // A precheck that lands after another page wrote a pending record cannot submit over it; a cross-page release clears the draft and error;
  // a receipt whose local write fails belongs to storageError, not to the adopt request's error.
  const calibrationKey = w.CalibrationAdoptionState.KEY, raceAdopts = [], raceHost = hooks(), tick = () => new Promise(resolve => setTimeout(resolve, 0));
  const calibrationPreview = { suggestion: baseline, input: calibrationInput, validation: { can_adopt: true }, write_context: { write_token: 'fixture' } };
  const calibrationReceipt = intent => ({ ok: true, result: 'committed', receipt_ref: 'c'.repeat(32), replayed: false, warnings: [],
    data: { adoption_ref: ref(14), template_operation_ref: baseline.template_operation_ref, request_key: intent.request_key, reason: intent.input.reason,
      declared_operator: intent.input.declared_operator, confirmed: true, application_operator: '本机', adopted_at: '2026-10-22T09:00:00', generated_at: '2026-10-22T09:00:00',
      old_unit_hours: 1, new_unit_hours: 2, template_revision_before: 1, template_revision_after: 2, method_version: 'v1', sample_count: 0, sample_refs: [], sample_revisions: [],
      effect_scope: 'future_template_use_only' } });
  let releasePreview;
  const raceAdapter = { preview: () => new Promise(resolve => { releasePreview = () => resolve(calibrationPreview); }), lookup: async () => { throw new Error('网络中断'); },
    adopt: async intent => { raceAdopts.push(intent); throw new Error('网络中断'); } };
  w.localStorage = storage();
  const renderRace = () => raceHost.render(() => w.CalibrationAdoptionState.useSession({ detail: calibrationDetail, stale: false, adapter: raceAdapter }));
  renderRace(); raceHost.flush(); renderRace().change(calibrationInput);
  const precheck = renderRace().inspect(), otherPage = { ...sessions[3].value, request_key: 'calibration-' + 'b'.repeat(48) };
  w.localStorage.data.set(calibrationKey, JSON.stringify(otherPage)); w.dispatchEvent({ type: 'storage', key: calibrationKey });
  releasePreview(); await precheck; renderRace().setConsent(true);
  let calibration = renderRace(); assert(calibration.preview && calibration.consent, 'The late precheck still lands after the other page wrote');
  await calibration.submit(); calibration = renderRace();
  assert.equal(calibration.saved.request_key, otherPage.request_key); assert.equal(calibration.storageError, ''); assert.equal(raceAdopts.length, 0); assert.deepEqual(w.localStorage.writes, []);
  raceHost.flush(); await tick(); assert.equal(renderRace().error, '上次操作的结果还没确认。网络中断');
  w.localStorage.data.delete(calibrationKey); w.dispatchEvent({ type: 'storage', key: calibrationKey }); calibration = renderRace();
  assert.equal(calibration.saved, null); assert.equal(calibration.error, ''); assert.equal(calibration.preview, null);
  assert.equal(JSON.stringify(calibration.draft), JSON.stringify({ reason: '', declared_operator: '' }));
  raceAdapter.preview = async () => calibrationPreview;
  raceAdapter.adopt = async intent => { raceAdopts.push(intent); w.localStorage.failSet = quota; return calibrationReceipt(intent); };
  renderRace().change(calibrationInput); await renderRace().inspect(); renderRace().setConsent(true); await renderRace().submit(); w.localStorage.failSet = null;
  calibration = renderRace(); assert.equal(raceAdopts.length, 1);
  assert.equal(calibration.storageError, '无法保存这次采用操作的记录，没有开始新的采用。'); assert.equal(calibration.error, ''); assert.equal(calibration.saved.phase, 'pending');
  raceHost.unmount();

  const dashboardCommands = [], dashboardLookups = [], dashboardHost = hooks();
  const dashboardAPI = { command: async original => { dashboardCommands.push(original); throw new Error('网络中断'); },
    lookup: async original => { dashboardLookups.push(original); return null; } };
  const dashboardItem = { item_ref: ref(9), subject: '风险', handling, source: {}, risk: {}, write_context: { write_token: 'fixture', capabilities: { transition: true } } };
  const handle = item => session => session.submit(item, 'transition', { target_status: 'following' });
  w.localStorage = storage();
  const renderDashboard = () => dashboardHost.render(() => w.DashboardSession.useCommand(dashboardAPI));
  renderDashboard(); dashboardHost.flush();
  await refused(renderDashboard, noLocks, handle(dashboardItem), '当前浏览器不支持，请用 Chrome 打开。', dashboardCommands);
  await refused(renderDashboard, contended, handle(dashboardItem), '另一个页面正在处置，这里没有开始新的处置。请先完成那边的处置。', dashboardCommands);
  await refused(renderDashboard, granted, handle({ ...dashboardItem, write_context: { write_token: 'fixture', capabilities: { transition: false } } }),
    '这条记录现在不能处置，请刷新后重试。', dashboardCommands);
  await handle(dashboardItem)(renderDashboard()); assert.equal(dashboardCommands.length, 1);
  // An unanswered command follows up once; a null lookup keeps the submit failure, while a manual click (its event is no flag) clears it.
  const notFound = '还是没有查到结果。请稍后再点「查询结果」，不要重复提交。';
  let dashboard = renderDashboard();
  assert.equal(dashboard.error.message, '网络中断'); assert.equal(dashboard.notice, notFound); assert.equal(dashboard.saved.phase, 'pending');
  assert.deepEqual(dashboardLookups.map(intent => intent.request_key), [dashboardCommands[0].request_key]);
  await dashboard.lookup({ currentTarget: {}, preventDefault() {} }); dashboard = renderDashboard();
  assert.equal(dashboard.error, null); assert.equal(dashboard.notice, notFound); assert.equal(dashboardLookups.length, 2);
  dashboardHost.unmount();
  // A receipt whose local write fails is a storage failure; an explicit rejection, even one whose local update fails, never looks the command up.
  const rejectedFetch = (before = () => {}) => async () => { before(); return { ok: false, status: 409, headers: { get: () => 'application/json' },
    json: async () => ({ ok: false, committed: false, error: { code: 'stale_write', message: '来源资料已变化，请刷新后重试。', fields: [] } }) }; };
  async function dashboardRun(command) {
    const host = hooks(), api = { command, lookup: dashboardAPI.lookup }, render = () => host.render(() => w.DashboardSession.useCommand(api));
    w.localStorage = storage(); render(); host.flush(); await handle(dashboardItem)(render()); w.localStorage.failSet = null;
    const session = render(); host.unmount(); return session;
  }
  const dashboardReceipt = intent => ({ ok: true, result: 'committed', receipt_ref: 'b'.repeat(32), replayed: false, warnings: [],
    data: { item_ref: intent.item_ref, refresh_required: true, handling: w.DashboardContract.expected(intent), source: intent.source, risk: intent.risk, history_ref: ref(13) } });
  dashboard = await dashboardRun(async intent => { w.localStorage.failSet = quota; return dashboardReceipt(intent); });
  assert.equal(dashboard.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。'); assert.equal(dashboard.error, null); assert.equal(dashboard.saved.phase, 'pending');
  dashboard = await dashboardRun(w.DashboardContract.create(rejectedFetch()).command);
  assert.equal(dashboard.saved.phase, 'rejected'); assert.equal(dashboard.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(dashboard.storageError, null);
  dashboard = await dashboardRun(w.DashboardContract.create(rejectedFetch(() => { w.localStorage.failSet = quota; })).command);
  assert.equal(dashboard.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。'); assert.equal(dashboard.error, null); assert.equal(dashboard.saved.phase, 'pending');
  assert.equal(dashboardLookups.length, 2);

  // Outsourcing checks the lock before it reads the preview.
  const outsourcingCommands = [], outsourcingHost = hooks();
  w.localStorage = storage();
  const renderOutsourcing = () => outsourcingHost.render(() => w.OutsourcingSession.useCommand({ command: async () => { outsourcingCommands.push(1); }, lookup: async () => null }));
  renderOutsourcing(); outsourcingHost.flush();
  await refused(renderOutsourcing, noLocks, session => session.submit({}), '当前浏览器不支持，请用 Chrome 打开。', outsourcingCommands);
  await refused(renderOutsourcing, contended, session => session.submit({}), '另一个页面有还没确认的外协登记，请先在那里点「查询结果」。', outsourcingCommands);
  // A failed precheck has not touched localStorage: an operation error, nothing written or sent.
  const outsourcingPreview = { ok: true, schema_version: 1, warnings: [], meta: { source: 'production', time_basis: 'factory_local', snapshot_ref: null, as_of: '2026-10-10T08:00:00' },
    data: { input: sessions[1].value.input, target, before: null, after, outsourcing_ref: null, can_confirm: true, write_context: { write_token: 'fixture', capabilities: { confirm: true } },
      execution: { automatically_reported: false, operation_refs: target.operation_refs, service: 'WorkbenchProductionReportService', reason: '回厂仍需报工' } } };
  const unconfirmable = { ...outsourcingPreview, data: { ...outsourcingPreview.data, can_confirm: false } }; let precheckFailure;
  assert.throws(() => w.OutsourcingContract.preview(unconfirmable, unconfirmable.data.input), error => { precheckFailure = error.message; return true; });
  await refused(renderOutsourcing, granted, session => session.submit(unconfirmable), precheckFailure, outsourcingCommands);
  outsourcingHost.unmount();
  // An unanswered registration follows up once and keeps its failure; a rejection whose local release fails is a storage failure without a lookup.
  const outsourcingLookups = [], outsourcingAPI = { lookup: async intent => { outsourcingLookups.push(intent); return null; } };
  async function outsourcingRun(command) {
    const host = hooks(), render = () => host.render(() => w.OutsourcingSession.useCommand(outsourcingAPI));
    outsourcingAPI.command = command; w.localStorage = storage(); render(); host.flush(); await render().submit(outsourcingPreview);
    w.localStorage.failRemove = null; const session = render(); host.unmount(); return session;
  }
  let outsourcing = await outsourcingRun(async () => { throw new Error('网络中断'); });
  assert.equal(outsourcing.error.message, '网络中断'); assert.equal(outsourcing.notice, notFound); assert.equal(outsourcing.saved.phase, 'pending');
  assert.deepEqual(outsourcingLookups.map(intent => intent.request_key), [outsourcing.saved.request_key]);
  outsourcing = await outsourcingRun(w.OutsourcingContract.create(rejectedFetch()).command);
  assert.equal(outsourcing.saved, null); assert.equal(outsourcing.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(outsourcing.storageError, null);
  outsourcing = await outsourcingRun(w.OutsourcingContract.create(rejectedFetch(() => { w.localStorage.failRemove = new Error('removeItem unavailable'); })).command);
  assert.equal(outsourcing.storageError.message, '上次操作记录保存不了，不能开始登记。请重新打开页面。'); assert.equal(outsourcing.error, null); assert.equal(outsourcing.saved.phase, 'pending');
  assert.equal(outsourcingLookups.length, 1); delete w.navigator;

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
