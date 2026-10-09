'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const payloads = JSON.parse(fs.readFileSync(0, 'utf8'));
const window = {};
const context = vm.createContext({ window, AbortController, URLSearchParams, setTimeout, clearTimeout });
for (const name of ['DashboardContract.js', 'RunCandidateAPI.js', 'DashboardAnalysisAPI.js']) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', name), 'utf8'), context);
}
const read = payload => window.DashboardContract.create(async () => ({
  ok: true, status: 200, headers: { get: () => 'application/json' },
  json: async () => JSON.parse(JSON.stringify(payload))
})).list({});

async function slowRead() {
  let now = 0, next = 0;
  const timers = new Map(), delayedWindow = {};
  const timer = (fn, delay) => { const id = ++next; timers.set(id, { fn, at: now + delay }); return id; };
  const delayedContext = vm.createContext({ window: delayedWindow, AbortController, URLSearchParams,
    setTimeout: timer, clearTimeout: id => timers.delete(id) });
  for (const name of ['DashboardContract.js', 'RunCandidateAPI.js', 'DashboardAnalysisAPI.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', name), 'utf8'), delayedContext);
  }
  const reading = delayedWindow.DashboardContract.create((url, options) => new Promise((resolve, reject) => {
    const response = timer(() => resolve({ ok: true, status: 200, headers: { get: () => 'application/json' },
      json: async () => JSON.parse(JSON.stringify(payloads.healthy)) }), 45000);
    options.signal.addEventListener('abort', () => {
      timers.delete(response); const error = new Error('读取超时'); error.name = 'AbortError'; reject(error);
    }, { once: true });
  })).list({}).then(value => ({ value }), error => ({ error }));
  while (Array.from(timers.values()).some(entry => entry.at <= 45000)) {
    const [id, entry] = Array.from(timers.entries()).sort((a, b) => a[1].at - b[1].at)[0];
    now = entry.at; timers.delete(id); entry.fn();
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
  await slowRead();
})().catch(error => { console.error(error); process.exitCode = 1; });
