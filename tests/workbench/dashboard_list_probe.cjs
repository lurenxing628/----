'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { routeFetch, browser, loadTransport, json, failure } = require('./route_fetch.cjs');
const payloads = JSON.parse(fs.readFileSync(0, 'utf8'));
const LIST = 'GET /api/workbench/v1/dashboard';

// The list read goes through the real DashboardContract and APSWorkbenchTransport; only the network answer is stubbed.
function dashboard(fetch, globals = {}) {
  const window = {}, context = vm.createContext({ window, URLSearchParams, ...globals });
  browser(context, fetch);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/WorkbenchTerms.js'), 'utf8'), context);
  loadTransport(context);
  for (const name of ['DashboardContract.js', 'RunCandidateAPI.js', 'ResourceProjectionContract.js', 'DashboardAnalysisAPI.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', name), 'utf8'), context);
  }
  return window.DashboardContract;
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
  invalid.data.items = null;
  await assert.rejects(read(invalid), /值班台读到的数据不完整/);
  const absentReceipt = routeFetch({ 'GET /api/workbench/v1/commands/*': () => json(failure('receipt_not_found', '未查到该操作结果。'), 404) });
  assert.equal(await dashboard(absentReceipt).lookup({ request_key: 'dashboard-' + 'a'.repeat(48) }), null);
  await slowRead();
})().catch(error => { console.error(error); process.exitCode = 1; });
