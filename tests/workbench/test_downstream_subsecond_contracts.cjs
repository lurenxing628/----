'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const W = { WorkbenchTerms: { report_actions: {} } }, context = vm.createContext({ window: W, Date });
for (const file of ['resource-contract.js', 'PointContract.js', 'WorkbenchFormat.js', 'FieldContract.js',
  'ActualGanttContract.js', 'RunCandidateAPI.js', 'RunBaselineAPI.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8'), context, { filename: file });
}
W.ActualGanttModel = { states: W.FieldContract.states, lateLabels: { all: '全部' } };
if (process.argv[2] === 'actual') {
  const query = { plan_ref: input.actual.data.plan.plan_ref };
  W.ActualGanttContract.workspace(input.actual, query);
  W.FieldContract.query(input.field, 'list');
  const chain = input.actual.data.critical_chain;
  assert.equal(chain.state, 'available');
  assert.equal(chain.edges.length, 1);
  assert.equal(chain.edges[0].gap_minutes, 0);
  const broken = JSON.parse(JSON.stringify(input.actual));
  broken.data.critical_chain.edges[0].gap_minutes = 1;
  assert.throws(() => W.ActualGanttContract.workspace(broken, query));
  const micro = input.field.data.tasks.find(task => task.planned_end.endsWith('.000001'));
  assert(micro);
  assert.equal(W.FieldContract.date(micro.planned_end), '2026-09-09 08:00:00.000001');
  assert.equal(W.FieldContract.validTime(micro.planned_end), false, 'Manual report input remains seconds-only');
  for (const bad of ['2026-02-29T08:00:00.000001', '2026-09-09T08:00:00.000000',
    '2026-09-09T08:00:00.1', '2026-09-09T08:00:00.000001Z', '2026-09-09T08:00:00.000001\n']) {
    assert.equal(W.ActualGanttContract.local(bad), false, bad);
  }
  console.log(JSON.stringify({ tasks: input.field.data.tasks.length, exact_gap_verified: true }));
} else {
  W.RunCandidateAPI.workspace(input.workspace, input.workspace.data.candidate.candidate_ref);
  W.RunBaselineAPI.validate(input.baseline, input.workspace.data);
  const row = input.baseline.data.comparisons.find(value => value.status === 'matched');
  assert(row && row.baseline_segments[0].interval_comparable);
  assert.equal(row.baseline_segments[0].end, '2026-09-09T08:00:00.123457');
  const broken = JSON.parse(JSON.stringify(input.baseline));
  broken.data.comparisons[0].baseline_segments[0].end = '2026-09-09T08:00:00.123455';
  assert.throws(() => W.RunBaselineAPI.validate(broken, input.workspace.data));
  console.log(JSON.stringify({ microsecond_baseline_comparable: true }));
}
