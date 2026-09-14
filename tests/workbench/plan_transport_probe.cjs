'use strict';
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const files = ['resource-contract.js', 'resource-api.js', 'WorkbenchTerms.js', 'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'PlanAPI.js'];
const scripts = files.map(name => ({name, source: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')}));
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
const sources = scripts.map(script => ({path: 'frontend/workbench/app/' + script.name, sha256: digest(script.source)}));
for (const file of ['tests/workbench/plan_transport_probe.cjs', 'tests/workbench/test_plan_transport.py'])
  sources.push({path: file, sha256: digest(fs.readFileSync(path.join(root, file)))});
const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
const P = 'a'.repeat(48), OTHER = 'b'.repeat(48), TASK = 'c'.repeat(48), OP = 'd'.repeat(48);
const START = '2026-09-09T22:30:00', END = '2026-09-10T06:30:00';
const origin = 'http://127.0.0.1:8080', endpoint = origin + '/api/workbench/v1/plans';
const cases = [], calls = [];
const clone = value => JSON.parse(JSON.stringify(value));
const issue = () => ({code: 'identity_missing', message: 'Identity unavailable'});
const header = () => ({plan_ref: P, version: 3, kind: 'official', is_current_official: true,
  display_name: 'Night plan', completeness: 'complete', capabilities: {view: true, export: true, edit_draft: false, adopt: false, report_actual: false}, blocked_reasons: []});
const envelope = data => ({ok: true, schema_version: 1, data, meta: {source: 'production', time_basis: 'factory_local',
  request_ref: 'request opaque', snapshot_ref: 'snapshot opaque', as_of: '2026-09-09T20:00:00'}, warnings: []});
const catalog = () => envelope({plans: [header()], page: {collection: 'history', size: 20, unit: 'version', has_more: false, next_cursor: null}});
const workspace = () => align(envelope({plan: header(), scope: {source: 'production', kind: 'plan_workspace', plan_ref: P, range_start: null, range_end: null},
  time_scope: {range_start: START, range_end: END, selection: 'overlap', boundary: 'half_open', time_basis: 'factory_local'},
  plan_span: {start: START, end: END}, task_span: {start: START, end: END}, tasks: [{task_ref: TASK, operation_ref: OP, plan_ref: P,
    batch_id: 'B-1', sequence: 1, process_label: 'Night work', piece_id: null, quantity: null, batch_quantity: null,
    quantity_basis: 'unknown', quantity_reason: 'plan_target_not_recorded',
    machine_ref: OTHER, operator_ref: null, supplier_ref: null, start: START, end: END}],
  task_count: 1, tasks_complete: true,
  resources: [{kind: 'machine', ref: OTHER, business_code: 'M1', label: 'Machine'}],
  projections: {baseline: {state: 'unavailable', reason_code: 'not_recorded', reason: 'No recorded baseline', baseline_plan: null,
    items: [], item_count: 0, items_complete: false}}}));
function align(payload) {
  const d = payload.data, time = clone(d.time_scope);
  d.projections.process_order = {state: 'unavailable', basis: null, items: [], issues: [{code: 'process_order_not_recorded', message: 'No captured process order'}]};
  d.projections.calendar = {state: 'available', plan_ref: P, time_scope: time, global: {state: 'available', basis: 'global_calendar',
    windows: [], issues: [], available_hours: 0, effective_hours: 0, normal_available_hours: 0, normal_effective_hours: 0,
    urgent_available_hours: 0, urgent_effective_hours: 0}, resources: [], issues: []};
  d.projections.occupancy = {state: 'available', plan_ref: P, time_scope: clone(time), basis: 'selected_plan_only', resources: [], issues: []};
  d.projections.delivery_risks = {state: 'available', plan_ref: P, scope: clone(d.scope), items: d.tasks.length ? [{batch_ref: OP, batch_id: 'B-1',
    part_no: 'P1', part_label: 'Part', planned_finish: END, partial_planned_finish: null, due_date: '2026-09-10', delivery_deadline_exclusive: '2026-09-11T00:00:00',
    risk: 'on_time', is_overdue: false, delay_hours: 0, delay_days: 0, completeness: 'complete', schedule_complete: true,
    operation_count: 1, scheduled_operation_count: 1, unscheduled_operation_count: 0, task_count: 1, invalid_task_count: 0, issues: []}] : [],
    batch_count: d.tasks.length ? 1 : 0, items_complete: true, completeness: d.tasks.length ? 'complete' : 'unknown',
    basis: {kind: 'planned_delivery', time_basis: 'factory_local', batch_selection: d.scope.range_start === null ? 'plan_task_batches' : 'overlap_or_bad_time_batches',
      completion_scope: 'full_selected_plan', operation_scope: 'current_batch_operations', due_boundary: 'next_day_exclusive', actual_completion: 'not_evaluated', actual_delivery: 'not_evaluated'}};
  if (!d.tasks.length) d.resources = [];
  return payload;
}
function response(payload, status = 200, type = 'application/json') {
  return {ok: status >= 200 && status < 300, status, headers: {get: () => type}, json: async () => clone(payload)};
}
function runtime(fetcher, timeout = 20000) {
  let timers = 0, listeners = 0;
  const context = vm.createContext({URL, AbortController, FormData, location: {origin, href: origin + '/workbench'},
    sessionStorage: {getItem() { assert.fail('GET must not read pending writes'); }, setItem() { assert.fail('GET must not write storage'); }, removeItem() { assert.fail('GET must not clear storage'); }},
    fetch: async (url, options) => {
      calls.push(url); assert.equal(options.method, 'GET'); assert.equal(options.body, undefined);
      assert.equal(options.headers.Accept, new URL(url).pathname.endsWith('/export') ? 'application/octet-stream,application/json' : 'application/json');
      assert.equal(options.credentials, 'same-origin');
      assert.equal(options.redirect, 'error'); assert.equal(options.cache, 'no-store');
      assert.equal(new URL(url).origin, origin); return fetcher(url, options);
    }, setTimeout: (fn, delay) => { assert.equal(delay, 20000); timers++; return setTimeout(fn, timeout); },
    clearTimeout: timer => { timers--; clearTimeout(timer); }});
  context.window = context;
  for (const script of scripts) vm.runInContext(script.source, context, {filename: script.name});
  return {api: context.APSPlanAPI.create(), C: context.APSPlanContract, idle: () => assert.equal(timers, 0),
    signal(controller) {
      return {get aborted() { return controller.signal.aborted; },
        addEventListener(...args) { listeners++; controller.signal.addEventListener(...args); },
        removeEventListener(...args) { listeners--; controller.signal.removeEventListener(...args); }};
    }, detached: () => assert.equal(listeners, 0)};
}
async function check(name, action) { await action(); cases.push(name); }
const rejected = error => error && error.committed === false && typeof error.message === 'string' && error.message.length > 0;
function aborting(signal) {
  return new Promise((resolve, reject) => {
    const abort = () => { const error = new Error('aborted'); error.name = 'AbortError'; reject(error); };
    if (signal.aborted) abort(); else signal.addEventListener('abort', abort, {once: true});
  });
}
async function requests() {
  const normal = runtime(async url => { assert.equal(url, endpoint + '?collection=history&size=20'); return response(catalog()); });
  await check('catalog exact default path and GET', async () => { assert.deepEqual(await normal.api.catalog(), catalog()); normal.idle(); });
  await check('read-only public surface', () => assert.deepEqual(Object.keys(normal.api).sort(), ['catalog', 'export', 'workspace']));
  const opaque = ' cursor:/+?&= % unicode \u6d4b\u8bd5 ';
  await check('opaque cursor and snapshot query escaping', async () => {
    const payload = catalog(); payload.data.page = {collection: 'scenario', size: 1, unit: 'scenario', has_more: false, next_cursor: null};
    payload.data.plans[0].kind = 'scenario'; payload.data.plans[0].is_current_official = false; payload.meta.snapshot_ref = opaque;
    const client = runtime(async url => {
      assert.equal(url, endpoint + '?' + new URLSearchParams({collection: 'scenario', size: '1', cursor: opaque, snapshot_ref: opaque}));
      return response(payload);
    });
    assert.deepEqual(await client.api.catalog({collection: 'scenario', size: 1, cursor: opaque, snapshot_ref: opaque}), payload); client.idle();
  });
  await check('workspace exact path and unbounded scope', async () => {
    const client = runtime(async url => { assert.equal(url, endpoint + '/' + P + '/workspace'); return response(workspace()); });
    assert.deepEqual(await client.api.workspace(P), workspace()); client.idle();
  });
  await check('workspace overlap not clipped with escaped query', async () => {
    const scope = {range_start: '2026-09-10T00:00:00', range_end: '2026-09-10T01:00:00', snapshot_ref: opaque};
    const payload = workspace(); Object.assign(payload.data.scope, scope); delete payload.data.scope.snapshot_ref;
    Object.assign(payload.data.time_scope, {range_start: scope.range_start, range_end: scope.range_end}); payload.meta.snapshot_ref = opaque;
    align(payload);
    const client = runtime(async url => { assert.equal(url, endpoint + '/' + P + '/workspace?' + new URLSearchParams(scope)); return response(payload); });
    assert.deepEqual(await client.api.workspace(P, scope), payload); client.idle();
  });
  const noRequest = runtime(() => assert.fail('Invalid scope must be rejected before transport'));
  const beforeInvalid = calls.length;
  for (const scope of [null, [], 'history', new Date(), new Map(), Object.create({resource_ref: OTHER}),
    {collection: 'all'}, {collection: undefined}, {size: null}, {size: '20'}, {size: 0}, {size: 51}, {size: 1.5},
    {page: 1}, {before_version: 2}, {after_scenario_id: 'x'}, {range_start: START}, {query: ''}, {source: 'demo'}, {filters: {}}, {cursor: ''}, {cursor: null},
    {cursor: 123}, {snapshot_ref: ''}, {snapshot_ref: undefined}, {[Symbol('filter')]: true}, Object.defineProperty({}, 'size', {value: 1})]) {
    await check('catalog invalid scope ' + cases.length, () => assert.rejects(noRequest.api.catalog(scope), rejected));
  }
  for (const value of [null, undefined, 3, P.toUpperCase(), 'a'.repeat(47), 'a'.repeat(49), '../plans', P + '?x=1', P + '/workspace']) {
    await check('invalid plan ref ' + cases.length, () => assert.rejects(noRequest.api.workspace(value), rejected));
  }
  for (const scope of [null, [], {range_start: START}, {range_end: END}, {range_start: null, range_end: null},
    {range_start: END, range_end: START}, {range_start: START, range_end: START}, {plan_ref: OTHER}, {cursor: 'x'}, {baseline_ref: P}, {resource_ref: P},
    {scenario_id: 'private'}, {snapshot_ref: ''}, {range_start: '2026-02-30T00:00:00', range_end: END},
    ...['2026-09-09', START + 'Z', START + '+08:00', '2026-09-09T24:00:00', '2026-09-09T22:60:00', '2026-09-09T22:30:60',
      '0000-01-01T00:00:00', '1900-02-29T00:00:00'].map(value => ({range_start: value, range_end: END}))]) {
    await check('workspace invalid scope ' + cases.length, () => assert.rejects(noRequest.api.workspace(P, scope), rejected));
  }
  await check('invalid inputs issue zero network calls', () => assert.equal(calls.length, beforeInvalid));
  await check('caller mutation cannot change in-flight scope', async () => {
    let finish; const client = runtime(() => new Promise(resolve => { finish = resolve; }));
    const scope = {size: 20}, pending = client.api.catalog(scope); scope.size = 1; finish(response(catalog()));
    assert.deepEqual(await pending, catalog()); client.idle();
  });
}
async function contracts() {
  const {C} = runtime(() => assert.fail('Contract checks do not fetch'));
  const quantityFields = ['piece_id', 'quantity', 'batch_quantity', 'quantity_basis', 'quantity_reason'];
  await check('legacy quantities stay explicitly unknown without mutation', () => {
    const p = workspace(), before = JSON.stringify(p);
    assert.strictEqual(C.workspace(p, P), p);
    assert.deepEqual(quantityFields.map(key => p.data.tasks[0][key]), [null, null, null, 'unknown', 'plan_target_not_recorded']);
    assert.equal(JSON.stringify(p), before);
  });
  for (const key of quantityFields) await check('missing task quantity field ' + key, () => {
    const p = workspace(); delete p.data.tasks[0][key]; assert.throws(() => C.workspace(p, P), rejected);
  });
  for (const reason of ['plan_target_not_recorded', 'plan_target_unavailable']) await check('unknown piece work retains reason ' + reason, () => {
    const p = workspace(); Object.assign(p.data.tasks[0], {piece_id: 'piece-1', quantity_reason: reason});
    assert.strictEqual(C.workspace(p, P), p);
    assert.deepEqual(quantityFields.map(key => p.data.tasks[0][key]), ['piece-1', null, null, 'unknown', reason]);
  });
  for (const basis of ['run_admission', 'trial_creation']) for (const [piece, quantity, batch] of [
    [null, 0, 0], [null, 7, 7], ['piece-1', 1, 7], [null, '9007199254740993', '9007199254740993']]) {
    await check('captured task quantities preserved ' + basis + ' ' + piece + ' ' + quantity, () => {
      const p = workspace(); Object.assign(p.data.tasks[0], {piece_id: piece, quantity, batch_quantity: batch, quantity_basis: basis, quantity_reason: null});
      const before = JSON.stringify(p); assert.strictEqual(C.workspace(p, P), p);
      assert.deepEqual(quantityFields.map(key => p.data.tasks[0][key]), [piece, quantity, batch, basis, null]);
      assert.equal(JSON.stringify(p), before);
    });
  }
  for (const patch of [{piece_id: ''}, {piece_id: ' '}, {piece_id: 1}, {piece_id: 'piece\0x'},
    {quantity: 0}, {batch_quantity: 7}, {quantity_reason: null}, {quantity_reason: ''}, {quantity_reason: 'not_recorded'},
    {quantity_basis: 'current_batch'}, {quantity_basis: 'run_admission', quantity_reason: null}]) {
    await check('invalid or fabricated legacy quantities ' + cases.length, () => {
      const p = workspace(); Object.assign(p.data.tasks[0], patch); assert.throws(() => C.workspace(p, P), rejected);
    });
  }
  for (const basis of ['run_admission', 'trial_creation']) {
    await check('invalid captured target remains explicit ' + basis, () => {
      const p = workspace(); Object.assign(p.data.tasks[0], {batch_quantity: 7, quantity_basis: basis, quantity_reason: 'plan_target_invalid'});
      assert.strictEqual(C.workspace(p, P), p); assert.equal(p.data.tasks[0].quantity, null); assert.equal(p.data.tasks[0].batch_quantity, 7);
    });
    for (const key of ['quantity', 'batch_quantity']) for (const value of [-1, 1.5, true, '7', '01', 9007199254740992, '9223372036854775808', NaN, Infinity]) {
      await check('invalid captured numeric field ' + basis + ' ' + key + ' ' + value, () => {
        const p = workspace(); Object.assign(p.data.tasks[0], {quantity: 7, batch_quantity: 7, quantity_basis: basis, quantity_reason: null, [key]: value});
        assert.throws(() => C.workspace(p, P), rejected);
      });
    }
  }
  for (const kind of ['catalog', 'workspace']) {
    const valid = kind === 'catalog' ? catalog : workspace;
    const validate = payload => kind === 'catalog' ? C.catalog(payload) : C.workspace(payload, P);
    for (const mutate of [p => { p.meta.source = 'demo'; }, p => { p.meta.snapshot_ref = ''; }, p => { p.meta.request_ref = ''; },
      p => { p.meta.as_of = '2026-02-30T00:00:00'; }, p => { p.meta.time_basis = 'UTC'; }, p => { p.schema_version = 2; },
      p => { p.warnings = null; }, p => { p.ok = false; }, p => { p.data = []; }, p => { p.meta.seek = 3; }, p => { p.extra = 'private'; }]) {
      await check(kind + ' malformed envelope ' + cases.length, () => { const p = valid(); mutate(p); assert.throws(() => validate(p), rejected); });
    }
  }
  for (const mutate of [p => { p.plan_ref = 'legacy'; }, p => { p.plan_ref = null; }, p => { p.version = null; }, p => { p.version = 9007199254740992; },
    p => { p.version = '9223372036854775808'; }, p => { p.version = '03'; }, p => { p.version = '3'; }, p => { p.version = true; }, p => { p.version = 0; },
    p => { p.capabilities.view = false; }, p => { p.capabilities.adopt = true; }, p => { p.capabilities.edit_draft = true; },
    p => { p.kind = 'candidate'; }, p => { p.kind = 'latest'; }, p => { p.completeness = 'invalid'; }, p => { p.blocked_reasons = [issue()]; },
    p => { p.schedule_id = 1; }, p => { p.display_name = ''; }]) {
    await check('catalog invalid identity ' + cases.length, () => { const p = catalog(); mutate(p.data.plans[0]); assert.throws(() => C.catalog(p), rejected); });
  }
  for (const mutate of [p => { p.page.collection = 'scenario'; }, p => { p.page.size = 1; }, p => { p.page.unit = 'task'; },
    p => { p.page.has_more = 'false'; }, p => { p.page.next_cursor = ''; }, p => { p.page.has_more = true; },
    p => { p.plans.push(clone(p.plans[0])); }, p => { p.page.seek = 1; }, p => { p.plans[0].kind = 'scenario'; }]) {
    await check('catalog bad page ' + cases.length, () => { const p = catalog(); mutate(p.data); assert.throws(() => C.catalog(p), rejected); });
  }
  await check('opaque next cursor is not a permanent ref', () => { const p = catalog(); Object.assign(p.data.page, {has_more: true, next_cursor: 'next ? + /'}); assert.strictEqual(C.catalog(p), p); });
  await check('snapshot mismatch is rejected', () => assert.throws(() => C.catalog(catalog(), {snapshot_ref: 'other'}), rejected));
  await check('repeated cursor is rejected', () => { const p = catalog(); Object.assign(p.data.page, {has_more: true, next_cursor: 'same'}); assert.throws(() => C.catalog(p, {cursor: 'same'}), rejected); });
  await check('disabled null references and invalid versions remain null', () => {
    const p = catalog(); const row = p.data.plans[0]; row.plan_ref = null; row.version = null; row.is_current_official = false;
    row.capabilities.view = false; row.capabilities.export = false; row.completeness = 'unknown'; row.blocked_reasons = [issue()]; p.data.plans.push(clone(row));
    assert.strictEqual(C.catalog(p), p); assert.equal(row.plan_ref, null);
  });
  await check('multiple roles share a version page unit', () => {
    const p = catalog(); p.data.page.size = 1; const row = clone(p.data.plans[0]); row.plan_ref = OTHER; row.kind = 'candidate';
    row.is_current_official = false; row.completeness = 'unknown'; p.data.plans.push(row); assert.strictEqual(C.catalog(p, {size: 1}), p);
    row.version = 2; assert.throws(() => C.catalog(p, {size: 1}), rejected);
  });
  for (const value of [1, Number.MAX_SAFE_INTEGER, '9007199254740992', '9007199254740993', '9223372036854775807']) {
    await check('exact int64 preserved ' + value, () => { const p = workspace(); p.data.plan.version = value; p.data.tasks[0].sequence = value;
      assert.strictEqual(C.workspace(p, P), p); assert.strictEqual(p.data.plan.version, value); assert.strictEqual(p.data.tasks[0].sequence, value); });
  }
  for (const mutate of [p => { p.plan.plan_ref = OTHER; }, p => { p.scope.plan_ref = OTHER; }, p => { p.scope.source = 'demo'; },
    p => { p.scope.kind = 'plan_catalog'; }, p => { p.scope.range_start = START; }, p => { p.scope.resource_ref = OTHER; },
    p => { p.time_scope.range_end = START; }, p => { p.time_scope.selection = 'contains'; }, p => { p.time_scope.boundary = 'closed'; },
    p => { p.time_scope.time_basis = 'UTC'; }, p => { p.plan_span.start = '2026-02-30T00:00:00'; }, p => { p.task_span = null; },
    p => { p.task_span.end = '2026-09-10T06:31:00'; }, p => { p.task_count = 0; }, p => { p.tasks_complete = false; },
    p => { delete p.tasks_complete; }, p => { p.tasks.push(clone(p.tasks[0])); p.task_count++; }, p => { p.tasks = []; p.task_count = 0; p.task_span = null; },
    p => { p.projections.calendar = []; }, p => { p.projections.calendar.state = 'complete'; }, p => { delete p.projections.baseline; },
    p => { p.projections.occupancy.reason = ''; }, p => { p.projections.delivery_risks.rows = []; }, p => { p.plan.capabilities.view = false; }]) {
    await check('workspace malformed DTO ' + cases.length, () => { const p = workspace(); mutate(p.data); assert.throws(() => C.workspace(p, P), rejected); });
  }
  for (const mutate of [t => { t.plan_ref = OTHER; }, t => { t.task_ref = 'legacy'; }, t => { t.operation_ref = null; },
    t => { t.machine_ref = 'machine-1'; }, t => { t.operator_ref = 1; }, t => { delete t.supplier_ref; }, t => { t.batch_id = ''; },
    t => { t.process_label = ' '; }, t => { t.sequence = 9007199254740992; }, t => { t.sequence = '1e3'; },
    t => { t.start = END; }, t => { t.end = '2026-09-10T06:31:00'; }, t => { t.start += 'Z'; }, t => { t.op_id = 1; }]) {
    await check('foreign or invalid task ' + cases.length, () => { const p = workspace(); mutate(p.data.tasks[0]); assert.throws(() => C.workspace(p, P), rejected); });
  }
  await check('real projections remain unchanged', () => { const p = workspace(), before = JSON.stringify(p); assert.strictEqual(C.workspace(p, P), p); assert.equal(JSON.stringify(p), before); });
  await check('legacy not_loaded is rejected', () => { const p = workspace(); p.data.projections.calendar = {state: 'not_loaded', reason: 'Legacy'}; assert.throws(() => C.workspace(p, P), rejected); });
  await check('explicit range covering whole plan cannot hide empty or clipped results', () => {
    const p = workspace(), scope = {range_start: START, range_end: END};
    Object.assign(p.data.scope, scope); align(p); assert.strictEqual(C.workspace(p, P, scope), p);
    p.data.tasks[0].end = p.data.task_span.end = '2026-09-10T05:00:00'; assert.throws(() => C.workspace(p, P, scope), rejected);
    p.data.tasks = []; p.data.task_count = 0; p.data.task_span = null; assert.throws(() => C.workspace(p, P, scope), rejected);
  });
  await check('empty overlap is not empty whole plan', () => {
    const p = workspace(), scope = {range_start: END, range_end: '2026-09-10T08:00:00'};
    Object.assign(p.data.scope, scope); Object.assign(p.data.time_scope, scope);
    assert.throws(() => C.workspace(p, P, scope), rejected);
    p.data.tasks = []; p.data.task_count = 0; p.data.task_span = null; align(p); assert.strictEqual(C.workspace(p, P, scope), p);
  });
  await check('local leap day and years below 100 avoid Date timezone normalization', () => {
    for (const range_start of ['2000-02-29T23:00:00', '0099-01-01T00:00:00', '0001-01-01T00:00:00'])
      assert.equal(C.workspaceScope(P, {range_start, range_end: END}).range_start, range_start);
  });
}
async function failures() {
  for (const [status, code] of [[404, 'entity_not_found'], [409, 'snapshot_stale'], [409, 'plan_binding_invalid'], [413, 'query_too_large'], [500, 'storage_failure']]) {
    await check('server failure preserved ' + code, async () => {
      const payload = {ok: false, committed: false, error: {code, message: code + ' visible', fields: [], retryable: status >= 500, request_ref: 'failure-ref'}};
      const client = runtime(async () => response(payload, status)); const before = calls.length;
      await assert.rejects(client.api.workspace(P), error => rejected(error) && error.error.code === code && error.error.request_ref === 'failure-ref');
      assert.equal(calls.length, before + 1); client.idle();
    });
  }
  for (const fetcher of [async () => { throw new TypeError('offline'); }, async () => response({}, 200, 'text/html'),
    async () => ({...response(null), json: async () => { throw new SyntaxError('bad json'); }}), async () => response({ok: false}, 500),
    async () => response({ok: true, schema_version: 1, data: {}}), async () => response(catalog(), 503)]) {
    await check('transport malformed or offline ' + cases.length, async () => { const client = runtime(fetcher); const before = calls.length;
      await assert.rejects(client.api.catalog(), rejected); assert.equal(calls.length, before + 1); client.idle(); });
  }
  for (const method of ['catalog', 'workspace']) {
    await check('cancel in flight and already cancelled ' + method, async () => {
      const client = runtime(async (_, options) => aborting(options.signal)), controller = new AbortController(), signal = client.signal(controller);
      const read = () => method === 'catalog' ? client.api.catalog({}, signal) : client.api.workspace(P, {}, signal);
      const pending = read(); controller.abort(); await assert.rejects(pending, rejected); client.idle(); client.detached();
      const before = calls.length; await assert.rejects(read(), rejected); assert.equal(calls.length, before); client.idle(); client.detached();
    });
  }
  for (const fetcher of [async (_, options) => aborting(options.signal), async (_, options) => ({...response(null), json: () => aborting(options.signal)})]) {
    await check('bounded timeout including body read ' + cases.length, async () => { const client = runtime(fetcher, 5);
      await assert.rejects(client.api.catalog(), error => rejected(error) && /超时/.test(error.message)); client.idle(); });
  }
}
async function backendFixtures() {
  for (const fixture of input.fixtures || []) {
    await check('backend DTO ' + fixture.name, async () => {
      const client = runtime(async url => {
        const target = new URL(url); assert.equal(target.pathname, '/api/workbench/v1/plans' + (fixture.kind === 'catalog' ? '' : '/' + fixture.plan_ref + '/workspace'));
        return response(fixture.payload, fixture.status || 200);
      });
      const read = () => fixture.kind === 'catalog' ? client.api.catalog(fixture.scope || {}) : client.api.workspace(fixture.plan_ref, fixture.scope || {});
      if (fixture.contract_error) await assert.rejects(read(), rejected);
      else if (fixture.error) await assert.rejects(read(), error => rejected(error) && error.error.code === fixture.error);
      else assert.deepEqual(await read(), fixture.payload);
      client.idle();
    });
  }
}
async function exports() {
  const scope = {format: 'csv', snapshot_ref: 'snapshot + ? /', range_start: START, range_end: END};
  const noRequest = runtime(() => assert.fail('Invalid export must not fetch'));
  for (const invalid of [undefined, null, {}, {format: 'csv'}, {format: 'CSV', snapshot_ref: 'x'},
    {...scope, extra: true}, {...scope, snapshot_ref: ''}, {...scope, range_end: START}]) {
    await check('invalid export scope ' + cases.length, () => assert.rejects(noRequest.api.export(P, invalid), rejected));
  }
  for (const format of ['csv', 'xlsx']) {
    const type = format === 'csv' ? 'text/csv; charset=utf-8' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    const blob = {size: 12}, disposition = 'attachment; filename="plan.' + format + '"';
    const client = runtime(async url => {
      assert.equal(url, endpoint + '/' + P + '/export?' + new URLSearchParams({...scope, format}));
      return {ok: true, status: 200, headers: {get: key => key === 'content-type' ? type : disposition}, blob: async () => blob};
    });
    await check('binary export exact GET and scope ' + format, async () => {
      const value = await client.api.export(P, {...scope, format});
      assert.strictEqual(value.blob, blob); assert.equal(value.disposition, disposition); client.idle();
    });
  }
  for (const type of ['text/html', 'application/json', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']) {
    await check('export wrong bytes or JSON success ' + type, async () => {
      const client = runtime(async () => ({...response(workspace(), 200, type), blob: async () => ({size: 10})}));
      await assert.rejects(client.api.export(P, scope), rejected); client.idle();
    });
  }
  await check('export stale does not retry or refresh snapshot', async () => {
    const payload = {ok: false, committed: false, error: {code: 'snapshot_stale', message: 'Stale', fields: []}};
    const client = runtime(async () => response(payload, 409)), before = calls.length;
    await assert.rejects(client.api.export(P, scope), error => rejected(error) && error.error.code === 'snapshot_stale');
    assert.equal(calls.length, before + 1); client.idle();
  });
}
async function run() {
  if (!input.fixturesOnly) { await requests(); await contracts(); await failures(); await exports(); }
  await backendFixtures();
  console.log(JSON.stringify({checks: cases.length, cases, sources, network: 'mock-only', production: false, methods: ['GET']}));
}
run().catch(error => { console.error(error); process.exitCode = 1; });
