'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const context = { window: {}, console, Number, Error, URL, setTimeout };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../frontend/workbench/app/ReportAPI.js'), 'utf8'), context);
const API = context.window.ReportAPI;
const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const data = fixture.topics.delivery;
const clone = value => JSON.parse(JSON.stringify(value));
(async () => {
  const calls = [];
  const api = API.create({ query: async (...args) => {
    calls.push(args);
    if (args[0].startsWith('reports/')) return fixture.catalogs[args[0].split('/')[1]];
    if (args[0].startsWith('analytics/operations/')) {
      const result = clone(data); result.data.detail = fixture.details[args[0].split('/').pop()]; return result;
    }
    return fixture.topics[args[1].topic];
  } });
  const input = { topic: 'records', source: 'production', query: 'search', snapshot_ref: 'original', page: 2 };
  assert.equal(await api.read(input), fixture.topics.records); assert.equal(calls[0][0], 'analytics'); assert.equal(calls[0][1], input);
  const operation = data.data.rows[0].operation_ref;
  const detail = await api.detail(operation, { ...input, plan_ref: data.data.plan.plan_ref, snapshot_ref: data.meta.snapshot_ref }); assert.equal(calls[1][0], 'analytics/operations/' + operation);
  assert.deepEqual(detail.data.detail, fixture.details[operation]);
  await api.catalog('downtime', { window_date_from: '2026-09-01', window_date_to: '2026-09-02' });
  assert.equal(calls[2][0], 'reports/downtime');
  await assert.rejects(api.detail(operation, input), /当前数据版本/);
  await assert.rejects(api.detail('23', input));
  await assert.rejects(api.catalog('unknown', {}));
  await assert.rejects(api.download('/api/workbench/v1/entities/machine/export', { snapshot_ref: 'a' }));
  await assert.rejects(api.download('/api/workbench/v1/analytics/export', {}));
  assert.throws(() => API.scope({ dateFrom: '2026-09-01' }));
  assert.throws(() => API.scope({ range_start: '2026-09-01T00:00:00' }));
  assert.equal(API.scope({ kind: 'execution_analysis', source: 'production', batch_ref: 'a' }).batch_ref, 'a');
  const candidate = JSON.parse(JSON.stringify(data)); candidate.data.plan.is_current_official = false;
  assert.throws(() => API.validate(candidate));
  const bad = JSON.parse(JSON.stringify(data)); delete bad.data.summary.completion_rate;
  assert.throws(() => API.validate(bad));
  const demo = JSON.parse(JSON.stringify(data)); demo.meta.source = 'demo'; assert.throws(() => API.validate(demo));
  Object.values(fixture.topics).forEach(value => assert.equal(API.validate(value), value));
  Object.values(fixture.catalogs).forEach(value => assert.equal(API.validate(value), value));
  assert.equal(data.data.summary.events, 5); assert.equal(data.data.summary.production_reports, 0);
  assert.equal(data.data.summary.records, 5); assert.equal(data.data.summary.effective_processing_hours, null);
  assert.equal(data.data.summary.known_effective_processing_hours, null);
  const mutations = [value => delete value.data.summary.production_reports, value => value.data.summary.records++,
    value => delete value.data.rows[0].production_report_count, value => delete value.data.rows[0].record_count,
    value => delete value.data.rows[0].known_completed_quantity, value => delete value.data.rows[0].effective_processing_hours];
  mutations.forEach(mutate => { const value = clone(data); mutate(value); assert.throws(() => API.validate(value)); });
  const missingLabel = clone(fixture.topics.records); delete missingLabel.data.rows[0].record_kind_label;
  assert.throws(() => API.validate(missingLabel));
  console.log(JSON.stringify({ transport: 'existing-query-only', fixture: 'captured-temporary-sqlite', topics: 5, catalogs: 4,
    ledger_rejections: mutations.length + 1, unknown_hours_preserved: true, writes: 0 }));
})().catch(error => { console.error(error); process.exitCode = 1; });
