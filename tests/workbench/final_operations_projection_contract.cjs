'use strict';
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const input = JSON.parse(fs.readFileSync(0, 'utf8')), host = { window: {}, URLSearchParams, AbortController, setTimeout, clearTimeout };
for (const file of ['PointContract.js', 'RunCandidateAPI.js', 'RunBaselineAPI.js', 'DashboardContract.js', 'DashboardAnalysisAPI.js', 'DashboardCandidateComparisonAPI.js']) {
  vm.runInNewContext(fs.readFileSync('frontend/workbench/app/' + file, 'utf8'), host, { filename: file });
}
const W = host.window, clone = value => JSON.parse(JSON.stringify(value));
const workspace = input.workspace.data, baseline = input.baseline.data, candidate = workspace.candidate;
W.RunCandidateAPI.workspace(input.workspace, candidate.candidate_ref, input.scope, candidate.run_ref);
W.RunBaselineAPI.validate(input.baseline, workspace);
W.DashboardAnalysisAPI.validate(input.analysis, input.analysis.data.plan.plan_ref);
W.DashboardCandidateComparisonAPI.validate(input.comparison, workspace, baseline);
let rejected = 0;
for (const mutate of [value => { value.data.pressure.count = 99; }, value => { value.data.tasks[0].batch_ref = 'wrong'; },
  value => { value.data.plan.plan_ref = 'f'.repeat(48); }]) {
  const value = clone(input.analysis); mutate(value);
  assert.throws(() => W.DashboardAnalysisAPI.validate(value, input.analysis.data.plan.plan_ref)); rejected++;
}
for (const mutate of [value => { value.data.candidate.candidate_ref = 'f'.repeat(48); },
  value => { value.data.time_scope.range_end = '2026-09-28T00:00:00'; }, value => { value.data.batch_refs = []; },
  value => { value.data.summary.after.total_tardiness_hours += 1; }, value => { value.data.summary.changeover_delta += 1; },
  value => { value.data.resources[0].after.peak_utilization = 0.991; }, value => { value.data.capabilities.adopt = true; },
  value => { value.data.generation.current_entities_consulted = true; }]) {
  const value = clone(input.comparison); mutate(value);
  assert.throws(() => W.DashboardCandidateComparisonAPI.validate(value, workspace, baseline)); rejected++;
}
for (const value of [{ run_ref: candidate.run_ref, write_token: 'forbidden' }, { candidate_ref: candidate.candidate_ref },
  { run_ref: candidate.run_ref, range_start: input.scope.range_end, range_end: input.scope.range_start }]) {
  assert.throws(() => W.DashboardCandidateComparisonAPI.context(value)); rejected++;
}
assert.equal(rejected, 14);
process.stdout.write(JSON.stringify({ valid: true, rejected, candidate_ref: candidate.candidate_ref }) + '\n');
