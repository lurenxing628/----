'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8')), context = { window: {}, Date };
for (const name of ['PointContract.js', 'TrialContract.js', 'PlanProcessOrder.js'])
  vm.runInNewContext(fs.readFileSync(path.resolve(__dirname, '../../frontend/workbench/app', name), 'utf8'), context, { filename: name });
const C = context.window.TrialContract, P = context.window.PlanProcessOrder, clone = value => JSON.parse(JSON.stringify(value));
const { draft, plan, origin } = input, other = 'f'.repeat(48); let checks = 0;
function pass(fn) { fn(); checks++; }
function rejects(fn) { assert.throws(fn); checks++; }
pass(() => C.workspace(draft, { draft_ref: draft.draft_ref }));
pass(() => C.target({ base: { plan_ref: origin.plan_ref }, task_origin: origin, scope: { query: 'item-B' } }));
pass(() => C.target({ draft_ref: draft.draft_ref, task_origin: origin }));
pass(() => assert.equal(C.originTask(draft, origin).source_task_ref, origin.task_ref));
for (const key of ['plan_ref', 'operation_ref', 'task_ref']) {
  const value = clone(origin); delete value[key]; rejects(() => C.origin(value));
  rejects(() => C.originTask(draft, { ...origin, [key]: other }));
}
for (const bad of [null, [], {}, { ...origin, extra: true }, { ...origin, task_ref: 1 }, { ...origin, task_ref: other.toUpperCase() }]) rejects(() => C.origin(bad));
for (const bad of [
  { task_origin: origin }, { base: { candidate_ref: other }, task_origin: origin },
  { base: { plan_ref: other }, task_origin: origin }, { scenario_ref: other, task_origin: origin },
  { draft_ref: draft.draft_ref, base: { plan_ref: origin.plan_ref }, task_origin: origin },
  { draft_ref: draft.draft_ref, scope: { query: 'item-B' }, task_origin: origin },
]) rejects(() => C.target(bad));
const matched = C.originTask(draft, origin);
rejects(() => C.originTask({ ...draft, tasks: draft.tasks.concat(matched) }, origin));
rejects(() => C.originTask({ ...draft, scenario_ref: other }, origin));
pass(() => assert.equal(C.originTask(draft, origin).task_ref, matched.task_ref));
pass(() => assert.notEqual(matched.task_ref, origin.task_ref));
pass(() => assert.equal(P.validate(plan.projections.process_order, plan), true));
for (const change of [
  value => { value.items.pop(); },
  value => { value.items[0].task_ref = other; },
  value => { value.items[0].operation_ref = other; },
  value => { value.items.push(clone(value.items[0])); },
  value => { value.items[0].predecessor_operation_refs = [value.items[0].operation_ref]; },
  value => { value.items[0].predecessor_operation_refs = [other, other]; },
  value => { value.items[0].extra = true; },
  value => { value.basis = null; },
]) {
  const value = clone(plan.projections.process_order); change(value);
  pass(() => assert.equal(P.validate(value, plan), false));
}
const empty = { state: 'unavailable', basis: null, items: [], issues: [{ code: 'missing', message: 'Missing frozen source' }] };
pass(() => assert.equal(P.validate(empty, plan), true));
pass(() => assert.equal(P.validate({ ...empty, issues: [] }, plan), false));
pass(() => assert.equal(P.validate({ ...empty, items: plan.projections.process_order.items }, plan), false));
pass(() => assert.equal(P.relationships(plan, { task: plan.tasks[0], before: true }), null));
console.log(JSON.stringify({ checks, actual_dto: true, full_entry: false }));
