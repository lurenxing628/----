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
})().catch(error => { console.error(error); process.exitCode = 1; });
