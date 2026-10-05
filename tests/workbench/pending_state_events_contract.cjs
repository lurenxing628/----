'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const clone = value => JSON.parse(JSON.stringify(value)), ref = value => value.repeat(48);
const runAction = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: 'app/RunAdoptionAction.jsx', code: fs.readFileSync(path.join(app, 'RunAdoptionAction.jsx'), 'utf8') }], check_combined: true }).outputs[0].code;

function host() {
  const values = new Map(), listeners = new Map(), events = [], counters = { reads: 0, writes: 0 };
  let mode = '', random = 0, rendering;
  const storage = {
    getItem(key) { counters.reads++; return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { counters.writes++; if (mode === 'quota') throw Error('quota');
      if (mode !== 'dropped') values.set(key, mode === 'corrupt' ? '{' : value); },
    removeItem(key) { counters.writes++; values.delete(key); }
  };
  class LocalEvent { constructor(type, options = {}) { this.type = type; Object.assign(this, options); } }
  const window = { localStorage: storage, crypto: { getRandomValues(array) { array.fill(++random); return array; } },
    fetch: async () => { throw Error('Unexpected network'); }, WorkbenchHandlerMemory: { read: () => ({ value: '' }) },
    WorkbenchGuards: { useDirtyGuard() {} }, RunAdoptionControls: {},
    WorkbenchTerms: { outcomes: { pending: () => 'pending', unknown: () => 'unknown', rejected: () => 'rejected', done: () => 'done' } },
    addEventListener(type, callback) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(callback); },
    removeEventListener(type, callback) { listeners.get(type)?.delete(callback); },
    dispatchEvent(event) { events.push(event); for (const callback of listeners.get(event.type) || []) callback(event); }
  };
  // Only the real hooks' state setters and mount effects are exercised here; no DOM or React renderer.
  const React = {
    useMemo(factory) { return factory(); }, useRef(value) { return { current: value }; },
    useState(initial) { const owner = rendering, index = owner.states.length;
      owner.states.push(typeof initial === 'function' ? initial() : initial);
      return [owner.states[index], value => { owner.states[index] = typeof value === 'function' ? value(owner.states[index]) : value; }]; },
    useReducer(reducer, initial) { const owner = rendering, index = owner.states.length; owner.states.push(initial);
      return [initial, value => { owner.states[index] = reducer(owner.states[index], value); }]; },
    useEffect(callback) { rendering.effects.push(callback); },
    createElement(type, props, ...children) { return { type, props: { ...props, children } }; }
  };
  const context = vm.createContext({ window, localStorage: storage, crypto: window.crypto, React, Event: LocalEvent, CustomEvent: LocalEvent,
    navigator: { locks: { request: async (_key, _options, callback) => callback(true) } },
    AbortController, Uint8Array, setTimeout, clearTimeout, URLSearchParams, console });
  for (const file of ['RunAdoptionAPI.js', 'TrialAdoptionAPI.js', 'CalibrationAdoptionAPI.js', 'DashboardContract.js', 'OutsourcingContract.js',
    'TrialAdoptionState.js', 'CalibrationAdoptionState.js', 'DashboardSession.js', 'OutsourcingSession.js'])
    vm.runInContext(fs.readFileSync(path.join(app, file), 'utf8'), context, { filename: file });
  vm.runInContext(runAction, context, { filename: 'RunAdoptionAction.jsx' });
  return { window, values, events, counters, storage, setMode(value) { mode = value; },
    emit(type, options) { window.dispatchEvent(new LocalEvent(type, options)); },
    mount(render) { const owner = { states: [], effects: [] }; rendering = owner; owner.result = render(); rendering = null;
      owner.effects.forEach(callback => callback()); return owner; },
    reset() { counters.reads = 0; counters.writes = 0; events.length = 0; } };
}

