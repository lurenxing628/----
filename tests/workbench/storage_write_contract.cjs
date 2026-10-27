'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const { routeFetch, envelope, failure, json: respond, deferred, browser } = require('./route_fetch.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const names = ['WorkbenchTerms.js', 'transport.js', 'DashboardContract.js', 'OutsourcingContract.js', 'TrialContract.js', 'TrialAdoptionAPI.js', 'CalibrationAdoptionAPI.js',
  'DashboardSession.js', 'OutsourcingSession.js', 'TrialAdoptionState.js', 'CalibrationAdoptionState.js', 'RunAdoptionAPI.js', 'RunAdoptionAction.jsx',
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
w.WorkbenchHandlerMemory = { read: () => ({ value: '经办人' }), write() {} }; w.WorkbenchGuards = { useDirtyGuard() {} };
w.RunAdoptionControls = { Button: 'button', Dialog: 'dialog' };
w.addEventListener = (type, fn) => { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); };
w.removeEventListener = (type, fn) => listeners.get(type)?.delete(fn);
w.dispatchEvent = event => { events.push(event); for (const fn of listeners.get(event.type) || []) fn(event); };
for (const item of compiled.outputs) vm.runInContext(item.code, w, { filename: item.path });
const ref = value => value.toString(16).padStart(48, '0'), values = { confirm: true, reason: '核对实际安排', declared_operator: '经办人' };
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
// An unanswered write: the transport turns it into the single "result unknown" error.
const offline = log => call => { log.push(call.body); throw new Error('网络中断'); };
const unknownOutcome = w.WorkbenchTerms.outcomes.pending('操作');
function storage() {
  const data = new Map(), writes = [];
  return { data, writes, failSet: null, failRemove: null,
    getItem(key) { counters.reads++; return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { writes.push(['set', key]); if (this.failSet) throw this.failSet; data.set(key, value); },
    removeItem(key) { writes.push(['remove', key]); if (this.failRemove) throw this.failRemove; data.delete(key); } };
}
const reset = () => { counters.reads = counters.parses = counters.validations = 0; contextParses = 0; };
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
  trialHost.unmount();

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
  renderRace().change(calibrationInput); await renderRace().inspect(); renderRace().setConsent(true); await renderRace().submit(); w.localStorage.failSet = null;
  calibration = renderRace(); assert.equal(raceAdopts.length, 1);
  assert.equal(calibration.storageError, '无法保存这次采用操作的记录，没有开始新的采用。'); assert.equal(calibration.error, ''); assert.equal(calibration.saved.phase, 'pending');
  raceHost.unmount();

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
  const stale = (before = () => {}) => () => { before(); return respond(failure('stale_write', '来源资料已变化，请刷新后重试。'), 409); };
  async function dashboardRun(handler) {
    const host = hooks(), render = () => host.render(() => w.DashboardSession.useCommand());
    routes[ITEM_COMMAND] = handler; w.localStorage = storage(); render(); host.flush(); await handle(dashboardItem)(render()); w.localStorage.failSet = null;
    const session = render(); host.unmount(); return session;
  }
  const dashboardReceipt = call => ({ ok: true, result: 'committed', receipt_ref: 'b'.repeat(32), replayed: false, warnings: [],
    data: { item_ref: ref(9), refresh_required: true, handling: w.DashboardContract.expected({ action: 'transition', input: call.body.input, before: handling }),
      source: {}, risk: {}, history_ref: ref(13) } });
  dashboard = await dashboardRun(call => { w.localStorage.failSet = quota; return dashboardReceipt(call); });
  assert.equal(dashboard.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。'); assert.equal(dashboard.error, null); assert.equal(dashboard.saved.phase, 'pending');
  dashboard = await dashboardRun(stale());
  assert.equal(dashboard.saved.phase, 'rejected'); assert.equal(dashboard.error.message, '来源资料已变化，请刷新后重试。'); assert.equal(dashboard.storageError, null);
  dashboard = await dashboardRun(stale(() => { w.localStorage.failSet = quota; }));
  assert.equal(dashboard.storageError.message, '上次操作记录保存不了，不能开始处置。请重新打开页面。'); assert.equal(dashboard.error, null); assert.equal(dashboard.saved.phase, 'pending');
  assert.equal(commandLookups.length, 2);

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
  assert.equal(outsourcing.storageError.message, '上次操作记录保存不了，不能开始登记。请重新打开页面。'); assert.equal(outsourcing.error, null); assert.equal(outsourcing.saved.phase, 'pending');
  assert.equal(commandLookups.length, 1); delete w.navigator;

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
