'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = { window: {}, Date, URLSearchParams, AbortController, setTimeout, clearTimeout };
for (const name of ['PointContract.js', 'RunCandidateAPI.js', 'RunBaselineAPI.js']) {
  vm.runInNewContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context, { filename: name });
}
const { RunCandidateAPI: A, RunBaselineAPI: B, PointContract: P } = context.window;
const clone = value => JSON.parse(JSON.stringify(value));
let checks = 0;
for (const fixture of input.fixtures) {
  const before = JSON.stringify(fixture);
  const data = A.workspace(fixture.workspace, input.candidate_ref, fixture.scope, input.run_ref);
  B.validate(fixture.baseline, data);
  assert.equal(JSON.stringify(fixture), before, 'Read validation changed the original DTO');
  checks += 3;
}
const full = input.fixtures[0], task = full.workspace.data.tasks.find(P.isPoint);
assert(task && task.start === task.end);
const malformed = [
  row => { delete row.event_kind; },
  row => { row.occupies_resources = true; },
  row => { row.duration_seconds = 1; },
  row => { for (const key of P.fields) delete row[key]; },
  row => { row.event_kind = 'duration'; },
  row => { row.duration_seconds = '0'; },
  row => { row.unexpected = true; }
];
for (const edit of malformed) {
  const bad = clone(full.workspace);
  edit(bad.data.tasks.find(row => row.row_ref === task.row_ref));
  assert.throws(() => A.workspace(bad, input.candidate_ref), 'Malformed point escaped candidate validation');
  const badBaseline = clone(full.baseline);
  edit(badBaseline.data.comparisons.find(row => row.operation_ref === task.operation_ref).candidate);
  assert.throws(() => B.validate(badBaseline, full.workspace.data), 'Malformed point escaped baseline validation');
  checks += 2;
}
const left = input.fixtures[1], right = input.fixtures[2];
assert(left.workspace.data.tasks.some(row => row.row_ref === task.row_ref));
assert(!right.workspace.data.tasks.some(row => row.row_ref === task.row_ref));
const pointComparison = full.baseline.data.comparisons.find(row => row.operation_ref === task.operation_ref);
assert.equal(pointComparison.candidate.elapsed_hours, 0);
assert.equal(pointComparison.improvement_assessment, null);
assert.equal(pointComparison.comparison_available, input.has_baseline);
if (input.all_points) assert.equal(full.workspace.data.candidate_span.start, full.workspace.data.candidate_span.end);
console.log(JSON.stringify({ checks: checks + 6, point_ref: task.row_ref, read_only: true, source: 'actual worker and HTTP DTOs' }));
