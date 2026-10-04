'use strict';
// 不重排时段（hold_window）的前端合同：排产检查输入三态、检查结果一致性、排产任务 / 排产记录回显的可选项。
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const context = vm.createContext({ window: {}, Date, AbortController, URLSearchParams, setTimeout, clearTimeout });
for (const name of ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'PreflightContract.js', 'RunJobAPI.js', 'RunHistoryAPI.js'])
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context, { filename: name });
const { PreflightContract: C, RunJobAPI: J, RunHistoryAPI: H, WorkbenchTerms: T } = context.window;
const clone = value => JSON.parse(JSON.stringify(value));
const batch = 'b'.repeat(48), refs = ['1', '2', '3'].map(n => n.repeat(48));
const settings = { batch_refs: [batch], start_date: '2026-10-05', end_date: '2026-10-07', ready_check: true, material_strategy: 'strict',
  missing_resource_policy: 'auto_assign', completed_policy: 'preserve_actuals' };
const HOLD = /不重排时段要填完整的开始和结束时刻/;
const span = { start: '2026-10-05T08:00', end: '2026-10-06T00:00' };

// 真实后端返回的排产检查结果（不带 / null / 本次填写三种）要原样通过页面校验。
if (process.argv[2] === 'real') {
  const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')).map(({ settings: input, response }) => {
    const data = C.result(response, input), held = data.tasks.filter(row => row.held);
    return { source: data.effective_config.hold_window_source, hold_window: data.effective_config.hold_window,
      held_tasks: data.counts.held_tasks, hold_window_tasks: data.counts.hold_window_tasks, bases: held.map(row => row.held.basis) };
  });
  console.log(JSON.stringify({ cases }));
  return;
}

// 1. 输入三态：不带键 = 按交付设置；null = 不设；对象 = 本次单独填的时段。
assert.equal('hold_window' in C.input(settings), false);
assert.equal('hold_window' in C.input({ ...settings, hold_window: undefined }), false);
assert.equal(C.input({ ...settings, hold_window: null }).hold_window, null);
assert.deepEqual(clone(C.input({ ...settings, hold_window: { end: span.end, start: span.start } }).hold_window), span);
assert.deepEqual(Object.keys(C.input({ ...settings, hold_window: span })).slice(-1), ['hold_window']);
// 边界：最早开始日期 00:00，最晚结束日期次日 00:00（跨月也对）。
C.input({ ...settings, hold_window: { start: '2026-10-05T00:00', end: '2026-10-08T00:00' } });
C.input({ ...settings, end_date: '2026-10-31', hold_window: { start: '2026-10-31T23:00', end: '2026-11-01T00:00' } });
assert.deepEqual(clone(C.holdBounds('2026-12-30', '2026-12-31')), { min: '2026-12-30T00:00', max: '2027-01-01T00:00' });
assert.equal(C.holdBounds('2026-10-07', '2026-10-05'), null);
const bad = [{ start: '2026-10-04T23:59', end: span.end }, { start: span.start, end: '2026-10-08T00:01' }, { start: span.end, end: span.start },
  { start: span.start, end: span.start }, { start: span.start + ':00', end: span.end }, { start: span.start, end: '' }, { start: '', end: '' },
  { start: '2026-02-30T08:00', end: span.end }, { start: '2026-10-05T24:00', end: span.end }, { start: span.start }, { ...span, note: 'x' }, 'x', [], 0];
bad.forEach(value => assert.throws(() => C.input({ ...settings, hold_window: value }), HOLD, JSON.stringify(value)));
assert.throws(() => C.input({ ...settings, extra: 1 }), /请核对已选批次/);
// 返回排产页时的页面记忆可以带回这一项（含 null）。
assert.deepEqual(clone(C.initial({ ...settings, hold_window: span }).hold_window), span);
assert.equal(C.initial({ ...settings, hold_window: null }).hold_window, null);
assert.equal('hold_window' in C.initial(settings), false);

// 2. 检查结果：effective_config、tasks[].held、两个计数要对得上。
const execution = { execution_state: 'unreported', completion_basis: null, data_quality: 'complete', first_actual_start: null, confirmed_finish: null,
  remaining_quantity: null, known_completed_quantity: null, unknown_record_count: null };
