'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), context = vm.createContext({ window: {}, Date });
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/RunPresentation.js'), 'utf8'), context);
const P = context.window.RunPresentation;
assert.equal(P.step(null, null), 1);
assert.equal(P.step({ batch_refs: [] }, null), 1);
assert.equal(P.step({ batch_refs: ['batch'] }, null), 2);
assert.equal(P.step({ batch_refs: ['batch'] }, {}), 3);
assert.equal(P.step({ batch_refs: [] }, {}), 1);
assert.equal(P.stage({ stage: 'awaiting_reconciliation' }), '核对排产记录');
assert.equal(P.stage({ stage: 'unexpected' }), '排产阶段未知');
const run = { accepted_at: '2026-09-12T12:00:00', started_at: '2026-09-12T12:01:00', finished_at: '2026-09-12T13:02:03' };
assert.equal(P.elapsed(run), '1 小时 1 分钟 3 秒');
assert.equal(P.elapsed({ ...run, started_at: null }), '1 小时 2 分钟 3 秒');
assert.equal(P.elapsed({ ...run, finished_at: null }, new Date(2026, 8, 12, 12, 1, 35).getTime()), '35 秒');
assert.equal(P.elapsed({ ...run, finished_at: '2026-09-12T11:59:59' }), '未知');
assert.equal(P.elapsed({ ...run, accepted_at: 'bad', started_at: null }), '未知');
context.window.PlanGanttModel = {};
for (const name of ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'RunCandidateModel.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context);
}
assert.equal(context.window.RunCandidateModel.number('9007199254740993'), '9,007,199,254,740,993');
assert.equal(context.window.RunCandidateModel.percent('9007199254740993'), '900,719,925,474,099,300%');
// 不到三位小数的真实变化不能显示成“增加 0”。
assert.equal(context.window.RunCandidateModel.signedChange(1 / 3600), '增加不到 0.001');
assert.equal(context.window.RunCandidateModel.signedChange(-0.0003), '减少不到 0.001');
assert.equal(context.window.RunCandidateModel.signedChange(0.25), '增加 0.25');
assert.equal(context.window.RunCandidateModel.signedChange(0), '不变');
// 生成时的执行状态与现场记录同一套叫法；数据质量的 complete 是“完整”，不能和执行状态的“已完工”混成一个词。
for (const [state, label] of Object.entries(context.window.WorkbenchTerms.execution_states)) assert.equal(context.window.RunCandidateModel.executionValue(state), label);
assert.deepEqual(['unreported', 'paused', 'complete'].map(state => context.window.RunCandidateModel.executionValue(state, 'execution_state')), ['待报工', '已暂停', '已完工']);
assert.equal(context.window.RunCandidateModel.executionValue('complete', 'data_quality'), '完整');
assert.equal(context.window.RunCandidateModel.executionValue('invalid', 'data_quality'), '需复核');
assert.equal(context.window.RunCandidateModel.executionValue('piece', 'target_basis'), '件');
assert.equal(context.window.RunCandidateModel.executionValue(2.5, 'remaining_quantity'), '2.5');
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/RunJobAPI.js'), 'utf8'), context);
const A = context.window.RunJobAPI, memory = new Map([['unrelated-command', 'keep']]);
let serial = 0;
context.window.crypto = { getRandomValues: bytes => bytes.fill(++serial) };
const store = A.pending({ getItem: key => memory.has(key) ? memory.get(key) : null,
  setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key) });
