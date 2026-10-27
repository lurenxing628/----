'use strict';
// APSWorkbenchTransport is the single request channel; every case runs the shipped transport.js
// with a mocked fetch and deterministic timers. No network calls are made.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const app = path.join(__dirname, '../../frontend/workbench/app');
const sources = ['WorkbenchTerms.js', 'transport.js'].map(name => ({ name, code: fs.readFileSync(path.join(app, name), 'utf8') }));
const origin = 'http://127.0.0.1:8080', endpoint = '/api/workbench/v1/system/overview';
const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const valid = () => ({ ok: true, schema_version: 1, data: {}, warnings: [], meta: {
  source: 'production', snapshot_ref: 's'.repeat(32), request_ref: 'a'.repeat(32), time_basis: 'factory_local', as_of: '2026-09-09T01:00:00'
} });
const failurePayload = (code, committed = false, extra = {}) => ({ ok: false, committed, error: {
  code, message: code + ' visible', fields: [{ path: 'quantity', message: '请填写数量。' }], retryable: false, request_ref: 'f'.repeat(32), ...extra } });
const cases = [];
const check = async (name, action) => { await action(); cases.push(name); };

function runtime(fetcher, { fire = null } = {}) {
  const live = new Set(), delays = [], downloads = [], revoked = [];
  class ContextURL extends URL {
    static createObjectURL(blob) { ContextURL.blobs.push(blob); return 'blob:fixture/' + ContextURL.blobs.length; }
    static revokeObjectURL(href) { revoked.push(href); }
  }
  ContextURL.blobs = [];
  const document = { body: { appendChild() {} }, createElement: () => {
    const link = { click() { downloads.push({ href: link.href, filename: link.download }); }, remove() {} };
    return link;
  } };
  const context = vm.createContext({ URL: ContextURL, AbortController, DOMException, FormData, Blob, document,
    location: { origin, href: origin + '/workbench' }, fetch: fetcher, crypto: { getRandomValues: bytes => bytes.fill(171) },
    setTimeout: (fn, delay) => { delays.push(delay); const id = setTimeout(() => { live.delete(id); fn(); }, fire === null ? delay : fire); live.add(id); return id; },
    clearTimeout: id => { live.delete(id); clearTimeout(id); } });
  context.window = context;
  for (const source of sources) vm.runInContext(source.code, context, { filename: source.name });
  return { T: context.APSWorkbenchTransport, terms: context.WorkbenchTerms, timers: () => live.size, delays, downloads, revoked, blobs: ContextURL.blobs };
}
function json(payload, status = 200, type = 'application/json') {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': type } });
}
function file(bytes, type, headers = {}) {
  return new Response(Uint8Array.from(bytes), { status: 200, headers: { 'Content-Type': type, ...headers } });
}
function aborted(signal) {
  return new Promise((_, reject) => {
    const fail = () => reject(new DOMException('aborted', 'AbortError'));
    if (signal.aborted) fail(); else signal.addEventListener('abort', fail, { once: true });
  });
}
const plain = value => JSON.parse(JSON.stringify(value));
const shaped = (error, expected) => Object.entries(expected).every(([key, value]) => JSON.stringify(error[key]) === JSON.stringify(value));

async function urls() {
  const { T } = runtime(() => assert.fail('url() does not fetch'));
  await check('url keeps the workbench prefix and omits empty query values', () => {
    assert.equal(T.url(endpoint, { page: 2, query: '中 & 文', blank: '', none: null, missing: undefined, zero: 0, no: false }),
      origin + endpoint + '?page=2&query=%E4%B8%AD+%26+%E6%96%87&zero=0&no=false');
  });
  for (const target of ['https://outside.invalid' + endpoint, '/system', 'plans', 'http://user:secret@127.0.0.1:8080' + endpoint]) {
    await check('url rejects foreign or unprefixed address ' + target, () => assert.throws(() => T.url(target), error => /不属于本机/.test(error.message) && error.committed === false));
  }
}

