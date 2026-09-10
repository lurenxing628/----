'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = { window: {}, Date, URLSearchParams, AbortController, setTimeout, clearTimeout };
vm.createContext(context);
for (const name of ['resource-contract.js', 'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'PointGanttModel.js', 'PlanGanttModel.js',
  'RunCandidateAPI.js', 'RunBaselineAPI.js', 'RunCandidateModel.js', 'TrialContract.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context, { filename: name });
}
const W = context.window, A = W.RunCandidateAPI, B = W.RunBaselineAPI, C = W.APSPlanContract;
const F = input.fixtures, clone = value => JSON.parse(JSON.stringify(value));
let checks = 0;
const ok = (value, message) => { checks++; assert(value, message); };
const reject = fn => { checks++; assert.throws(fn); };
const before = JSON.stringify(F);
A.workspace(F.candidate, input.candidate_ref); B.validate(F.baseline, F.candidate.data);
for (const kind of ['plan', 'old']) C.workspace(F[kind], F[kind].data.plan.plan_ref);
W.TrialContract.workspace(F.trial.data);
const piece = F.candidate.data.tasks.find(t => t.piece_id !== null);
for (const edit of [t => delete t.piece_id, t => delete t.batch_quantity, t => t.extra_unknown = true,
  t => t.piece_id = 1, t => t.quantity = t.batch_quantity, t => t.batch_quantity = false, t => t.piece_id = '']) {
  const bad = clone(F.candidate); edit(bad.data.tasks.find(t => t.operation_ref === piece.operation_ref));
  reject(() => A.workspace(bad, input.candidate_ref));
  const baseline = clone(F.baseline); edit(baseline.data.comparisons.find(t => t.operation_ref === piece.operation_ref));
  reject(() => B.validate(baseline, F.candidate.data));
}
for (const edit of [t => delete t.quantity_basis, t => delete t.piece_id, t => t.extra_unknown = true,
  t => t.quantity = false, t => t.quantity = -1, t => t.quantity_basis = 'current_batch', t => t.quantity_reason = 'fallback']) {
  const bad = clone(F.plan); edit(bad.data.tasks[0]); reject(() => C.workspace(bad, bad.data.plan.plan_ref));
}
const badBefore = clone(F.plan); badBefore.data.projections.baseline.items[0].after.batch_quantity = 99;
reject(() => C.workspace(badBefore, badBefore.data.plan.plan_ref));
for (const field of ['quantity', 'batch_quantity']) {
  const old = clone(F.old); old.data.tasks[0][field] = 1; reject(() => C.workspace(old, old.data.plan.plan_ref));
}
for (const quantity of [0, null]) {
  const candidate = clone(F.candidate), task = candidate.data.tasks.find(t => t.operation_ref === piece.operation_ref);
  task.quantity = quantity; task.execution_at_generation.target_quantity = quantity;
  A.workspace(candidate, input.candidate_ref);
  ok(W.RunCandidateModel.title(task).includes('本工序目标量：' + (quantity === 0 ? '0' : '未知')));
}
function geometry(model) {
  return { start: model.start, end: model.end, rows: model.rows.map(row => ({ top: row.top, height: row.height,
    items: row.items.map(item => [item.start, item.end]) })) };
}
for (const width of [1920, 1392, 640, 12800]) for (const mode of ['machine', 'operator', 'batch']) {
  for (const kind of ['plan', 'candidate']) {
    const data = F[kind].data, previous = clone(data);
    previous.tasks.forEach(task => { task.piece_id = null; task.quantity = null; task.batch_quantity = null; });
    const layout = kind === 'plan' ? data => W.PlanGanttModel.layout(data, mode, '', false, width) : data => W.RunCandidateModel.layout(data, mode, '', width);
    assert.deepEqual(geometry(layout(data)), geometry(layout(previous))); checks++;
  }
}
for (const pieceId of input.pieces) {
  ok(W.RunCandidateModel.matching(F.candidate.data.tasks, pieceId).length === 2);
  ok(W.PlanGanttModel.layout(F.plan.data, 'machine', pieceId, false).tasks.length === 2);
  const task = F.plan.data.tasks.find(row => row.piece_id === pieceId);
  ok(W.PlanGanttModel.taskTitle(task, W.PlanGanttModel.names(F.plan.data)).includes(pieceId));
}
ok(JSON.stringify(F) === before, 'Strict validation and layout must never mutate real DTOs');
console.log(JSON.stringify({ checks, read_only: true, real_http_dtos: true, physical_geometry_unchanged: true }));
