'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const F = require('./plan_ui_fixtures.cjs'), root = path.resolve(__dirname, '../..');
const runtime = vm.createContext({ window: {}, console }); runtime.window = runtime;
for (const name of ['WorkbenchFormat.js', 'resource-contract.js', 'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'PointGanttModel.js', 'PlanGanttModel.js']) vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), runtime);
const M = runtime.PlanGanttModel, P = runtime.APSPlanContract, checks = [];
function check(name, fn) { fn(); checks.push(name); }
function admitted(ref, scope = {}, options = {}) { const data = F.workspace(ref, scope, options); P.workspace(data, ref, scope); return data.data; }
check('typical real DTO shape admitted', () => {
  const data = admitted(F.ref(1)); assert.equal(data.task_count, 36);
  for (const task of data.tasks) assert.deepEqual(
    [task.piece_id, task.quantity, task.batch_quantity, task.quantity_basis, task.quantity_reason],
    [null, null, null, 'unknown', 'plan_target_not_recorded']);
});
check('current resource labels from directory', () => assert.equal(M.names(admitted(F.ref(1))).get(F.ref(500)), '数控车床 C01'));
check('null name preserves actual business code', () => assert.equal(M.names(admitted(F.ref(1), {}, { nullLabels: true })).get(F.ref(500)), 'M-0'));
check('unknown capacity remains null', () => assert.equal(admitted(F.ref(1), {}, { unknown: true }).projections.occupancy.resources[0].available_hours, null));
check('factory-local axis unaffected by DST and leap boundaries', () => {
  assert.equal(M.instant('2026-03-08T03:00:00') - M.instant('2026-03-08T01:00:00'), 7200000);
  assert.equal(M.wire(M.instant('0001-01-01T00:00:00')), '0001-01-01T00:00:00');
});
check('real span not fixed two-day or20h', () => {
  const data = admitted(F.ref(1)), model = M.layout(data, 'machine', '', false);
  assert.equal(model.start, M.instant(data.plan_span.start)); assert.equal(model.end, M.instant(data.plan_span.end)); assert(model.end - model.start > 86400000 * 2);
});
check('overlaps split without changing task times', () => {
  const data = admitted(F.ref(1), {}, { concurrent: true, count: 10000 }), model = M.layout(data, 'machine', '', false);
  assert.equal(model.rows.length, 10000); assert.equal(model.conflicts.size, 10000); assert.equal(model.locations.size, 10000);
  assert(model.rows.every(row => row.items[0].start === M.instant(data.tasks[0].start)));
  assert(M.visibleRows(model.rows, 0, 700).length < 20);
});
check('search preserves conflict against hidden tasks and complete time range', () => {
  const data = admitted(F.ref(1), {}, { concurrent: true, count: 10000 }), all = M.layout(data, 'machine', '', false), one = M.layout(data, 'machine', 'BATCH-09999', false);
  assert.equal(one.tasks.length, 1); assert(one.conflicts.has(one.tasks[0].task_ref)); assert.equal(one.start, all.start); assert.equal(one.end, all.end);
});
check('adjacent intervals are not conflicts', () => {
  const data = admitted(F.ref(1), {}, { dense: true, count: 10000 }), model = M.layout(data, 'machine', '', false);
  assert.equal(model.rows.length, 1); assert.equal(model.conflicts.size, 0); assert.equal(model.locations.size, 10000);
  assert.equal(M.visibleItems(model.rows[0].items, model.start, model.start + 60000).length, 1);
});
check('batch overlap is not asserted as resource conflict', () => {
  const data = admitted(F.ref(1)), model = M.layout(data, 'batch', '', false); assert.equal(model.conflicts.size, 0);
});
check('same-operation fragments do not fabricate resource conflicts', () => {
  const data = admitted(F.ref(1), {}, { concurrent: true, count: 3 });
  data.tasks.forEach(task => { task.operation_ref = data.tasks[0].operation_ref; });
  data.projections.occupancy.resources.forEach(row => { row.has_overlap = false; row.overlap_hours = 0; row.segments.forEach(segment => { segment.concurrent_operations = 1; }); });
  const model = M.layout(data, 'machine', '', false); assert.equal(model.rows.length, 3); assert.equal(model.conflicts.size, 0);
});
check('scenario baseline is unclipped and expands actual overview', () => {
  const data = admitted(F.ref(3)), model = M.layout(data, 'machine', '', true);
  assert(model.start < M.instant(data.plan_span.start)); assert(model.rows.some(row => row.before));
  assert.deepEqual(data.projections.baseline.compared_fields, ['start', 'end', 'machine_ref', 'operator_ref']);
  for (const item of data.projections.baseline.items) {
    for (const task of [item.before, item.after]) assert.deepEqual(
      [task.piece_id, task.quantity, task.batch_quantity, task.quantity_basis, task.quantity_reason],
      [null, null, null, 'unknown', 'plan_target_not_recorded']);
    assert.deepEqual(item.after, data.tasks.find(task => task.task_ref === item.after.task_ref));
  }
});
check('empty overlap scope is not completed delivery', () => {
  const data = admitted(F.ref(1), { range_start: '2026-10-01T00:00:00', range_end: '2026-10-02T00:00:00' });
  assert.equal(data.tasks.length, 0); assert.equal(data.projections.delivery_risks.state, 'available'); assert.equal(data.projections.delivery_risks.completeness, 'unknown');
});
check('bounded tick DOM for enormous sparse spans', () => {
  const ticks = M.ticks(M.instant('0001-01-01T00:00:00'), M.instant('9999-12-31T00:00:00'), 1000000, 500000, 1000); assert(ticks.length < 20);
});
check('input payload not mutated by layout or search', () => {
  const data = admitted(F.ref(3)), original = JSON.stringify(data); M.layout(data, 'operator', '张工', true); assert.equal(JSON.stringify(data), original);
});
console.log(JSON.stringify({ scope: 'plan-ui-model-mock', checks, assertions: checks.length }));
