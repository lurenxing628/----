'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const repo = path.resolve(__dirname, '../..'), fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const context = vm.createContext({ window: {}, URLSearchParams, AbortController, setTimeout, clearTimeout });
for (const name of ['RunCandidateAPI.js', 'RunCandidateAnalysisAPI.js']) vm.runInContext(fs.readFileSync(path.join(repo, 'frontend/workbench/app', name), 'utf8'), context, { filename: name });
const A = context.window.RunCandidateAnalysisAPI, clone = value => JSON.parse(JSON.stringify(value));
for (const fixture of fixtures) {
  for (const name of ['analysis', 'history']) {
    const payload = fixture[name], d = payload.data, validate = value => A[name](value, d.candidate_ref, d.run_ref);
    assert.equal(validate(payload), d);
    assert.throws(() => A[name](payload, 'f'.repeat(48), d.run_ref));
    assert.throws(() => A[name](payload, d.candidate_ref, 'f'.repeat(48)));
    const missing = clone(payload); delete missing.data.run_ref; assert.throws(() => validate(missing));
    const wrongEnvelope = clone(payload); wrongEnvelope.ok = false; assert.throws(() => validate(wrongEnvelope));
  }
  const value = fixture.analysis, d = value.data;
  for (const edit of [
    p => { p.data.metrics.changed_operation_count.known_subtotal += 1; },
    p => { p.data.metrics.overdue_count.value = 999; },
    p => { p.data.batches[0].before.due_date = '2050-01-01'; },
    p => { p.data.operations.operation_refs.push(p.data.operations.operation_refs[0]); },
    p => { p.data.basis.scope = 'visible_tasks'; },
    p => { p.data.delivery_deltas.overdue_count = 999; },
    p => { p.data.batch_refs = []; },
  ]) { const bad = clone(value); edit(bad); assert.throws(() => A.analysis(bad, d.candidate_ref, d.run_ref)); }
  for (const metric of Object.values(d.metrics)) if (metric.value === null) {
    assert(metric.reason && metric.unknown_count > 0 && metric.known_subtotal >= 0);
  }
  if (fixture.history.data.items.length) {
    const bad = clone(fixture.history); bad.data.items[0].candidate_ref = 'f'.repeat(48);
    assert.throws(() => A.history(bad, d.candidate_ref, d.run_ref));
    const gaps = clone(fixture.history); gaps.data.items[0].evidence_gaps.push({ code: 'invalid', message: 'Missing evidence' });
    assert.throws(() => A.history(gaps, d.candidate_ref, d.run_ref));
  }
}
console.log(JSON.stringify({ status: 'passed', source: 'real_api_envelopes', cases: fixtures.length }));
