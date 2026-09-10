'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const source = path.resolve(__dirname, '../../frontend/workbench/app/ReportAPI.js'), sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync(source, 'utf8'), sandbox);
const api = sandbox.window.ReportAPI, plain = value => JSON.parse(JSON.stringify(value)), report = { type: 'pure_policy_unit', cases: [] };
async function test(name, callback) { await callback(); report.cases.push({ name, passed: true }); }
async function main() {
  await test('legacy-table-token-is-not-part-of-permanent-view', () => {
    assert.deepEqual(plain(api.table({ topic: 'records', page: 3, size: 10, sort: 'event_time', direction: 'desc', snapshot_ref: 'old-process' }, 'records')),
      { topic: 'records', page: 3, size: 10, sort: 'event_time', direction: 'desc' });
    for (const value of [{ page: 0 }, { page: '2' }, { size: 5 }, { direction: 'sideways' }, { sort: 'unknown' }]) assert.throws(() => api.table(value));
  });
  const input = { plan_ref: '1'.repeat(48), source: 'production', query: 'original', topic: 'records', page: 3, size: 10, sort: 'event_time', direction: 'asc' };
  const response = (page, plan = input.plan_ref) => ({ ok: true, meta: { snapshot_ref: 'new-token' }, data: { topic: 'records',
    plan: { plan_ref: plan }, scope: { source: 'production', plan_ref: plan, query: 'original' }, page: { number: page, size: 10 } } });
  await test('fresh-read-page-one-then-exact-target-with-new-token', async () => {
    const calls = [], snapshot = JSON.stringify(input);
    const result = await api.readView({ read: async value => { calls.push(plain(value)); return response(value.page); } }, input);
    assert.equal(result.data.page.number, 3); assert.equal(JSON.stringify(input), snapshot);
    assert.equal(calls.length, 2); assert.equal(calls[0].page, 1); assert.equal(calls[0].snapshot_ref, undefined);
    assert.deepEqual(calls[1], { ...input, snapshot_ref: 'new-token' });
  });
  await test('live-stale-token-is-one-request-and-same-visible-error', async () => {
    const failure = { code: 'snapshot_stale', committed: false }, calls = [];
    await assert.rejects(api.readView({ read: async value => { calls.push(plain(value)); throw failure; } }, { ...input, snapshot_ref: 'old-token' }), error => error === failure);
    assert.deepEqual(calls, [{ ...input, snapshot_ref: 'old-token' }]);
  });
  await test('unavailable-target-page-does-not-report-page-one-as-restored', async () => {
    await assert.rejects(api.readView({ read: async () => response(1) }, input), /原报表页已不可用/);
  });
  await test('different-plan-is-not-a-fresh-read-fallback', async () => {
    const calls = [];
    await assert.rejects(api.readView({ read: async value => { calls.push(value); return response(1, '2'.repeat(48)); } }, input), /计划或专题/);
    assert.equal(calls.length, 1);
  });
  fs.writeFileSync(path.join(process.argv[2], 'report-read-view-unit.json'), JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