async function envelopes() {
  const { T } = runtime(() => assert.fail('envelope() does not fetch'));
  await check('envelope returns the validated payload itself', () => { const payload = valid(); assert.strictEqual(T.envelope(payload), payload); });
  await check('envelope accepts a null snapshot_ref', () => { const payload = valid(); payload.meta.snapshot_ref = null; assert.strictEqual(T.envelope(payload), payload); });
  for (const [name, mutate] of [['schema version', p => { p.schema_version = 2; }], ['sample source', p => { p.meta.source = 'sample'; }],
    ['missing as_of', p => { delete p.meta.as_of; }], ['sixth meta key', p => { p.meta.seek = 3; }], ['numeric snapshot', p => { p.meta.snapshot_ref = 123; }],
    ['short snapshot', p => { p.meta.snapshot_ref = 'snapshot'; }], ['non-hex request ref', p => { p.meta.request_ref = 'request opaque'.padEnd(32, 'x'); }],
    ['UTC time basis', p => { p.meta.time_basis = 'UTC'; }], ['zoned as_of', p => { p.meta.as_of += 'Z'; }], ['array data', p => { p.data = []; }],
    ['missing warnings', p => { delete p.warnings; }], ['malformed warning', p => { p.warnings = [{ code: 'x' }]; }], ['not ok', p => { p.ok = false; }]]) {
    await check('envelope rejects ' + name, () => {
      const payload = valid(); mutate(payload);
      assert.throws(() => T.envelope(payload), error => /读到的数据不完整/.test(error.message) && error.code === 'invalid_response' && error.committed === false);
    });
  }
}

async function failures() {
  const { T } = runtime(() => assert.fail('failure() does not fetch'));
  await check('failure maps the backend failure envelope to the unified error', () => {
    const error = T.failure(failurePayload('stale_write', false, { request_key: 'run-' + 'b'.repeat(48), result_target: '/api/workbench/v1/scheduling/requests/x', conflicts: [{ code: 'c' }] }), 409);
    assert.equal(Object.prototype.toString.call(error), '[object Error]');
    assert(shaped(error, { message: 'stale_write visible', code: 'stale_write', fields: [{ path: 'quantity', message: '请填写数量。' }], conflicts: [{ code: 'c' }],
      committed: false, status: 409, requestRef: 'f'.repeat(32), requestKey: 'run-' + 'b'.repeat(48), resultTarget: '/api/workbench/v1/scheduling/requests/x' }));
    assert.equal(Object.prototype.hasOwnProperty.call(error, 'error'), false, 'There is one error shape; no nested error.error');
  });
  await check('failure keeps committed unknown and absent optional echoes as null', () => {
    assert(shaped(T.failure(failurePayload('storage_failure', 'unknown'), 500), { committed: 'unknown', status: 500, requestKey: null, resultTarget: null, conflicts: [] }));
  });
  for (const [name, payload] of [['success payload', valid()], ['missing fields', { ok: false, committed: false, error: { code: 'x', message: 'm' } }],
    ['bad committed', { ...failurePayload('x'), committed: 'maybe' }], ['non-text code', { ok: false, committed: false, error: { code: 1, message: 'm', fields: [] } }], ['null', null]]) {
    await check('failure turns an unrecognised payload into invalid_response: ' + name, () => {
      assert(shaped(T.failure(payload, 502), { code: 'invalid_response', status: 502, committed: false }));
    });
  }
}

