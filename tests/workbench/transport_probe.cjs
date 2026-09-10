'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/transport.js'), 'utf8');
const endpoint = '/api/workbench/v1/system/overview';
const valid = () => ({ok: true, schema_version: 1, data: {}, meta: {
  source: 'production', snapshot_ref: 'snapshot', request_ref: 'request',
  time_basis: 'factory_local', as_of: '2026-09-09T01:00:00'
}});
let checks = 0;

function runtime(fetcher, timeout = 20000) {
  let activeTimers = 0;
  const context = vm.createContext({URL, AbortController, location: {
    origin: 'http://127.0.0.1:8080', href: 'http://127.0.0.1:8080/workbench'
  }, fetch: fetcher, setTimeout: (fn, delay) => {
    assert.equal(delay, 20000); activeTimers++;
    return setTimeout(fn, timeout);
  }, clearTimeout: timer => { activeTimers--; clearTimeout(timer); }});
  context.window = context;
  vm.runInContext(source, context);
  return {read: context.APSWorkbenchTransport.read, timers: () => activeTimers};
}
function response(payload, ok = true, contentType = 'application/json') {
  return {ok, headers: {get: () => contentType}, json: async () => payload};
}
function aborted(signal) {
  return new Promise((_, reject) => {
    const fail = () => { const error = new Error('aborted'); error.name = 'AbortError'; reject(error); };
    if (signal.aborted) fail(); else signal.addEventListener('abort', fail, {once: true});
  });
}
async function rejects(fetcher, matcher, timeout) {
  const client = runtime(fetcher, timeout);
  await assert.rejects(client.read(endpoint), matcher);
  assert.equal(client.timers(), 0); checks++;
}
async function run() {
  const client = runtime(async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8080' + endpoint);
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers.Accept, 'application/json');
    return response(valid());
  });
  assert.deepEqual(await client.read(endpoint), valid()); assert.equal(client.timers(), 0); checks++;
  for (const url of ['https://outside.invalid' + endpoint, '/system']) {
    await assert.rejects(client.read(url), /不属于本机/); checks++;
  }
  await rejects(async () => { throw new TypeError('offline'); }, /无法连接本机/);
  await rejects(async () => response(null, true, 'text/html'), /非预期/);
  await rejects(async () => ({...response(null), json: async () => { throw new SyntaxError('invalid'); }}), /无法解析/);
  await rejects(async () => response({ok: false, error: {message: '系统正在维护'}}, false), /系统正在维护/);
  for (const mutate of [p => { p.schema_version = 2; }, p => { p.meta.source = 'sample'; },
    p => { delete p.meta.as_of; }, p => { p.meta.snapshot_ref = 123; },
    p => { p.meta.time_basis = 'UTC'; }, p => { p.data = []; }, p => { p.meta.request_ref = ''; }]) {
    const payload = valid(); mutate(payload);
    await rejects(async () => response(payload), /协议不匹配/);
  }
  await rejects(async (_, options) => aborted(options.signal), /读取超时/, 5);
  await rejects(async (_, options) => ({...response(null), json: () => aborted(options.signal)}), /读取超时/, 5);
  const external = new AbortController();
  const cancellable = runtime(async (_, options) => aborted(options.signal));
  const pending = cancellable.read(endpoint, external.signal); external.abort();
  await assert.rejects(pending, error => error.name === 'AbortError');
  assert.equal(cancellable.timers(), 0); checks++;
  await assert.rejects(cancellable.read(endpoint, external.signal), error => error.name === 'AbortError');
  assert.equal(cancellable.timers(), 0); checks++;
  console.log(JSON.stringify({checks, network: 'mock-only', production: false}));
}
run().catch(error => { console.error(error); process.exitCode = 1; });
