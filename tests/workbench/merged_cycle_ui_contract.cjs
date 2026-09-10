'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8')), context = {window: null}; context.window = context; vm.createContext(context);
for (const name of ['resource-contract.js', 'ProcessContract.js'])
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', name), 'utf8'), context);
const P = context.APSProcessContract, raw = input.raw, checks = [];
assert.equal(P.detail(raw, raw.data.ref), raw);
for (const row of raw.data.operations) {
  const label = P.groupCycle(row, raw.data.external_groups);
  assert.equal(!!label, row.external_days_source === 'group');
  if (label) { const g = raw.data.external_groups.find(g => g.ref === row.external_group_ref); assert(label.includes(g.start_sequence + ' 至 ' + g.end_sequence)); }
}
if (input.mutate) {
  const variants = {
    missing_source: d => { delete d.operations[1].external_days_source; },
    unknown_source: d => { d.operations[1].external_days_source = 'supplier'; },
    object_source: d => { d.operations[1].external_days_source = {}; },
    number_source: d => { d.operations[1].external_days_source = 1; },
    false_source: d => { d.operations[1].external_days_source = false; },
    null_operation: d => { d.operations[1].external_days_source = 'operation'; },
    group_with_value: d => { d.operations[1].external_days = 6.75; },
    value_with_null_source: d => { Object.assign(d.operations[1], {external_days: 2, external_days_source: null}); },
    zero_operation: d => { Object.assign(d.operations[1], {external_days: 0, external_days_source: 'operation'}); },
    missing_group: d => { d.external_groups = []; },
    null_group_ref: d => { d.operations[1].external_group_ref = null; },
    unknown_group_ref: d => { d.operations[1].external_group_ref = 'f'.repeat(48); },
    other_group_ref: d => { d.operations[1].external_group_ref = d.external_groups.find(g => g.total_days === 9.5).ref; },
    separate_group: d => { d.external_groups.find(g => g.total_days === 6.75).merge_mode = 'separate'; },
    missing_total: d => { d.external_groups.find(g => g.total_days === 6.75).total_days = null; },
    invalid_total: d => { d.external_groups.find(g => g.total_days === 6.75).total_days = -1; },
    nonfinite_total: d => { d.external_groups.find(g => g.total_days === 6.75).total_days = Infinity; },
    group_problem: d => { d.external_groups.find(g => g.total_days === 6.75).issues.push({code: 'external_group_members_invalid', message: 'bad member'}); },
    unknown_mode: d => { d.external_groups.find(g => g.total_days === 6.75).merge_mode = 'unknown'; },
    inactive_member: d => { d.operations[1].status = 'deleted'; },
    internal_member: d => { d.operations[1].source = 'internal'; },
    invalid_sibling: d => { const r = d.operations.find(r => r.sequence === 25); r.source = 'internal'; r.external_days_source = null; },
    reversed_range: d => { const g = d.external_groups.find(g => g.total_days === 6.75); g.start_sequence = 30; },
    duplicate_group: d => { d.external_groups.push(d.external_groups[0]); },
    false_cross_part: d => { d.operations[1].issues.push({code: 'external_group_part_mismatch', message: 'cross part'}); },
  };
  for (const [name, change] of Object.entries(variants)) {
    const broken = JSON.parse(JSON.stringify(raw)); change(broken.data);
    assert.throws(() => P.detail(broken, broken.data.ref), undefined, name); checks.push(name);
  }
  const large = JSON.parse(JSON.stringify(raw)), row = large.data.operations.find(r => r.sequence === 40);
  const group = large.data.external_groups.find(g => g.ref === row.external_group_ref);
  row.sequence = group.start_sequence = group.end_sequence = '9223372036854775807';
  P.detail(large, large.data.ref); assert(P.groupCycle(row, large.data.external_groups).includes(row.sequence));
  group.end_sequence = '9223372036854775806';
  assert.throws(() => P.detail(large, large.data.ref)); checks.push('sqlite_int64_exact_range');
}
console.log(JSON.stringify({accepted: true, rejected: checks}));