async function reads() {
  let seen;
  const client = runtime(async (target, options) => { seen = { target, options }; return json(valid()); });
  await check('read sends one bounded same-origin GET and returns the validated envelope', async () => {
    assert.deepEqual(await client.T.read(endpoint, { page: 1, empty: '' }, { timeout: 60000 }), valid());
    assert.equal(seen.target, origin + endpoint + '?page=1'); assert.equal(seen.options.method, 'GET');
    assert.equal(seen.options.credentials, 'same-origin'); assert.equal(seen.options.redirect, 'error'); assert.equal(seen.options.cache, 'no-store');
    assert.deepEqual(plain(seen.options.headers), { Accept: 'application/json' }); assert.equal(client.delays.at(-1), 60000); assert.equal(client.timers(), 0);
  });
  await check('read uses the 20 second default and a read lane header', async () => {
    await client.T.read(endpoint, {}, { lane: 'dashboard-list' });
    assert.equal(client.delays.at(-1), 20000); assert.equal(seen.options.headers['X-Workbench-Read-Lane'], 'dashboard-list'); assert.equal(client.timers(), 0);
  });
  const rejects = async (name, fetcher, matcher, options = {}) => check(name, async () => {
    const local = runtime(fetcher, options);
    await assert.rejects(local.T.read(endpoint, {}, options.read || {}), matcher); assert.equal(local.timers(), 0);
  });
  await rejects('read offline', async () => { throw new TypeError('offline'); }, error => /无法连接本机/.test(error.message) && error.committed === false && error.code === null);
  await rejects('read non-JSON', async () => json(null, 200, 'text/html'), error => /非预期/.test(error.message) && error.code === 'invalid_response' && error.status === 200);
  await rejects('read unparsable JSON', async () => new Response('{bad', { status: 200, headers: { 'Content-Type': 'application/json' } }), error => /无法解析/.test(error.message) && error.code === 'invalid_response');
  await rejects('read failure envelope', async () => json(failurePayload('entity_not_found'), 404),
    error => shaped(error, { message: 'entity_not_found visible', code: 'entity_not_found', committed: false, status: 404, requestRef: 'f'.repeat(32) }));
  await rejects('read non-ok without failure envelope', async () => json(valid(), 503), error => /未能完成读取/.test(error.message) && error.status === 503 && error.code === 'invalid_response');
  await rejects('read invalid success envelope', async () => { const payload = valid(); payload.meta.snapshot_ref = 'short'; return json(payload); }, error => /读到的数据不完整/.test(error.message));
  await rejects('read superseded by a newer read', async () => json(failurePayload('request_superseded'), 499), error => error.name === 'AbortError' && error.requestRef === undefined);
  await rejects('read timeout while waiting for headers', async (_, options) => aborted(options.signal), error => /读取超时/.test(error.message) && error.code === 'timeout' && error.committed === false, { fire: 5 });
  await rejects('read timeout while reading the body', async (_, options) => ({ ok: true, status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), json: () => aborted(options.signal) }),
    error => /读取超时/.test(error.message) && error.code === 'timeout', { fire: 5 });
  await check('read external cancellation stays an AbortError and detaches', async () => {
    const local = runtime(async (_, options) => aborted(options.signal)), external = new AbortController();
    const pending = local.T.read(endpoint, {}, { signal: external.signal }); external.abort();
    await assert.rejects(pending, error => error.name === 'AbortError'); assert.equal(local.timers(), 0);
    await assert.rejects(local.T.read(endpoint, {}, { signal: external.signal }), error => error.name === 'AbortError'); assert.equal(local.timers(), 0);
  });
}

async function previews() {
  const calls = [], client = runtime(async (target, options) => { calls.push({ target, options }); return calls.length === 3 ? json(failurePayload('invalid_input'), 422) : json(valid()); });
  await check('preview posts JSON and validates the success envelope', async () => {
    assert.deepEqual(await client.T.preview(endpoint, { input: { a: 1 } }, { timeout: 30000 }), valid());
    assert.equal(calls[0].options.method, 'POST'); assert.equal(calls[0].options.body, JSON.stringify({ input: { a: 1 } }));
    assert.deepEqual(plain(calls[0].options.headers), { Accept: 'application/json', 'Content-Type': 'application/json' }); assert.equal(client.delays.at(-1), 30000);
  });
  await check('preview passes FormData through without a JSON content type', async () => {
    const form = new FormData(); form.append('file', new Blob(['x']), 'a.csv');
    await client.T.preview(endpoint, form); assert.strictEqual(calls[1].options.body, form); assert.deepEqual(plain(calls[1].options.headers), { Accept: 'application/json' });
  });
  await check('preview failure is a read-side error, never an uncertain write', async () => {
    await assert.rejects(client.T.preview(endpoint, {}), error => shaped(error, { code: 'invalid_input', committed: false, status: 422 }) && !client.T.uncertain(error));
  });
}

