'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const fixtures = require('./plan_ui_fixtures.cjs'), root = path.resolve(__dirname, '../..');
const runtime = vm.createContext({ window: {}, console }); runtime.window = runtime;
for (const name of ['resource-contract.js', 'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'PointGanttModel.js', 'PlanGanttModel.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), runtime);
}
const data = fixtures.workspace(fixtures.ref(3)).data, M = runtime.PlanGanttModel;
assert.equal(data.projections.baseline.state, 'available');
data.projections.baseline.items.forEach((row, index) => { row.change = index % 2 ? 'changed' : 'unchanged'; });
const original = JSON.stringify(data);
const wanted = new Set(data.projections.baseline.items.filter(row => row.change === 'changed').map(row => row.operation_ref));
for (const mode of ['machine', 'operator', 'batch']) {
  for (const baseline of [false, true]) {
    const full = M.layout(data, mode, '', baseline), filtered = M.layout(data, mode, '', baseline, 1000, true);
    assert.deepEqual(Array.from(filtered.tasks, task => task.task_ref), data.tasks.filter(task => wanted.has(task.operation_ref)).map(task => task.task_ref));
    assert(filtered.rows.every(row => row.items.every(item => wanted.has(item.task.operation_ref))));
    assert.equal(filtered.start, full.start); assert.equal(filtered.end, full.end);
    assert.equal(M.layout(data, mode, 'no-matching-operation', baseline, 1000, true).tasks.length, 0);
  }
}
assert.equal(JSON.stringify(data), original);
data.projections.baseline = { state: 'unavailable', reason: 'No captured source' };
assert.equal(M.layout(data, 'machine', '', false, 1000, true).tasks.length, 0);
console.log(JSON.stringify({ model_only: true, real_full_entry_evidence: false, checks: 8 }));
