'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const babel = require(path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'));
const source = fs.readFileSync(path.join(root, 'frontend/workbench/app/ResourceWorkspace.jsx'), 'utf8');
const ast = babel.transform(source, {ast: true, code: false, sourceType: 'script', parserOpts: {plugins: ['jsx']}}).ast;
const body = ast.program.body[0].expression.callee.body.body;
const declaration = body.find(node => node.type === 'FunctionDeclaration' && node.id.name === 'readList');
assert(declaration, 'The workspace list reader must be tested without exporting a product test hook');
const runtime = vm.createContext({window: {}});
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/resource-contract.js'), 'utf8'), runtime);
runtime.C = runtime.window.APSResourceContract;
vm.runInContext(source.slice(declaration.start, declaration.end), runtime);
const read = runtime.readList, plain = value => JSON.parse(JSON.stringify(value));
const scope = Object.freeze({query: '原搜索条件', status: 'active', sort: 'label', direction: 'desc', page: 3, size: 20,
  snapshot_ref: undefined, column_filters: Object.freeze({spec: Object.freeze({mode: 'exclude', values: Object.freeze(['x'])})})});
const envelope = (scope, total = 61) => ({ok: true, schema_version: 1,
  data: {entities: [], page: {number: scope.page, size: scope.size, total, pages: Math.max(1, Math.ceil(total / scope.size)), sort: []}},
  meta: {source: 'production', time_basis: 'factory_local', snapshot_ref: 'actual-returned-snapshot', request_ref: 'actual-request', as_of: '2026-09-10T14:00:00'}, warnings: []});
let checks = 0;
async function main() {
  for (const kind of ['material', 'machine', 'operator', 'supplier', 'op_type']) {
    const original = envelope(scope), calls = [], signal = new AbortController().signal;
    assert.equal(await read({list: async (...args) => {calls.push(args); return original;}}, kind, scope, signal), original);
    assert.deepEqual(calls, [[kind, scope, signal]]); checks++;
  }
  for (const total of [0, 1, 20, 21, 40]) {
    const calls = [], page = Math.max(1, Math.ceil(total / 20)), signal = new AbortController().signal;
    const adapter = {list: async (kind, request, supplied) => {
      calls.push(plain(request)); assert.equal(kind, 'material'); assert.equal(supplied, signal);
      return envelope(request, total);
    }};
    const result = await read(adapter, 'material', scope, signal);
    assert.equal(result.data.page.number, page);
    assert.deepEqual(calls, [plain(scope), {...plain(scope), page, snapshot_ref: 'actual-returned-snapshot'}]); checks++;
  }
  for (const property of ['page', 'size']) {
    const value = envelope(scope); value.data.page[property === 'page' ? 'number' : 'size']++;
    await assert.rejects(read({list: async () => value}, 'material', scope), /翻页位置已失效/); checks++;
  }
  for (const mutate of [result => {result.data.page.number = 1;}, result => {result.data.page.size = 50;},
    result => {result.data.page.total = 39;}, result => {result.meta.snapshot_ref = 'different';}, result => {result.meta.source = 'demo';}]) {
    let calls = 0;
    await assert.rejects(read({list: async (_, request) => {
      const result = envelope(request, 40); if (++calls === 2) mutate(result); return result;
    }}, 'material', scope), /翻页位置已失效/);
    assert.equal(calls, 2); checks++;
  }
  for (const at of [1, 2]) {
    const failure = new Error('actual snapshot stale or disconnected'); let calls = 0;
    await assert.rejects(read({list: async (_, request) => {
      if (++calls === at) throw failure; return envelope(request, 40);
    }}, 'material', scope), error => error === failure);
    assert.equal(calls, at); checks++;
  }
  await assert.rejects(read({}, 'material', scope), /dependency not wired/); checks++;
  assert.equal(scope.page, 3); assert.equal(scope.snapshot_ref, undefined); checks++;
  console.log(JSON.stringify({checks, passed: true, scope: 'extracted-private-reader-unit-not-browser'}));
}
main().catch(error => {console.error(error); process.exitCode = 1;});