async function commands() {
  const key = 'run-' + 'c'.repeat(48), expect = '/api/workbench/v1/scheduling/requests/' + key, body = { request_key: key, write_token: 'w'.repeat(32) };
  const receipt = { ok: true, result: 'committed', receipt_ref: 'r'.repeat(32), replayed: false, warnings: [], data: {} };
  const run = async (respond, options = {}) => { const client = runtime(async (_, init) => respond(init), options); return { client, outcome: client.T.command(endpoint, body, { timeout: 30000, expect }) }; };
  await check('command posts JSON and returns the raw receipt', async () => {
    let init; const { client, outcome } = await run(value => { init = value; return json(receipt, 202); });
    assert.deepEqual(await outcome, receipt); assert.equal(init.method, 'POST'); assert.equal(init.body, JSON.stringify(body)); assert.equal(client.delays.at(-1), 30000); assert.equal(client.timers(), 0);
  });
  await check('command accepts a 200 receipt as well as 202', async () => {
    const { outcome } = await run(() => json(receipt, 200)); assert.deepEqual(await outcome, receipt);
  });
  const pending = runtime(() => null).terms.outcomes.pending('操作');
  for (const [name, respond, options] of [['offline', async () => { throw new TypeError('offline'); }], ['non-JSON', async () => json(receipt, 200, 'text/html')],
    ['unparsable JSON', async () => new Response('{', { status: 200, headers: { 'Content-Type': 'application/json' } })], ['non-ok success body', async () => json(receipt, 500)],
    ['timeout', init => aborted(init.signal), { fire: 5 }]]) {
    await check('command without a definite answer is uncertain: ' + name, async () => {
      const { client, outcome } = await run(respond, options);
      await assert.rejects(outcome, error => error.committed === 'unknown' && client.T.uncertain(error) && !client.T.rejected(error) && error.message === pending);
      assert.equal(client.timers(), 0);
    });
  }
  await check('command echo that names another request is not followed', async () => {
    const { client, outcome } = await run(() => json(failurePayload('stale_write', false, { request_key: 'run-' + 'd'.repeat(48), result_target: expect }), 409));
    await assert.rejects(outcome, error => error.code === 'invalid_response' && error.committed === 'unknown' && client.T.uncertain(error) && error.requestRef === 'f'.repeat(32));
  });
  await check('command echo that matches this request keeps the server rejection', async () => {
    const { client, outcome } = await run(() => json(failurePayload('stale_write', false, { request_key: key, result_target: expect }), 409));
    await assert.rejects(outcome, error => shaped(error, { code: 'stale_write', committed: false, status: 409, requestKey: key, resultTarget: expect }) && client.T.rejected(error));
  });
}

async function verdicts() {
  // Q2-A: only committed:false within 400/404/409/422/503 is a definite rejection; request_key_conflict never is.
  const { T } = runtime(() => null);
  const verdict = (code, committed, status) => T.rejected(T.failure(failurePayload(code, committed), status));
  for (const status of [400, 404, 409, 422, 503]) await check('rejected for committed:false HTTP ' + status, () => assert.equal(verdict('stale_write', false, status), true));
  for (const status of [401, 403, 405, 413, 429, 500, 502]) await check('not rejected for committed:false HTTP ' + status, () => assert.equal(verdict('stale_write', false, status), false));
  await check('request_key_conflict is never a rejection', () => assert.equal(verdict('request_key_conflict', false, 409), false));
  for (const committed of ['unknown', true]) await check('not rejected when committed is ' + committed, () => assert.equal(verdict('stale_write', committed, 409), false));
  // A local failure (status null: the request was never sent, or a read never got an answer) is also a definite non-commit.
  await check('rejected for a local failure that never reached the server', () => {
    assert.equal(T.rejected({ committed: false, status: null }), true);
    assert.equal(T.rejected({ committed: false, status: undefined }), false);
    assert.equal(T.rejected({ committed: false, status: 500 }), false);
    let guard; try { T.url('/api/other'); } catch (error) { guard = error; }
    assert(shaped(guard, { committed: false, status: null }) && T.rejected(guard));
  });
  await check('read network failure is a definite non-commit, lookup failure never is', async () => {
    const offline = runtime(async () => { throw new TypeError('offline'); });
    await assert.rejects(offline.T.read(endpoint), error => error.committed === false && error.status === null && offline.T.rejected(error));
    await assert.rejects(offline.T.lookup(endpoint), error => error.committed === 'unknown' && !offline.T.rejected(error));
    await assert.rejects(runtime(async () => json(failurePayload('stale_write'), 409)).T.lookup(endpoint), error => error.committed === 'unknown' && !offline.T.rejected(error));
  });
  await check('uncertain is exactly committed unknown', () => {
    assert.equal(T.uncertain(T.failure(failurePayload('x', 'unknown'), 500)), true);
    assert.equal(T.uncertain(T.failure(failurePayload('x', false), 500)), false);
  });
}

