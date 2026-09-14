'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const plain = value => JSON.parse(JSON.stringify(value)), report = { type: 'pure_policy_unit_synthetic_adapters', cases: [] };
const sandbox = { window: { APSResourceContract: { failure: message => new Error(message) },
  FieldContract: { query: value => value }, ResourceTableFilterModel: { signature: value => JSON.stringify(value), rule: value => value } } };
for (const name of ['FieldAPI.js', 'CalibrationAPI.js']) vm.runInNewContext(fs.readFileSync(path.resolve(__dirname, '../../frontend/workbench/app/' + name), 'utf8'), sandbox);
const field = sandbox.window.FieldAPI, calibration = sandbox.window.CalibrationAPI;
async function test(name, callback) { await callback(); report.cases.push({ name, passed: true }); }
async function main() {
  const plan = '1'.repeat(48), task = '2'.repeat(48), operation = '3'.repeat(48);
  const scope = { plan_ref: plan, query: 'original', batch_ids: ['B1', 'B2'], resource_ref: '4'.repeat(48), resource_type: 'machine' };
  const input = { ...scope, page: 2, size: 10, task_ref: task, operation_ref: operation };
  const result = (page, returnedScope = scope, rows = [{ task_ref: task, operation_ref: operation }]) => ({ meta: { snapshot_ref: 'fresh-token' },
    data: { scope: returnedScope, page: { number: page, size: 10 }, tasks: rows } });
  await test('field-legacy-tokens-ignored-only-permanent-view-restored', () => {
    const saved = { plan_ref: plan, task_ref: task, operation_ref: operation, snapshot_ref: 'expired',
      scope: { ...scope, snapshot_ref: 'expired' }, table: { page: 2, size: 10, snapshot_ref: 'expired' } };
    const original = JSON.stringify(saved);
    assert.deepEqual(plain(field.initial(saved)), input); assert.equal(JSON.stringify(saved), original);
  });
  await test('field-new-read-first-page-without-selector-then-original-page-and-selector', async () => {
    const calls = [], original = JSON.stringify(input);
    const actual = await field.readView({ list: async query => { calls.push(plain(query)); return result(query.page); } }, input);
    assert.equal(actual.data.page.number, 2); assert.equal(JSON.stringify(input), original);
    assert.deepEqual(calls, [{ ...scope, page: 1, size: 10 }, { ...input, snapshot_ref: 'fresh-token' }]);
  });
  await test('field-permanent-plan-page-scope-and-original-ref-mismatches-rejected', async () => {
    await assert.rejects(field.readView({ list: async () => result(1, { ...scope, plan_ref: '5'.repeat(48) }) }, input));
    await assert.rejects(field.readView({ list: async () => result(1) }, input));
    await assert.rejects(field.readView({ list: async query => result(query.page, scope, []) }, input));
    await assert.rejects(field.readView({ list: async query => result(query.page, query.snapshot_ref ? { ...scope, query: 'other' } : scope) }, input));
    await assert.rejects(field.readView({ list: async () => { throw new Error('must not read'); } }, { operation_ref: operation }), /缺少明确任务/);
  });
  await test('field-new-navigation-without-explicit-page-can-locate-original-task', async () => {
    const calls = [], { page, ...navigation } = input;
    const actual = await field.readView({ list: async query => { calls.push(plain(query)); return result(query.task_ref ? 2 : 1); } }, navigation);
    assert.equal(actual.data.page.number, 2); assert.equal(calls.length, 2); assert.equal(calls[1].task_ref, task);
  });
  const saved = { scope: { query: 'P1', source: 'internal', part_ref: '6'.repeat(48), snapshot_ref: 'expired' },
    table: { page: 3, size: 10, sort: 'sample_count', direction: 'desc', snapshot_ref: 'expired' }, snapshot_ref: 'expired', selected: task, sample_ref: operation };
  const calInput = calibration.initial(saved);
  const calResponse = query => ({ ok: true, schema_version: 1, warnings: [],
    meta: { source: 'production', time_basis: 'factory_local', as_of: '2026-09-11T00:00:00', snapshot_ref: 'fresh-token' },
    data: { scope: plain({ ...calInput, page: query.page }), summary: { total: 0, suggested: 0, insufficient_data: 0, over_20_percent: 0 },
      capabilities: { view: true, export: true }, blocked_reasons: [], source_constraints: [], lineage_available: true,
      exports: { url: '/api/workbench/v1/calibration/export', scope: 'all_filtered_suggestions', formats: ['csv'] },
      items: [], page: { number: query.page, size: 10, total: 0, total_pages: 0 } } });
  await test('calibration-restored-page-without-old-token-does-not-weaken-live-input', () => {
    assert.equal(calInput.snapshot_ref, undefined); assert.equal(calInput.page, 3); assert.equal(calInput.part_ref, saved.scope.part_ref);
    assert.equal(saved.snapshot_ref, 'expired'); assert.throws(() => calibration.input(calInput), /翻页位置已失效/);
  });
  await test('calibration-fresh-first-page-then-original-page-same-part-and-filters', async () => {
    const calls = [];
    const actual = await calibration.readView({ read: async query => { calls.push(plain(query)); return calResponse(query); } }, calInput);
    assert.equal(actual.data.page.number, 3); assert.equal(calls.length, 2);
    assert.deepEqual(calls, [{ ...plain(calInput), page: 1 }, { ...plain(calInput), snapshot_ref: 'fresh-token' }]);
  });
  await test('calibration-wrong-page-or-scope-not-silently-substituted', async () => {
    await assert.rejects(calibration.readView({ read: async query => calResponse({ ...query, page: 1 }) }, calInput));
    await assert.rejects(calibration.readView({ read: async query => { const value = calResponse(query); value.data.scope.part_ref = '7'.repeat(48); return value; } }, calInput));
  });
  for (const [name, module, method, original] of [['field', field, 'list', input], ['calibration', calibration, 'read', calInput]]) {
    await test(name + '-live-409-is-one-request-with-identical-error-no-fresh-fallback', async () => {
      const calls = [], failure = { error: { code: 'snapshot_stale' }, committed: false }, active = { ...original, snapshot_ref: 'expired' };
      await assert.rejects(module.readView({ [method]: async query => { calls.push(plain(query)); throw failure; } }, active), error => error === failure);
      assert.deepEqual(calls, [plain(active)]);
    });
  }
  fs.writeFileSync(path.join(process.argv[2], 'field-calibration-read-policy.json'), JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
