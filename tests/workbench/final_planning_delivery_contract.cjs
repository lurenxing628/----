'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(process.argv[2]));
const context = vm.createContext({ window: {} });
for (const name of ['PointContract.js', 'RunCandidateAPI.js']) vm.runInContext(
  fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context, { filename: name });
const api = context.window.RunCandidateAPI, ref = input.data.candidate.candidate_ref;
api.workspace(input, ref);
const checks = [
  value => { delete value.data.delivery_risks; },
  value => { value.data.delivery_risks.candidate_ref = 'f'.repeat(48); },
  value => { value.data.delivery_risks.scope.range_start = '2026-09-09T08:00:00'; },
  value => { value.data.delivery_risks.basis.current_entities_consulted = true; },
  value => { value.data.delivery_risks.items[0].last_operations[0].row_ref = 'f'.repeat(48); },
  value => { value.data.delivery_risks.items[0].last_operations[0].piece_id = 'another-piece'; },
  value => { value.data.delivery_risks.items[0].risk = 'unknown'; },
  value => { value.data.delivery_risks.summary.overdue_count++; },
  value => { value.data.delivery_risks.summary.total_tardiness_hours += 10; },
  value => { value.data.delivery_risks.items[0].raw = {}; },
];
for (const change of checks) {
  const invalid = JSON.parse(JSON.stringify(input)); change(invalid);
  assert.throws(() => api.workspace(invalid, ref));
}
console.log(JSON.stringify({ valid: 1, rejected: checks.length }));