const first = store.begin('a'.repeat(32), null, 'b'.repeat(64));
assert.equal(first.schema_version, 2);
assert.equal(first.data_context_ref, 'b'.repeat(64));
const attached = store.attach(first, 'c'.repeat(48));
store.finish(attached, 'found');
assert.equal(store.read(), null);
assert.equal(store.recent().intent.request_key, first.request_key);
assert.equal(memory.get('unrelated-command'), 'keep');
const second = store.begin('a'.repeat(32), null, 'd'.repeat(64));
assert.throws(() => store.finish(attached, 'found'));
assert.equal(store.read().request_key, second.request_key);
store.finish(second, 'context_replaced');
assert.equal(store.read(), null);
assert.equal(store.recent().resolution, 'context_replaced');
const legacy = { input_ref: 'a'.repeat(32), request_key: 'run-' + 'f'.repeat(48), run_ref: null };
memory.set(A.PENDING_KEY, JSON.stringify(legacy));
assert.equal(store.read().request_key, legacy.request_key);
store.finish(legacy, 'context_replaced');
assert.equal(memory.get('unrelated-command'), 'keep');
assert.equal(A.previewMessage({ code: 'storage_failure' }), '排产条件没有读出来，请重新检查。');
assert.equal(A.previewMessage({ code: 'no_eligible_tasks' }), '当前范围没有可排工序。请调整批次、齐套条件或补齐工序资料后重新检查。');
assert(!A.previewMessage({ code: 'unknown_preview_error' }).includes('不确定'));
// 已结束的排产失败是确定结果：不认识的原因照后端原话显示，不能说“可能已经生效”。
const calendarReason = '工作日历里有班次时间读不出来或者填得不对，这次排产没有开始。请到工作日历按 08:30 这样改好。';
assert.equal(A.failure({ code: 'invalid_calendar_shift', message: calendarReason }), calendarReason);
assert.equal(A.failure({ code: 'candidate_computation_failed', message: '' }), '本次候选计算失败。请联系维护人员，再重新做排产检查。');
assert.equal(A.failure({ code: 'resource_pool_unavailable', message: '' }), '本次候选计算失败。请联系维护人员，再重新做排产检查。');
assert(A.message({ code: 'invalid_calendar_shift', message: calendarReason }).includes('可能已经生效'));
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/RunHistoryAPI.js'), 'utf8'), context);
const H = context.window.RunHistoryAPI, ref48 = n => String(n).repeat(48);
const historyRun = (state, error) => ({ run_ref: ref48(1), state, stage: 'finished', accepted_at: '2026-09-10T12:00:00', started_at: '2026-09-10T12:01:00',
  finished_at: '2026-09-10T12:02:00', candidate_count: state === 'complete' ? 1 : 0, task_count: state === 'complete' ? 1 : 0,
  task_count_basis: 'persisted_rows_across_candidates', counts_final: true, recovery_required: false, recovery_reason: null, error,
  completion_semantics: 'execution_state_only', constraint_verification: 'not_checked_by_history', task_content_verification: 'candidate_workspace_required',
  scope_summary: { start_date: '2026-09-10', end_date: '2026-09-11', ready_check: true, missing_resource_policy: 'auto_assign', completed_policy: 'preserve_actuals',
    batch_count: 1, selection: 'explicit_batches', basis: 'captured_at_run_admission', data_gaps: [] } });
const historyPage = run => H.catalog({ ok: true, schema_version: 1, warnings: [],
  meta: { request_ref: 'e'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: 'f'.repeat(32), as_of: '2026-09-10T12:03:00' },
  data: { runs: [run], page: { number: 1, size: 20, total: 1, has_more: false }, run_count: 1, state: 'all', sort: 'accepted_at', order: 'desc',
    nulls: 'last', tie_breaker: 'run_ref_same_order', time_scope: { accepted_from: null, accepted_to: null, field: 'accepted_at', boundary: 'inclusive_dates', time_basis: 'factory_local' } } });
assert.equal(historyPage(historyRun('failed', { code: 'invalid_calendar_shift', message: calendarReason })).runs[0].error.message, calendarReason);
assert.equal(historyPage(historyRun('failed', null)).runs[0].error, null);
assert.throws(() => historyPage(historyRun('complete', { code: 'invalid_calendar_shift', message: calendarReason })));
assert.throws(() => historyPage(historyRun('failed', { code: 'invalid_calendar_shift', message: '' })));
assert.throws(() => { const value = historyRun('failed', null); delete value.error; historyPage(value); });
console.log('run UI step and elapsed contracts passed');
