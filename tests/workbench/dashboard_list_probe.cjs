'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const { routeFetch, browser, loadTransport, json, failure } = require('./route_fetch.cjs');
const payloads = JSON.parse(fs.readFileSync(0, 'utf8'));
const LIST = 'GET /api/workbench/v1/dashboard';
const appDir = path.join(__dirname, '../../frontend/workbench/app');
const compiledTerms = compile({
  sources: [{ path: 'WorkbenchTerms.js', code: fs.readFileSync(path.join(appDir, 'WorkbenchTerms.js'), 'utf8') }],
}).outputs;
const compiledContracts = compile({
  sources: ['DashboardContract.js', 'RunCandidateAPI.js', 'DashboardAnalysisAPI.js'].map(name => ({
    path: name,
    code: fs.readFileSync(path.join(appDir, name), 'utf8'),
  })),
}).outputs;

// The list read goes through the real DashboardContract and APSWorkbenchTransport; only the network answer is stubbed.
function dashboard(fetch, globals = {}) {
  const window = {}, context = vm.createContext({ window, URLSearchParams, ...globals });
  browser(context, fetch);
  for (const out of compiledTerms) vm.runInContext(out.code, context, { filename: out.path });
  loadTransport(context);
  for (const out of compiledContracts) {
    vm.runInContext(out.code, context, { filename: out.path });
  }
  return context.__wbRuntime.getModule('DashboardContract.js');
}
const read = payload => {
  const C = dashboard(routeFetch({ [LIST]: () => JSON.parse(JSON.stringify(payload)) }));
  return C.list(C.scope({}));
};

async function slowRead() {
  let now = 0, next = 0;
  const timers = new Map();
  const timer = (fn, delay) => { const id = ++next; timers.set(id, { fn, at: now + delay }); return id; };
  // The healthy answer arrives after 45 seconds, inside the 60-second dashboard read limit.
  const C = dashboard(routeFetch({ [LIST]: () => new Promise(resolve => {
    timer(() => resolve(JSON.parse(JSON.stringify(payloads.healthy))), 45000);
  }) }), { setTimeout: timer, clearTimeout: id => timers.delete(id) });
  const reading = C.list(C.scope({})).then(value => ({ value }), error => ({ error }));
  await new Promise(resolve => setImmediate(resolve));
  while (Array.from(timers.values()).some(entry => entry.at <= 45000)) {
    const [id, entry] = Array.from(timers.entries()).sort((a, b) => a[1].at - b[1].at)[0];
    now = entry.at; timers.delete(id); entry.fn();
    await new Promise(resolve => setImmediate(resolve));
  }
  const outcome = await reading;
  assert.equal(outcome.error, undefined);
  assert(outcome.value.data.items.length > 0 && outcome.value.data.analysis);
}

(async () => {
  for (const payload of [payloads.healthy, payloads.unavailable]) {
    const result = await read(payload);
    assert(result.data.items.length > 0);
    assert.equal(result.data.analysis_error, null);
    assert.equal(JSON.stringify(result.data.analysis.plan), JSON.stringify(result.data.plan));
  }
  const invalid = JSON.parse(JSON.stringify(payloads.healthy));
  invalid.data.analysis.plan.plan_ref = 'f'.repeat(48);
  const result = await read(invalid);
  assert.equal(result.data.items.length, invalid.data.items.length);
  assert.equal(result.data.analysis, null);
  assert.match(result.data.analysis_error, /影响分析读取失败/);
  const absentReceipt = routeFetch({ 'GET /api/workbench/v1/commands/*': () => ({ state: 'not_observed', receipt: null, may_be_in_flight: true, resolution: 'unresolved' }) });
  assert.equal(await dashboard(absentReceipt).lookup({ request_key: 'dashboard-' + 'a'.repeat(48) }), null);
  await slowRead();
})().catch(error => { console.error(error); process.exitCode = 1; });
