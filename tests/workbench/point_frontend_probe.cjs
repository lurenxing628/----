'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = { window: {}, console, URLSearchParams }; vm.createContext(context);
for (const name of ['WorkbenchTerms.js', 'WorkbenchFormat.js', 'resource-contract.js', 'PointContract.js',
  'PlanProcessOrder.js', 'PlanContract.js', 'PointGanttModel.js', 'PlanGanttModel.js',
  'RunCandidateModel.js', 'RunBaselineModel.js', 'TrialContract.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context, {filename: name});
}
const W = context.window, F = input.fixtures, clone = value => JSON.parse(JSON.stringify(value));
let assertions = 0;
function ok(value, message) { assertions++; assert.ok(value, message); }
function reject(action) { assertions++; assert.throws(action); }
W.APSPlanContract.workspace(F.plan, input.identity.plan_ref);
W.APSPlanContract.workspace(F.initial, input.identity.initial_plan_ref);
W.TrialContract.workspace(F.trial.data); W.TrialContract.workspace(F.saved.data);
for (const side of ['left', 'right']) {
  const fixture = F['plan_' + side]; W.APSPlanContract.workspace(fixture.payload, input.identity.plan_ref, fixture.scope);
  const initial = F['initial_' + side]; W.APSPlanContract.workspace(initial.payload, input.identity.initial_plan_ref, initial.scope);
}
W.APSPlanContract.workspace(F.plan_until_last.payload, input.identity.plan_ref, F.plan_until_last.scope);
const point = F.plan.data.tasks.find(W.PointContract.isPoint);
ok(!F.plan_right.payload.data.tasks.some(t => W.PointContract.isPoint(t) && t.start === point.start), 'Right boundary excludes point');
ok(F.plan_left.payload.data.tasks.some(t => t.task_ref === point.task_ref), 'Left boundary includes point');
for (const edit of [t => delete t.event_kind, t => delete t.duration_seconds, t => t.occupies_resources = true,
  t => t.duration_seconds = 1, t => t.duration_seconds = '0', t => t.event_kind = 'interval', t => t.end = '2026-09-09T09:00:00']) {
  const bad = clone(F.plan); edit(bad.data.tasks.find(t => t.task_ref === point.task_ref));
  reject(() => W.APSPlanContract.workspace(bad, input.identity.plan_ref));
  const trial = clone(F.trial.data); edit(trial.tasks.find(W.PointContract.isPoint)); reject(() => W.TrialContract.workspace(trial));
}
const badHistory = clone(F.saved.data); badHistory.change_history[0].task_ref = 'a'.repeat(48);
reject(() => W.TrialContract.workspace(badHistory));
const allZero = F.candidate.data.tasks.every(W.PointContract.isPoint);
if (allZero) {
  ok(F.candidate.data.task_span.start === F.candidate.data.task_span.end, 'True zero-width candidate span remains zero');
  ok(F.initial.data.plan_span.start === F.initial.data.plan_span.end, 'True zero-width official span remains zero');
  const initial = W.PlanGanttModel.layout(F.initial.data, 'machine', '', false, 600);
  ok(initial.rows.length === F.initial.data.tasks.length && initial.start < initial.end, 'Zero-span plan displays every point on a finite axis');
}
function geometry(model, width, candidate) {
  ok(Number.isFinite(model.start) && model.start < model.end, 'Finite display viewport');
  ok(model.conflicts === undefined || model.conflicts.size === 0, 'Points never create resource conflicts');
  const references = new Set();
  for (const row of model.rows) {
    if (row.point) {
      ok(row.overlap === undefined || row.overlap === 0, 'No point overlap warning');
      row.items.forEach((item, i) => {
        ok(item.start === item.end, 'No duration inflation');
        references.add(candidate ? item.task.row_ref : item.task.task_ref);
        if (i) ok((item.start - row.items[i - 1].start) / (model.end - model.start) * width >= 28 - 1e-6, 'Nonoverlapping hit areas');
        const x = (item.start - model.start) / (model.end - model.start) * width;
        ok(W.PointGanttModel.hit(row.items, x + 10, 24, model, width, 0, 24) === item, 'Pixel hit tolerance');
        ok(!W.PointGanttModel.hit(row.items, x, 39, model, width, 0, 24), 'Y hit excludes neighboring tracks');
      });
    } else ok(row.items.every(i => !W.PointContract.isPoint(i.task)), 'Normal bars isolated from points');
  }
  return references;
}
const before = JSON.stringify(F);
for (const width of [240, 600, 1400, 12000]) for (const mode of ['machine', 'operator', 'batch']) {
  const model = W.PlanGanttModel.layout(F.plan.data, mode, '', true, width), refs = geometry(model, width, false);
  for (const task of F.plan.data.tasks.filter(W.PointContract.isPoint)) ok(refs.has(task.task_ref), 'Current point retained');
  for (const item of F.plan.data.projections.baseline.items) if (W.PointContract.isPoint(item.before)) ok(refs.has(item.before.task_ref), 'Baseline point retained');
  geometry(W.PointGanttModel.candidateRows(W.RunCandidateModel.layout(F.candidate.data, mode, '', width), width), width, true);
  const filtered = W.PlanGanttModel.layout(F.plan.data, mode, 'Point 00', false, width);
  ok(filtered.tasks.length === 1 && W.PointContract.isPoint(filtered.tasks[0]), 'Real search retains point');
}
ok(JSON.stringify(F) === before, 'All source DTOs unchanged by validation/layout');
for (const row of F.plan.data.projections.occupancy.resources) {
  ok(row.overlap_hours === 0 && row.outside_available_hours === 0, 'No invented overlap or night hours');
  if (allZero) ok(row.occupied_hours === 0 && row.arranged_hours === 0 && row.segments.length === 0, 'Point-only resource occupancy stays zero');
}
console.log(JSON.stringify({ assertions, allZero, real_tasks: F.plan.data.task_count, real_history: F.saved.data.change_history.length, source: 'real temporary engine and HTTP DTOs' }));
