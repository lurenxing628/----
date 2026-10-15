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
w.WorkbenchHandlerMemory = { read: () => ({ value: '经办人' }) }; w.WorkbenchGuards = { useDirtyGuard() {} };
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
    { name: 'TrialAdoptionState', contract: 'TrialAdoptionAPI', leaf: 'overview', mount: module => module.useSession({ disabled: true }),
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
