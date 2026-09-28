'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const mode = process.argv[2], input = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const context = vm.createContext({window: {}, Date, AbortController, URLSearchParams, setTimeout, clearTimeout});
for (const name of ['resource-contract.js', 'PointContract.js', 'TrialContract.js', 'TrialAPI.js',
  'PlanContract.js', 'PreflightContract.js', 'RunCandidateAPI.js', 'RunAdoptionAPI.js', 'TrialAdoptionAPI.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context, {filename: name});
}
const {TrialContract: T, APSPlanContract: P, RunCandidateAPI: R} = context.window;
const clone = value => JSON.parse(JSON.stringify(value));
const ref = 'a'.repeat(48), start = '2026-09-09T08:00:00.123456', end = '2026-09-09T08:00:00.123457';
const invalid = ['0000-01-01T00:00:00', '2026-02-29T08:00:00', '2026-04-31T08:00:00',
  '2026-00-01T08:00:00', '2026-13-01T08:00:00', '2026-09-00T08:00:00',
  '2026-09-09T24:00:00', '2026-09-09T08:60:00', '2026-09-09T08:00:60',
  '2026-09-09T08:00:00Z', start + '+08:00', '2026-09-09 08:00:00.123456',
  '2026-09-09T08:00:00.1', '2026-09-09T08:00:00.000000', start + '7', start + '\n'];
const scope = (low = start, high = end) => ({range_start: low, range_end: high});
const meta = as_of => ({request_ref: 'b'.repeat(32), source: 'production', time_basis: 'factory_local',
  snapshot_ref: 'c'.repeat(32), as_of});

function scopes() {
  const canonical = ['0001-01-01T00:00:00', '2024-02-29T23:59:59.000001',
    '2026-09-09T08:00:00', '9999-12-31T23:59:59.999999'];
  canonical.forEach(value => assert.equal(T.time(value), true, value));
  invalid.forEach(value => {
    assert.equal(T.time(value), false, value);
    assert.throws(() => T.scope(scope(value, '9999-12-31T23:59:59.999999')), value);
    assert.throws(() => P.workspaceScope(ref, scope(value, '9999-12-31T23:59:59.999999')), value);
  });
  for (const select of [value => T.scope(value), value => P.workspaceScope(ref, value),
    value => P.exportScope(ref, {...value, format: 'csv', snapshot_ref: 'snapshot'}),
    value => R.workspaceScope(ref, value)]) {
    const value = select(scope());
    assert.equal(value.range_start, start); assert.equal(value.range_end, end);
    assert.throws(() => select(scope(end, start)));
    assert.throws(() => select(scope(start, start)));
  }
  // Candidate query compatibility must neither truncate nor rewrite old 1–6 digit fractions.
  for (let width = 1; width <= 6; width++) {
    const value = '2026-09-09T08:00:00.' + '1'.repeat(width);
    assert.equal(R.workspaceScope(ref, scope(value, '2026-09-09T08:00:01')).range_start, value);
  }
  assert.throws(() => R.workspaceScope(ref, scope('2026-09-09T08:00:00.1', '2026-09-09T08:00:00.100000')));
  for (const value of invalid.filter(value => ![invalid[12], invalid[13]].includes(value)))
    assert.throws(() => R.workspaceScope(ref, scope(value, '9999-12-31T23:59:59.999999')), value);
  const definitions = [
    {api: context.window.RunAdoptionAPI, action: 'scheduling.candidate.adopt',
      overview: {candidate_ref: ref, run_ref: 'd'.repeat(48), baseline: {plan_ref: null, version: null}, task_count: 1, scope_complete: true},
      argument: ref},
    {api: context.window.TrialAdoptionAPI, action: 'trial.scenario.adopt',
      overview: {scenario_ref: ref, draft_ref: 'd'.repeat(48), baseline: {plan_ref: null, version: null}, task_count: 1, scope_complete: true}},
  ];
  definitions.forEach(({api, action, overview, argument}) => {
    const response = {ok: true, schema_version: 1, meta: meta(start), warnings: [], data: {...overview,
      validation: {status: 'valid', can_adopt: true, issues: []}, write_context: {
        write_token: 'e'.repeat(32), expires_at: end, capabilities: {[action]: true}, blocked_reasons: []}}};
    assert.equal(api.preview(response, argument || overview).write_context.expires_at, end);
    invalid.forEach(value => {
      const bad = clone(response); bad.meta.as_of = value;
      assert.throws(() => api.preview(bad, argument || overview), value);
      bad.meta.as_of = start; bad.data.write_context.expires_at = value;
      assert.throws(() => api.preview(bad, argument || overview), value);
    });
    const expired = clone(response); expired.data.write_context.expires_at = start;
    assert.throws(() => api.preview(expired, argument || overview));
  });
  return {canonical_valid: canonical.length, invalid_times: invalid.length, legacy_query_widths: 6, adoption_contracts: 2};
}

function candidate() {
  const valid = input.candidate, candidateRef = valid.data.candidate.candidate_ref;
  R.workspace(valid, candidateRef);
  // Alter a real DTO coherently to isolate a one-microsecond, non-point interval.
  const micro = clone(valid), task = micro.data.tasks[0], delivery = micro.data.delivery_risks.items[0];
  assert.equal(micro.data.tasks.length, 1); assert.equal(delivery.last_operations.length, 1);
  Object.assign(task, {start, end});
  Object.assign(delivery.last_operations[0], {start, end}); delivery.planned_finish = end;
  micro.data.task_span = {start, end}; micro.data.candidate_span = {start, end};
  assert.equal(context.window.PointContract.isPoint(task), false);
  R.workspace(micro, candidateRef);
  const changes = [
    value => { value.data.delivery_risks.items[0].planned_finish = start; },
    value => { value.data.task_span.start = end; },
    value => { value.data.task_span.end = start; },
    value => { value.data.candidate_span.start = end; },
    value => { value.data.candidate_span.end = start; },
    value => { value.data.tasks[0].end = start; },
    value => { value.data.tasks[0].start = '2026-09-09T08:00:00.123458'; },
  ];
  changes.forEach(change => {
    const bad = clone(micro); change(bad);
    assert.throws(() => R.workspace(bad, candidateRef));
  });
  const F = context.window.PreflightContract;
  F.result(input.preflight, input.settings);
  const observed = clone(input.preflight);
  observed.data.tasks[0].execution.first_actual_start = start;
  observed.data.tasks[0].execution.confirmed_finish = end;
  assert.equal(F.result(observed, input.settings).tasks[0].execution.first_actual_start, start);
  invalid.forEach(value => {
    for (const field of ['first_actual_start', 'confirmed_finish']) {
      const bad = clone(observed); bad.data.tasks[0].execution[field] = value;
      assert.throws(() => F.result(bad, input.settings), field + ': ' + value);
    }
  });
  return {candidate_mutations_rejected: changes.length, microsecond_interval_accepted: true, preflight_invalid_times: invalid.length};
}

async function trial() {
  T.workspace(input.draft); T.receipt(input.receipt, input.intent);
  let submitted;
  context.fetch = async (url, options) => {
    submitted = {url, ...JSON.parse(options.body)};
    return {ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => input.receipt};
  };
  const result = await context.window.TrialAPI.command(input.intent, 'write-token', 'trial-' + 'f'.repeat(48));
  assert.equal(submitted.url, '/api/workbench/v1/trial/drafts/' + input.intent.draft_ref + '/change');
  assert.deepEqual(submitted.input, input.intent.input);
  const rounded = clone(input.receipt);
  rounded.data.tasks[0].start = rounded.data.tasks[0].start.slice(0, 23) + '000';
  assert.throws(() => T.receipt(rounded, input.intent));
  return {request_start: submitted.input.start, receipt_start: result.data.tasks[0].start, response_rounding_rejected: true};
}
Promise.resolve(mode === 'scopes' ? scopes() : mode === 'candidate' ? candidate() : trial())
  .then(value => console.log(JSON.stringify(value))).catch(error => {console.error(error); process.exitCode = 1;});