function fixtures(W) {
  const input = { confirm: true, reason: '已核对', declared_operator: '经办人' }, baseline = { plan_ref: null, version: null };
  const runPreview = { candidate_ref: ref('a'), run_ref: ref('b'), baseline, task_count: 1, scope_complete: true };
  const trial = { schema_version: 1, scenario_ref: ref('a'), request_key: 'trial-adoption-' + ref('1'), input,
    preview: { scenario_ref: ref('a'), draft_ref: ref('b'), baseline, task_count: 1, scope_complete: true }, phase: 'pending' };
  const sampleRefs = ['1', '2', '3', '4', '5'].map(ref);
  const calibration = { version: 1, request_key: 'calibration-' + ref('1'), phase: 'pending', input,
    baseline: { template_operation_ref: ref('a'), template_revision: 1, template_snapshot: 'original-template', part_ref: ref('b'), part_no: 'P1',
      part_name: '零件', sequence: 10, operation_label: '10 自制', source: 'internal', old_unit_hours: 1, suggested_unit_hours: 2,
      sample_count: 5, eligible_sample_count: 5, candidate_count: 5, excluded_count: 0, sample_refs: sampleRefs,
      sample_revisions: sampleRefs.map(sample_ref => ({ sample_ref, sample_revision: 'original', template_revision: 1, report_revision_refs: [] })),
      exclusion_reasons: [], method_version: 'median_v1' } };
  const before = Object.fromEntries(['owner', 'deadline', 'action', 'remark', 'completed_at', 'completion_evidence', 'evidence_reference_text', 'evidence_ref'].map(key => [key, null]));
  before.status = 'new';
  const dashboard = { version: 1, request_key: 'dashboard-' + ref('1'), phase: 'pending', item_ref: ref('a'), action: 'transition',
    input: { target_status: 'following' }, before, source: { kind: 'material' }, risk: { active: true, message: '待核对', code: 'material_gap' } };
  const after = { sent: '2026-09-09T08:00:00', planned: '2026-09-10T08:00:00', returned: null, confirmedState: 'in_transit' };
  const target = { kind: 'single', batch_ref: ref('a'), supplier_ref: ref('b'), operation_refs: [ref('c')], grouping_basis: 'explicit_receipt_membership',
    batch: { ref: ref('a') }, supplier: { ref: ref('b') }, operations: [{ operation_ref: ref('c') }] };
  const outsourcing = { version: 1, request_key: 'outsourcing-' + ref('1'), phase: 'pending', target, after,
    input: { declared_operator: '经办人', reason: '核对发出', target: W.OutsourcingContract.target(target), ...after } };
  return { input, runPreview, trial, calibration, dashboard, outsourcing };
}

function entry(host, name) {
  const W = host.window, data = fixtures(W), adapter = { lookup: async () => null };
  if (name === 'run') {
    const pending = W.RunAdoptionAPI.pending();
    return { key: W.RunAdoptionAPI.PENDING_KEY, event: W.RunAdoptionAPI.EVENT, read: pending.read,
      write: previous => pending.begin(data.runPreview, data.input, previous),
      mount: () => host.mount(() => { const node = W.RunAdoptionAction({ candidateRef: ref('a'), adapter }); return node.type(node.props); }),
      async reject(saved) {
        const api = W.RunAdoptionAPI.create(async () => ({ ok: false, status: 409, headers: { get: () => 'application/json' },
          json: async () => ({ ok: false, committed: false, error: { code: 'snapshot_stale', message: 'changed', fields: [], retryable: false, request_ref: 'f'.repeat(32) } }) }));
        let rejected; try { await api.adopt(saved, 't'.repeat(32)); } catch (error) { rejected = error; }
        assert(W.RunAdoptionAPI.isRejected(rejected)); return pending.reject(saved, rejected);
      }, clear: saved => pending.cancelRejected(saved),
      retainUnknown(saved) { assert.throws(() => pending.reject(saved, new Error('lost reply'))); } };
  }
  const state = { trial: W.TrialAdoptionState, calibration: W.CalibrationAdoptionState, dashboard: W.DashboardSession, outsourcing: W.OutsourcingSession }[name];
  return { key: state.KEY, event: state.KEY + '_changed', read: state.read, write: previous => state.save(data[name], previous),
    mount: () => host.mount(() => name === 'trial' ? state.useSession({ scenarioRef: ref('a'), data: null })
      : name === 'calibration' ? state.useSession({ detail: null, stale: true, adapter }) : state.useCommand(adapter)),
    reject: saved => state.save({ ...saved, phase: 'rejected' }, saved), clear: saved => state.save(null, saved) };
}

