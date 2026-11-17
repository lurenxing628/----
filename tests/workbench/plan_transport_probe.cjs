'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const files = ['resource-contract.js', 'shared/network/transport.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'FieldContract.js', 'RunGenerationContract.js', 'PointContract.js', 'PointGanttModel.js', 'GanttGraph.js', 'PlanContract.js', 'PlanAPI.js', 'PlanGanttModel.js'];
const compiledOutputs = compile({
  sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })),
}).outputs;
// stdin 由 tests/workbench/plan_transport_support.py 的 run_probe 提供，成功形状全部来自后端真实投影：
// fixtures 逐个走真实计划读取链；boundary 是后端导出的真实信封，传输边界自检只在它们之上手写非法输入。
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const P = 'a'.repeat(48), OTHER = 'b'.repeat(48);
const START = '2026-09-09T22:30:00', END = '2026-09-10T06:30:00';
const origin = 'http://127.0.0.1:8080', endpoint = origin + '/api/workbench/v1/plans';
const cases = [], calls = [];
const clone = value => JSON.parse(JSON.stringify(value));
const real = name => clone(input.boundary[name]);
function response(payload, status = 200, type = 'application/json') {
  return new Response(JSON.stringify(payload), {status, headers: {'Content-Type': type}});
}
function runtime(fetcher, timeout = 20000) {
  let timers = 0; const listeners = new Set();
  const context = vm.createContext({URL, URLSearchParams, AbortController, DOMException, FormData, Blob, location: {origin, href: origin + '/workbench'},
    sessionStorage: {getItem() { assert.fail('GET must not read pending writes'); }, setItem() { assert.fail('GET must not write storage'); }, removeItem() { assert.fail('GET must not clear storage'); }},
    fetch: async (url, options) => {
      calls.push(url); assert.equal(options.method, 'GET'); assert.equal(options.body, undefined);
      const format = new URL(url).searchParams.get('format');
      assert.equal(options.headers.Accept, new URL(url).pathname.endsWith('/export') ? (format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') + ',application/json' : 'application/json');
      assert.equal(options.credentials, 'same-origin');
      assert.equal(options.redirect, 'error'); assert.equal(options.cache, 'no-store');
      assert.equal(new URL(url).origin, origin); return fetcher(url, options);
    }, setTimeout: (fn, delay) => { assert.equal(delay, 20000); timers++; return setTimeout(fn, timeout); },
    clearTimeout: timer => { timers--; clearTimeout(timer); }});
  context.window = context;
  for (const out of compiledOutputs) vm.runInContext(out.code, context, {filename: out.path});
  const getMod = rel => context.__wbRuntime.getModule(rel);
  return {api: getMod('PlanAPI.js').default || getMod('PlanAPI.js'), C: getMod('PlanContract.js'), T: getMod('shared/network/transport.js'), M: getMod('PlanGanttModel.js'),
    idle: () => assert.equal(timers, 0),
    signal(controller) {
      return {get aborted() { return controller.signal.aborted; },
        addEventListener(type, listener, options) { listeners.add(listener); controller.signal.addEventListener(type, listener, options); },
        removeEventListener(type, listener) { listeners.delete(listener); controller.signal.removeEventListener(type, listener); }};
    }, detached: () => assert.equal(listeners.size, 0)};
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
  const more = real('catalog_more'), last = real('catalog_last'), ws = real('workspace'), REF = ws.data.plan.plan_ref;
  const normal = runtime(async url => { assert.equal(url, endpoint + '?collection=history&size=20'); return response(more); });
  await check('catalog exact default path and GET', async () => { assert.deepEqual(await normal.api.catalog(), more); normal.idle(); });
  await check('read-only public surface', () => assert.deepEqual(Object.keys(normal.api).sort(), ['baseline', 'capacity', 'catalog', 'export', 'ganttGraph', 'workspace']));
  const opaque = ' cursor:/+?&= % unicode \u6d4b\u8bd5 ';
  await check('opaque cursor and snapshot query escaping', async () => {
    const scope = {collection: 'history', size: 1, cursor: opaque, snapshot_ref: last.meta.snapshot_ref};
    const client = runtime(async url => { assert.equal(url, endpoint + '?' + new URLSearchParams(scope)); return response(last); });
    assert.deepEqual(await client.api.catalog(scope), last); client.idle();
  });
  await check('workspace exact path and unbounded scope', async () => {
    const client = runtime(async url => { assert.equal(url, endpoint + '/' + REF + '/workspace'); return response(ws); });
    assert.deepEqual(await client.api.workspace(REF), ws); client.idle();
  });
  await check('baseline exact path and default pagination', async () => {
    const base = real('baseline'), snapshot = {snapshot_ref: ws.meta.snapshot_ref}, combined = clone(base);
    delete combined.data.page;
    const client = runtime(async url => {
      assert.equal(url, endpoint + '/' + REF + '/baseline?' + new URLSearchParams({...snapshot, page: '1', size: '5000'}));
      return response(base);
    });
    assert.deepEqual(client.C.baselinePage(clone(base), ws.data, {...snapshot, page: 1, size: 5000}), base);
    const read = await client.api.baseline(REF, snapshot, ws.data);
    assert.deepEqual(read, combined);
    assert.equal(client.C.baseline(read.data, ws.data), true);
    client.idle();
  });
  const noRequest = runtime(() => assert.fail('Invalid scope must be rejected before transport'));
  const beforeInvalid = calls.length;
  for (const scope of [null, [], 'history',
    {collection: 'all'}, {collection: 'scenario'}, {collection: undefined}, {size: null}, {size: '20'}, {size: 0}, {size: 51}, {size: 1.5},
    {page: 1}, {before_version: 2}, {after_scenario_id: 'x'}, {range_start: START}, {query: ''}, {source: 'demo'}, {filters: {}}, {cursor: ''}, {cursor: null},
    {cursor: 123}, {snapshot_ref: ''}, {snapshot_ref: undefined}]) {
    await check('catalog invalid scope ' + cases.length, () => assert.rejects(noRequest.api.catalog(scope), rejected));
  }
  const validWsData = ws.data, token = ws.meta.snapshot_ref;
  for (const value of [null, undefined, 3, P.toUpperCase(), 'a'.repeat(47), 'a'.repeat(49), '../plans', P + '?x=1', P + '/workspace']) {
    await check('invalid plan ref ' + cases.length, () => assert.rejects(noRequest.api.workspace(value), rejected));
    await check('invalid baseline plan ref ' + cases.length, () => assert.rejects(noRequest.api.baseline(value, {snapshot_ref: token}, validWsData), rejected));
  }
  for (const scope of [null, [], {}, {page: 1}, {snapshot_ref: ''}, {snapshot_ref: null}, {snapshot_ref: token, page: 0},
    {snapshot_ref: token, page: '1'}, {snapshot_ref: token, page: 1.5}, {snapshot_ref: token, size: 0}, {snapshot_ref: token, size: 5001},
    {snapshot_ref: token, size: '5000'}, {snapshot_ref: token, range_start: START}, {snapshot_ref: token, range_end: END},
    {snapshot_ref: token, range_start: END, range_end: START}, {snapshot_ref: token, cursor: 'x'}]) {
    await check('baseline invalid scope ' + cases.length, () => assert.rejects(noRequest.api.baseline(P, scope, validWsData), rejected));
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
    const scope = {size: 20}, pending = client.api.catalog(scope); scope.size = 1; finish(response(more));
    assert.deepEqual(await pending, more); client.idle();
  });
}
async function contracts() {
  const {C, M} = runtime(() => assert.fail('Contract checks do not fetch'));
  const REF = input.boundary.workspace.data.plan.plan_ref;
  for (const [kind, name] of [['catalog', 'catalog_more'], ['workspace', 'workspace']]) {
    // The envelope is validated once, in APSWorkbenchTransport; read it through the real API path.
    for (const mutate of [p => { p.meta.source = 'demo'; }, p => { p.meta.snapshot_ref = ''; }, p => { p.meta.snapshot_ref = null; }, p => { p.meta.request_ref = ''; },
      p => { p.meta.as_of = '2026-02-30T00:00:00'; }, p => { p.meta.time_basis = 'UTC'; }, p => { p.schema_version = 2; },
      p => { p.warnings = null; }, p => { p.ok = false; }, p => { p.data = []; }, p => { p.meta.seek = 3; }, p => { p.extra = 'private'; }]) {
      await check(kind + ' malformed envelope ' + cases.length, async () => {
        const p = real(name); mutate(p); const client = runtime(async () => response(p));
        await assert.rejects(kind === 'catalog' ? client.api.catalog() : client.api.workspace(REF), rejected); client.idle();
      });
    }
  }
  // 只核游标协议（防翻页死循环）；collection/size 回声由后端唯一生产者保证，前端不再比对（S09-02）。
  for (const mutate of [p => { p.page.next_cursor = ''; }, p => { p.page.has_more = true; }]) {
    await check('catalog bad page ' + cases.length, () => { const p = real('catalog_last'); mutate(p.data); assert.throws(() => C.catalog(p, C.catalogScope()), rejected); });
  }
  await check('snapshot mismatch is rejected', () => assert.throws(() => C.catalog(real('catalog_last'), C.catalogScope({snapshot_ref: 'other'})), rejected));
  await check('repeated cursor is rejected', () => { const p = real('catalog_more'); assert.throws(() => C.catalog(p, C.catalogScope({cursor: p.data.page.next_cursor})), rejected); });
  for (const mutate of [p => { p.plan.plan_ref = OTHER; }, p => { p.scope.plan_ref = OTHER; }, p => { p.scope.source = 'demo'; },
    p => { p.scope.kind = 'plan_catalog'; }, p => { p.scope.range_start = START; },
    p => { p.time_scope.range_end = START; },
    p => { p.plan.capabilities.view = false; }, p => { p.projections.calendar = {state: 'not_loaded', reason: 'Legacy'}; }]) {
    await check('workspace malformed DTO ' + cases.length, () => { const p = real('workspace'); mutate(p.data); assert.throws(() => C.workspace(p, REF, {}), rejected); });
  }
  await check('local leap day and years below 100 avoid Date timezone normalization', () => {
    for (const range_start of ['2000-02-29T23:00:00', '0099-01-01T00:00:00', '0001-01-01T00:00:00'])
      assert.equal(C.workspaceScope(P, {range_start, range_end: END}).range_start, range_start);
  });
  await check('baseline items stay bound to the workspace tasks', () => {
    const data = real('workspace').data, items = real('baseline').data.items, facts = M.prepareTasks(data);
    const {comparisons} = M.prepareBaseline(data, facts, items), bound = items.filter(item => item.after_in_scope);
    assert.ok(bound.length > 0, 'The real baseline compares tasks that are still in scope');
    for (const item of bound) assert.strictEqual(comparisons.get(item.operation_ref).after, facts.taskIndex.get(item.after.task_ref).task);
    bound[0].after = {task_ref: '9'.repeat(48)};
    assert.throws(() => M.prepareBaseline(data, facts, items), /原安排对照/);
  });
}
async function failures() {
  for (const [status, code] of [[404, 'entity_not_found'], [409, 'snapshot_stale'], [409, 'plan_binding_invalid'], [413, 'query_too_large'], [500, 'storage_failure']]) {
    await check('server failure preserved ' + code, async () => {
      const ref = 'f'.repeat(32);
      const payload = {ok: false, committed: false, error: {code, message: code + ' visible', fields: [], retryable: status >= 500, request_ref: ref}};
      const client = runtime(async () => response(payload, status)); const before = calls.length;
      await assert.rejects(client.api.workspace(P), error => rejected(error) && error.code === code && error.status === status && error.requestRef === ref);
      assert.equal(calls.length, before + 1); client.idle();
    });
  }
  for (const fetcher of [async () => { throw new TypeError('offline'); }, async () => response({}, 200, 'text/html'),
    async () => new Response('{bad json', {status: 200, headers: {'Content-Type': 'application/json'}}), async () => response({ok: false}, 500),
    async () => response({ok: true, schema_version: 1, data: {}}), async () => response(real('catalog_more'), 503)]) {
    await check('transport malformed or offline ' + cases.length, async () => { const client = runtime(fetcher); const before = calls.length;
      await assert.rejects(client.api.catalog(), rejected); assert.equal(calls.length, before + 1); client.idle(); });
  }
  const cancelWsData = real('workspace').data;
  for (const method of ['catalog', 'workspace', 'tasks', 'ganttGraph', 'capacity', 'baseline']) {
    await check('cancel in flight and already cancelled ' + method, async () => {
      const client = runtime(async (_, options) => aborting(options.signal)), controller = new AbortController(), signal = client.signal(controller);
      const read = () => method === 'catalog' ? client.api.catalog({}, signal)
        : method === 'workspace' ? client.api.workspace(P, {}, signal)
        : method === 'tasks' ? (async () => {
          const query = client.C.tasksScope(P, {snapshot_ref: 's'.repeat(32)});
          return client.C.tasksPage(await client.T.read('/api/workbench/v1/plans/' + P + '/tasks', query, {signal, timeout: 20000}), cancelWsData, query);
        })()
        : client.api[method](P, {snapshot_ref: 's'.repeat(32)}, cancelWsData, signal);
      const cancelled = error => error.name === 'AbortError';
      const pending = read(); controller.abort(); await assert.rejects(pending, cancelled); client.idle(); client.detached();
      await assert.rejects(read(), cancelled); client.idle(); client.detached();
    });
  }
  for (const fetcher of [async (_, options) => aborting(options.signal), async (_, options) => ({ok: true, status: 200, headers: new Headers({'Content-Type': 'application/json'}), json: () => aborting(options.signal), text: () => aborting(options.signal)})]) {
    await check('bounded timeout including body read ' + cases.length, async () => { const client = runtime(fetcher, 5);
      await assert.rejects(client.api.catalog(), error => rejected(error) && /超时/.test(error.message)); client.idle(); });
  }
}
// 后端真实投影逐个走真实读取链：首个请求带上 Python 读取时用的全部参数；pages 是后续分页的真实应答，必须被读完；
// 跟进读取（对照、分页、衔接图、班表负荷）绑定 workspace 指名的那次真实读取，只核身份与范围，不再扫它的工序。
async function backendFixtures() {
  const leaves = {catalog: '', workspace: '/workspace', baseline: '/baseline', tasks: '/tasks', gantt_graph: '/gantt-graph', capacity: '/capacity', export: '/export'};
  const follow = {workspace: '/tasks', baseline: '/baseline'};
  const workspaces = new Map(input.fixtures.filter(fixture => fixture.kind === 'workspace').map(fixture => [fixture.name, fixture.payload.data]));
  for (const fixture of input.fixtures) {
    await check('backend DTO ' + fixture.name, async () => {
      const base = '/api/workbench/v1/plans' + (fixture.kind === 'catalog' ? '' : '/' + fixture.plan_ref);
      const replies = [{path: base + leaves[fixture.kind], scope: fixture.scope, payload: fixture.payload},
        ...(fixture.pages || []).map(payload => ({path: base + follow[fixture.kind], scope: {}, payload}))];
      const client = runtime(async url => {
        const target = new URL(url), reply = replies.shift();
        assert.ok(reply, 'Unexpected extra read ' + target.pathname);
        assert.equal(target.pathname, reply.path);
        for (const [key, value] of Object.entries(reply.scope)) assert.equal(target.searchParams.get(key), String(value));
        return fixture.kind === 'export' ? new Response(Buffer.from(fixture.body, 'base64'), {status: 200, headers: fixture.headers})
          : response(clone(reply.payload));
      });
      let taskReads = 0;
      const admitted = () => {
        const data = workspaces.get(fixture.workspace);
        return {...data, tasks: new Proxy(data.tasks, {get(target, prop, receiver) { if (prop !== 'length') taskReads++; return Reflect.get(target, prop, receiver); }})};
      };
      const reads = {
        catalog: () => client.api.catalog(fixture.scope),
        workspace: () => client.api.workspace(fixture.plan_ref, fixture.scope),
        export: () => client.api.export(fixture.plan_ref, fixture.scope),
        baseline: () => client.api.baseline(fixture.plan_ref, fixture.scope, admitted()),
        tasks: async () => {
          const query = client.C.tasksScope(fixture.plan_ref, fixture.scope);
          return client.C.tasksPage(await client.T.read(base + '/tasks', query, {timeout: 20000}), admitted(), query);
        },
        gantt_graph: () => client.api.ganttGraph(fixture.plan_ref, fixture.scope, admitted()),
        capacity: () => client.api.capacity(fixture.plan_ref, fixture.scope, admitted())
      };
      if (fixture.contract_error) await assert.rejects(reads[fixture.kind](), rejected);
      else if (fixture.kind === 'export') {
        const file = await reads.export();
        assert.deepEqual([...new Uint8Array(await file.blob.arrayBuffer())], [...Buffer.from(fixture.body, 'base64')]);
        assert.equal(file.filename, fixture.filename);
      } else assert.deepEqual(await reads[fixture.kind](), fixture.expected || fixture.payload);
      assert.equal(replies.length, 0, 'Every real follow-up page was read');
      assert.equal(taskReads, 0, 'Follow-up reads validate against the admitted workspace without reading its tasks');
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
  for (const type of ['text/html', 'application/json', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']) {
    await check('export wrong bytes or JSON success ' + type, async () => {
      const client = runtime(async () => response(real('workspace'), 200, type));
      await assert.rejects(client.api.export(P, scope), rejected); client.idle();
    });
  }
  await check('export stale does not retry or refresh snapshot', async () => {
    const payload = {ok: false, committed: false, error: {code: 'snapshot_stale', message: 'Stale', fields: [], retryable: false, request_ref: 'f'.repeat(32)}};
    const client = runtime(async () => response(payload, 409)), before = calls.length;
    await assert.rejects(client.api.export(P, scope), error => rejected(error) && error.code === 'snapshot_stale');
    assert.equal(calls.length, before + 1); client.idle();
  });
}
async function run() {
  if (input.boundary) { await requests(); await contracts(); await failures(); await exports(); }
  const boundary = cases.length;
  await backendFixtures();
  console.log(JSON.stringify({fixtures: cases.length - boundary, boundary, cases, network: 'mock-only', production: false, methods: ['GET']}));
}
run().catch(error => { console.error(error); process.exitCode = 1; });