async function lookups() {
  const target = '/api/workbench/v1/scheduling/requests/run-' + 'e'.repeat(48);
  await check('lookup returns the raw JSON for the domain to validate', async () => {
    const raw = { ok: true, schema_version: 1, data: { state: 'found' } }, client = runtime(async () => json(raw));
    assert.deepEqual(await client.T.lookup(target), raw);
  });
  await check('lookup turns 404 receipt_not_found into null', async () => {
    assert.equal(await runtime(async () => json(failurePayload('receipt_not_found'), 404)).T.lookup(target), null);
  });
  await check('lookup failures keep the earlier command uncertain', async () => {
    await assert.rejects(runtime(async () => json(failurePayload('entity_not_found'), 404)).T.lookup(target), error => error.code === 'entity_not_found' && error.committed === 'unknown');
    await assert.rejects(runtime(async () => { throw new TypeError('offline'); }).T.lookup(target), error => /无法连接本机/.test(error.message) && error.committed === 'unknown');
  });
}

async function downloads() {
  const bom = [0xef, 0xbb, 0xbf, 0x61], zip = [0x50, 0x4b, 0x03, 0x04, 0x00], sqlite = Array.from('SQLite format 3\0', c => c.charCodeAt(0));
  let seen;
  const get = (respond, types = ['text/csv']) => { const client = runtime(async (target, init) => { seen = { target, init }; return respond(); }); return client.T.download(endpoint, { format: 'csv', blank: null }, { types, timeout: 60000 }); };
  await check('download returns blob, type, parsed filename and header reader', async () => {
    const value = await get(() => file(bom, 'text/csv; charset=utf-8', { 'Content-Disposition': "attachment; filename*=UTF-8''%E6%8E%92%E4%BA%A7.csv", 'X-Workbench-Row-Count': '3' }));
    assert.equal(value.contentType, 'text/csv'); assert.equal(value.filename, '排产.csv'); assert.equal(value.header('X-Workbench-Row-Count'), '3');
    assert.deepEqual([...new Uint8Array(await value.blob.arrayBuffer())], bom);
    assert.equal(seen.target, origin + endpoint + '?format=csv'); assert.equal(seen.init.headers.Accept, 'text/csv,application/json'); assert.deepEqual(Object.keys(seen.init.headers), ['Accept']);
  });
  for (const [name, bytes, type, disposition] of [['quoted filename', zip, XLSX, 'attachment; filename="plan \\"v2\\".xlsx"'], ['bare filename', zip, 'application/zip', 'attachment; filename=backup.zip'],
    ['sqlite backup', sqlite, 'application/vnd.sqlite3', 'attachment; filename=aps.db']]) {
    await check('download accepts ' + name, async () => assert.ok((await get(() => file(bytes, type, { 'Content-Disposition': disposition }), [type])).filename));
  }
  await check('download rejects a missing filename', async () => {
    await assert.rejects(get(() => file(bom, 'text/csv', { 'Content-Disposition': 'attachment' })), error => /缺少文件名/.test(error.message) && error.committed === false);
  });
  for (const [name, bytes, type, filename] of [['CSV saved as .xlsx', bom, 'text/csv', 'a.xlsx'], ['XLSX saved as .zip', zip, XLSX, 'plan.zip'], ['SQLite backup without .db', sqlite, 'application/vnd.sqlite3', 'aps.sqlite']]) {
    await check('download rejects a suffix that does not match the type: ' + name, async () => assert.rejects(
      get(() => file(bytes, type, { 'Content-Disposition': 'attachment; filename=' + filename }), [type]), error => /后缀与文件类型不一致/.test(error.message) && error.committed === false));
  }
  await check('download keeps escaped quotes inside a quoted filename', async () => {
    assert.equal((await get(() => file(zip, XLSX, { 'Content-Disposition': 'attachment; filename="plan \\"v2\\".xlsx"' }), [XLSX])).filename, 'plan "v2".xlsx');
  });
  await check('download maps a JSON failure envelope to the unified error', async () => {
    await assert.rejects(get(() => json(failurePayload('snapshot_stale'), 409)), error => shaped(error, { code: 'snapshot_stale', status: 409, committed: false }));
  });
  for (const [name, respond, pattern] of [['JSON success instead of a file', () => json(valid()), /格式不正确/], ['type outside the allowed list', () => file(zip, XLSX, { 'Content-Disposition': 'attachment; filename=a.xlsx' }), /格式不正确/],
    ['empty file', () => file([], 'text/csv', { 'Content-Disposition': 'attachment; filename=a.csv' }), /空的/], ['CSV without BOM', () => file([0x61, 0x62], 'text/csv', { 'Content-Disposition': 'attachment; filename=a.csv' }), /不符/],
    ['inline disposition', () => file(bom, 'text/csv', { 'Content-Disposition': 'inline; filename=a.csv' }), /不是附件/], ['path in filename', () => file(bom, 'text/csv', { 'Content-Disposition': 'attachment; filename="../a.csv"' }), /文件名无效/],
    ['missing disposition', () => file(bom, 'text/csv'), /不是附件/], ['non-ok file response', () => new Response(Uint8Array.from(bom), { status: 500, headers: { 'Content-Type': 'text/csv' } }), /未能完成读取/]]) {
    await check('download rejects ' + name, async () => assert.rejects(get(respond), error => pattern.test(error.message) && error.committed === false));
  }
}