function envelope(input, hold, source, helds) {
  const tasks = refs.map((ref, index) => ({ operation_ref: ref, batch_ref: batch, batch_id: 'B1', label: '车', sequence: String(10 * (index + 1)), status: 'eligible',
    has_execution_facts: false, issues: [], predecessor_refs: [], execution, held: helds[index] }));
  const held = tasks.filter(row => row.held), kept = held.filter(row => row.held.basis === 'hold_window').length;
  const counts = { ready_tasks: 3, auto_assign_required: 0, skipped_tasks: 0, blocked_tasks: 0, protected_tasks: 0, eligible_tasks: 3, selected_batches: 1,
    selected_tasks: 3, no_route_batches: 0, unready_batches: 0, missing_resource_tasks: 0, actual_fact_tasks: 0, held_tasks: held.length, hold_window_tasks: kept };
  return { data: { input_ref: 'T'.repeat(32), input_expires_at: '2026-10-05T10:00:00', counts, normalized_input: clone(input), tasks,
    blockers: [], warnings: [], run_blocked_reasons: [{ code: 'preflight_only', message: '这是排产检查。' }], calendar_check: 'not_evaluated',
    config_scope: 'single_run', run_blocked: true, write_context: { capabilities: { 'scheduling.run': false }, write_token: null },
    no_route_batches: [], unready_batches: [], included_batches: [{ batch_ref: batch, batch_id: 'B1' }], excluded_batches: [],
    scope: { source: 'production', batch_refs: [batch] }, effective_start: '2026-10-05T00:00:00', eligible_tasks: 3, auto_assign_required: 0, skipped_tasks: 0,
    effective_config: { ready_check: true, material_strategy: 'strict', missing_resource_policy: 'auto_assign', completed_policy: 'preserve_actuals',
      hold_window: hold, hold_window_source: source } } };
}
const kept = { basis: 'hold_window', start: '2026-10-05T08:00:00', end: '2026-10-05T10:30:00.500000' };
const locked = { basis: 'locked', start: '2026-10-06T08:00:00', end: '2026-10-06T08:00:00' };
const defaults = envelope(settings, { start: '2026-10-05T00:00', end: '2026-10-07T00:00' }, 'default', [kept, null, locked]);
assert.equal(C.result(defaults, settings).counts.hold_window_tasks, 1);
C.result(envelope(settings, null, 'default', [null, null, locked]), settings);
const explicit = { ...settings, hold_window: span };
C.result(envelope(explicit, { end: span.end, start: span.start }, 'explicit', [kept, kept, null]), explicit);
C.result(envelope({ ...settings, hold_window: null }, null, 'explicit', [null, null, locked]), { ...settings, hold_window: null });
const rejected = [
  ['显式填写却标成按交付设置', envelope(explicit, span, 'default', [kept, null, null]), explicit],
  ['生效时段与本次填的不同', envelope(explicit, { ...span, end: '2026-10-06T01:00' }, 'explicit', [kept, null, null]), explicit],
  ['填了时段却回 null', envelope(explicit, null, 'explicit', [null, null, null]), explicit],
  ['没带键却标成本次填写', envelope(settings, null, 'explicit', [null, null, null]), settings],
  ['来源缺失', envelope(settings, null, undefined, [null, null, null]), settings],
  ['按交付设置的时段格式不对', envelope(settings, { start: '2026-10-05T00:00:00', end: '2026-10-07T00:00:00' }, 'default', [null, null, null]), settings],
  ['没带键却回显了时段', envelope({ ...settings, hold_window: span }, span, 'default', [null, null, null]), settings],
];
rejected.forEach(([label, value, input]) => assert.throws(() => C.result(value, input), /不一致/, label));
const mutations = [
  ['保留计数不符', value => { value.data.counts.held_tasks += 1; }],
  ['不重排计数不符', value => { value.data.counts.hold_window_tasks = 0; }],
  ['未设时段却有不重排工序', value => { value.data.effective_config.hold_window = null; }],
  ['缺少 held', value => { delete value.data.tasks[1].held; }],
  ['依据未知', value => { value.data.tasks[0].held.basis = 'frozen'; }],
  ['原安排起止颠倒', value => { value.data.tasks[0].held.start = '2026-10-05T11:00:00'; }],
  ['原安排时刻格式不对', value => { value.data.tasks[0].held.end = '2026-10-05T10:30'; }],
  ['多余的项', value => { value.data.tasks[0].held.note = 'x'; }],
  ['缺少计数', value => { delete value.data.counts.hold_window_tasks; }],
];
mutations.forEach(([label, change]) => { const value = clone(defaults); change(value); assert.throws(() => C.result(value, settings), /不一致|不能继续/, label); });