async function checkDomain(name) {
  const h = host(), e = entry(h, name), first = e.mount(), peer = e.mount();
  h.reset(); const saved = e.write(null);
  assert.equal(h.counters.reads, 2, name + ': compare and readback remain; same-page listeners do not reread');
  assert.equal(h.events.length, 1); assert.strictEqual(h.events[0].detail, saved);
  for (const owner of [first, peer]) assert.deepEqual(clone(owner.states[1]), clone(saved));
  if (e.retainUnknown) { h.reset(); e.retainUnknown(saved); assert.equal(h.events.length, 0); assert.deepEqual(clone(e.read()), clone(saved)); }
  const rejected = await e.reject(saved);
  for (const owner of [first, peer]) assert.equal(owner.states[1].phase, 'rejected');
  h.reset(); e.clear(rejected); assert.equal(h.counters.reads, 2); assert.equal(h.events[0].detail, null);
  for (const owner of [first, peer]) assert.equal(owner.states[1], null);
  // A delayed cross-tab event must read the current value, never trust its stale newValue.
  h.values.set(e.key, JSON.stringify(saved)); h.reset();
  h.emit('storage', { key: e.key, newValue: JSON.stringify(rejected) });
  assert.equal(h.counters.reads, 2); for (const owner of [first, peer]) assert.equal(owner.states[1].phase, 'pending');
  h.reset(); assert.throws(() => e.write(null)); assert.equal(h.counters.writes, 0); assert.equal(h.events.length, 0);
  h.emit('storage', { key: 'unrelated' }); assert.equal(h.counters.reads, 1);
  // Malformed same-page data is rejected without replacing the real pending operation.
  h.reset(); h.emit(e.event, { detail: {} }); assert.equal(h.counters.reads, 0);
  for (const owner of [first, peer]) { assert.equal(owner.states[1].phase, 'pending'); assert(owner.states[2]); }
  h.values.set(e.key, '{'); h.reset(); h.emit('storage', { key: e.key }); assert.equal(h.counters.reads, 2);
  for (const owner of [first, peer]) assert(owner.states[2]);
  for (const mode of ['quota', 'dropped', 'corrupt']) {
    const bad = host(), pending = entry(bad, name), owner = pending.mount(); bad.reset(); bad.setMode(mode);
    assert.throws(() => pending.write(null), name + ': ' + mode); assert.equal(bad.events.length, 0); assert.equal(owner.states[1], null);
  }
  return name;
}

async function dashboardUnknown() {
  const h = host(), W = h.window, pending = fixtures(W).dashboard;
  const owner = h.mount(() => W.DashboardSession.useCommand({ command: async () => { throw Error('lost reply'); }, lookup: async () => null }));
  h.mount(() => W.DashboardSession.useCommand({ lookup: async () => null })); h.reset();
  const item = { item_ref: pending.item_ref, subject: 'material', handling: pending.before, source: pending.source, risk: pending.risk,
    write_context: { write_token: 'original-token', capabilities: { transition: true } } };
  await owner.result.submit(item, pending.action, pending.input);
  assert.equal(h.counters.reads, 4, 'one lock check, compare, readback and one post-submit observation');
  assert.equal(owner.states[1].phase, 'pending'); assert.equal(owner.result.finish(), false);
  assert.equal(JSON.parse(h.values.get(W.DashboardSession.KEY)).phase, 'pending');
}

(async () => {
  const domains = []; for (const name of ['trial', 'calibration', 'dashboard', 'outsourcing', 'run']) domains.push(await checkDomain(name));
  await dashboardUnknown();
  console.log(JSON.stringify({ passed: true, domains, same_page_storage_reads_per_save: 2, cross_tab_reads_per_listener: 1,
    checked: ['pending-conflict', 'null-clear', 'unknown-retained', 'rejected-retained', 'quota', 'dropped-write', 'corrupt-readback', 'stale-storage-event'] }));
})().catch(error => { console.error(error); process.exitCode = 1; });