async function saving() {
  await check('types maps the four download formats to frozen MIME types', () => {
    const T = runtime(() => null).T;
    assert.deepEqual(plain(T.types), { csv: 'text/csv', xlsx: XLSX, zip: 'application/zip', sqlite: 'application/vnd.sqlite3' });
    assert.equal(Object.isFrozen(T.types), true);
  });
  await check('saveBlob hands one named object URL to the browser and revokes it later', async () => {
    const client = runtime(() => null, { fire: 1 }), blob = new Blob(['x']);
    client.T.saveBlob('计划.csv', blob);
    assert.deepEqual(plain(client.downloads), [{ href: 'blob:fixture/1', filename: '计划.csv' }]); assert.strictEqual(client.blobs[0], blob);
    await new Promise(resolve => setTimeout(resolve, 10)); assert.deepEqual(plain(client.revoked), ['blob:fixture/1']); assert.equal(client.delays.at(-1), 1000);
  });
  await check('downloadJSON saves pretty JSON through saveBlob', async () => {
    const client = runtime(() => null, { fire: 1 });
    client.T.downloadJSON('诊断.json', { a: [1] });
    assert.equal(client.downloads[0].filename, '诊断.json'); assert.equal(await client.blobs[0].text(), JSON.stringify({ a: [1] }, null, 2));
    assert.equal(client.blobs[0].type, 'application/json;charset=utf-8');
  });
  await check('requestKey is prefix plus 48 lowercase hex', () => assert.equal(runtime(() => null).T.requestKey('resource'), 'resource-' + 'ab'.repeat(24)));
}

async function run() {
  await urls(); await envelopes(); await failures(); await reads(); await previews(); await commands(); await verdicts(); await lookups(); await downloads(); await saving();
  console.log(JSON.stringify({ checks: cases.length, cases, network: 'mock-only', production: false }));
}
run().catch(error => { console.error(error); process.exitCode = 1; });