// 3. 排产任务：normalized_input 的这一项可选；格式错误整页拒绝。
const meta = { request_ref: 'e'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: 'f'.repeat(32), as_of: '2026-10-05T09:00:00' };
const preview = input => ({ ok: true, schema_version: 1, warnings: [], meta, data: { input_ref: 'T'.repeat(32), normalized_input: input, calendar_check: 'not_evaluated',
  warnings: [], data_context_ref: 'c'.repeat(64), write_context: { write_token: null, expires_at: null, capabilities: { 'scheduling.run': false },
    blocked_reasons: [{ code: 'run_worker_not_connected', message: '暂不可用' }] } } });
for (const value of [undefined, null, span]) J.preview(preview(value === undefined ? settings : { ...settings, hold_window: value }), 'T'.repeat(32));
for (const value of [{ start: span.start }, { start: span.end, end: span.start }, { start: span.start + ':00', end: span.end + ':00' }, 'x'])
  assert.throws(() => J.preview(preview({ ...settings, hold_window: value }), 'T'.repeat(32)), JSON.stringify(value));

// 4. 排产记录：旧记录不带这一项；null 是不设；读不出来的记录为 null 并附一条资料缺项。
const run = summary => ({ run_ref: '1'.repeat(48), state: 'complete', stage: 'finished', accepted_at: '2026-10-05T12:00:00', started_at: '2026-10-05T12:01:00',
  finished_at: '2026-10-05T12:02:00', candidate_count: 1, task_count: 1, task_count_basis: 'persisted_rows_across_candidates', counts_final: true,
  recovery_required: false, recovery_reason: null, error: null, completion_semantics: 'execution_state_only', constraint_verification: 'not_checked_by_history',
  task_content_verification: 'candidate_workspace_required', scope_summary: { start_date: '2026-10-05', end_date: '2026-10-07', ready_check: true,
    missing_resource_policy: 'auto_assign', completed_policy: 'preserve_actuals', batch_count: 1, selection: 'explicit_batches',
    basis: 'captured_at_run_admission', data_gaps: [], ...summary } });
const page = summary => H.catalog({ ok: true, schema_version: 1, warnings: [], meta, data: { runs: [run(summary)], page: { number: 1, size: 20, total: 1, has_more: false },
  run_count: 1, state: 'all', sort: 'accepted_at', order: 'desc', nulls: 'last', tie_breaker: 'run_ref_same_order',
  time_scope: { accepted_from: null, accepted_to: null, field: 'accepted_at', boundary: 'inclusive_dates', time_basis: 'factory_local' } } });
const invalidGap = [{ field: 'hold_window', code: 'invalid_stored_value', message: '排产时未记录此项。' }];
assert.equal('hold_window' in page({}).runs[0].scope_summary, false);
assert.equal(page({ hold_window: null }).runs[0].scope_summary.hold_window, null);
assert.deepEqual(clone(page({ hold_window: span }).runs[0].scope_summary.hold_window), span);
page({ hold_window: null, data_gaps: invalidGap });
assert.throws(() => page({ hold_window: span, data_gaps: invalidGap }));
assert.throws(() => page({ data_gaps: invalidGap }));
assert.throws(() => page({ hold_window: { start: span.end, end: span.start } }));
assert.throws(() => page({ hold_window: { start: span.start + ':00', end: span.end } }));

// 5. 回显文案：三处共用同一套说法。
assert.equal(T.hold_window(undefined), '未记录（按当时的交付设置）');
assert.equal(T.hold_window(null), '不设');
assert.equal(T.hold_window(null, true), '记录无效');
assert.equal(T.hold_window(span), '2026-10-05 08:00 至 2026-10-06 00:00');
console.log(JSON.stringify({ invalid_inputs: bad.length, rejected_results: rejected.length + mutations.length }));
