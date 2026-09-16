'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const requests = [], saved = new Map(), ref = 'a'.repeat(48), preview = 'b'.repeat(32);
const context = { console, URL, FormData, Blob, AbortController, crypto: webcrypto, setTimeout, clearTimeout,
  location: { origin: 'http://127.0.0.1:9981', href: 'http://127.0.0.1:9981/workbench' },
  sessionStorage: { getItem: key => saved.has(key) ? saved.get(key) : null, setItem: (key, value) => saved.set(key, value), removeItem: key => saved.delete(key) } };
context.window = context;
context.fetch = async (url, options) => {
  requests.push({ url, options }); const pathname = new URL(url).pathname;
  const writing = /\/(create|update|delete|operation_update|sync-confirm|bulk-confirm|import-confirm)$/.test(pathname);
  const data = pathname.endsWith('/bulk-confirm') || pathname.endsWith('/import-confirm') ? { items: [{ entity_ref: ref, result: 'committed' }], count: 1 } : { entity_ref: ref };
  const payload = writing ? { ok: true, result: 'committed', receipt_ref: 'fixture-receipt', replayed: false, data, warnings: [] }
    : { ok: true, schema_version: 1, data: {}, meta: { source: 'production', time_basis: 'factory_local', snapshot_ref: 'snapshot', request_ref: 'request', as_of: '2026-09-09T12:00:00' }, warnings: [] };
  return { ok: true, headers: { get: name => name.toLowerCase() === 'content-type' ? 'application/json' : null }, json: async () => payload };
};
vm.createContext(context);
for (const file of ['resource-contract.js', 'resource-api.js', 'BatchContract.js', 'BatchAPI.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', file), 'utf8'), context, { filename: file });
(async () => {
  const api = context.APSBatchAPI.create();
  await api.list('batch', { page: 1, size: 20, column_filters: { quantity: [0, null] } });
  assert.equal(new URL(requests.at(-1).url).pathname, '/api/workbench/v1/entities/batch/query');
  assert.deepEqual(JSON.parse(requests.at(-1).options.body).column_filters.quantity, [0, null]);
  await api.detail('batch', ref); await api.choices();
  await api.preview('sync', ref, {}, {}, 'snapshot');
  assert.equal(new URL(requests.at(-1).url).pathname, '/api/workbench/v1/entities/batch/' + ref + '/sync-preview');
  await api.preview('bulk', null, { action: 'delete', refs: [ref] }, {}, 'snapshot');
  assert.equal(JSON.parse(requests.at(-1).options.body).snapshot_ref, 'snapshot');
  for (const action of context.APSBatchContract.actions) {
    const target = action === 'create' ? null : ['bulk_confirm', 'import_confirm'].includes(action) ? preview : ref;
    const intent = { kind: 'batch', action, ref: target, request_key: 'resource-' + ref };
    api.savePending(intent); assert.equal(api.readPending().action, action); assert.equal(context.APSResourceAPI.create().readPending(), null);
    const body = { request_key: intent.request_key, write_token: 'write-token', input: target === preview ? { preview_ref: preview } : { fields: { quantity: 1 } } };
    await api.command('batch', action, target, body); api.clearPending();
  }
  const count = requests.length;
  assert.throws(() => api.detail('batch', 'B001'));
  await assert.rejects(api.command('batch', 'bulk_confirm', preview, { input: { preview_ref: 'c'.repeat(32) } }));
  await assert.rejects(api.command('material', 'update', ref, { input: {} }));
  assert.equal(requests.length, count);
  assert.throws(() => context.APSResourceAPI.create().list('batch', {}));
  assert.equal(saved.size, 0);
  console.log(JSON.stringify({ passed: true, namespace: 'batches', actions: Array.from(context.APSBatchContract.actions), requests: requests.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
