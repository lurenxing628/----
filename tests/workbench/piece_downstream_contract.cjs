'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const window = { APSResourceContract: {}, PointContract: { isPoint: () => false } };
const context = vm.createContext({ window, Date, Number, Map, Set });
for (const file of ['resource-contract.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'ResourceMaterialContract.js', 'FieldContract.js', 'PlanGanttModel.js', 'ActualGanttModel.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app', file), 'utf8'), context);
const C = window.FieldContract, M = window.ActualGanttModel;
const filePreview = { ok: true, schema_version: 1, meta: { source: 'production', time_basis: 'factory_local', snapshot_ref: 'snapshot', as_of: '2026-10-01T10:00:00' }, warnings: [],
  data: { preview_ref: 'p'.repeat(32), actual_source_ref: 'a'.repeat(32), operation: 'material.import', format: 'csv', mode: 'upsert', template_version: 1,
    rows: [], summary: Object.fromEntries(['new', 'update', 'unchanged', 'delete', 'rejected'].map(key => [key, 0])), can_confirm: false, commit_policy: 'atomic',
    expires_at: '2026-10-01T10:15:00', write_context: { capabilities: { 'material.import': false }, write_token: 'w'.repeat(32) } } };
assert.strictEqual(window.APSResourceMaterial.preview(filePreview, 'import', 'csv'), filePreview);
assert.strictEqual(C.query(filePreview, 'preview'), filePreview);
for (const value of [undefined, ['a'.repeat(32)], 'bad-source']) {
  const changed = { ...filePreview, data: { ...filePreview.data, actual_source_ref: value, file_sha256: 'b'.repeat(64) } };
  assert.throws(() => window.APSResourceMaterial.preview(changed, 'import', 'csv'));
  assert.throws(() => C.query(changed, 'preview'));
}
assert.strictEqual(M.instant, window.PlanGanttModel.instant, 'Actual and planned marks share the factory-local coordinate parser');
const base = { piece_id: 'item-A', quantity: 1, batch_quantity: 3, quantity_basis: 'run_admission', quantity_reason: null };
assert(C.planQuantity(base));
for (const patch of [{ piece_id: undefined }, { quantity: undefined }, { quantity: true }, { quantity: -1 }, { quantity: 1.5 }, { quantity_basis: 'guessed' }, { quantity_reason: 'guessed' }]) assert(!C.planQuantity({ ...base, ...patch }));
const old = { ...base, quantity: null, batch_quantity: null, quantity_basis: 'unknown', quantity_reason: 'plan_target_not_recorded' };
assert(C.planQuantity(old)); assert.equal(C.quantity(old.quantity), '未知');
assert(!C.planQuantity({ ...old, quantity: 3 }));
for (const quantity of [0, 9007199254740991, '9007199254740992', '9223372036854775807']) {
  assert(C.planQuantity({ ...base, quantity, batch_quantity: quantity }));
  assert.equal(C.quantity(quantity), typeof quantity === 'string' ? window.WorkbenchFormat.integerText(quantity) : window.WorkbenchFormat.number(quantity, { digits: 0 }));
}
for (const quantity of [9007199254740992, '42', '0', '09007199254740992', '9223372036854775808', '9007199254740992\n', '1.5', '-1']) assert(!C.planQuantity({ ...base, quantity }));
for (const piece of ['item-A', 'item-B', 'item-C', '分件原始中文身份']) {
  const task = { ...base, piece_id: piece, task_ref: piece, batch_id: 'B1', sequence: 20, process_label: 'Turning', start: '2026-09-09T08:00:00', end: '2026-09-09T09:00:00' };
  const item = { task, execution: null };
  assert(M.taskLabel(task).includes(piece)); assert(M.searchText(item, new Map()).includes(piece.toLowerCase()));
  const text = M.describe(item, new Map()).join('\n'); assert(text.includes(piece)); assert(text.includes('计划应做：1.00 件 · 批次：3.00 件'));
  const unknown = M.describe({ task: { ...task, ...old }, execution: null }, new Map()).join('\n');
  assert(unknown.includes('计划应做：未知 件')); assert(unknown.includes('原计划未记录应做数量'));
  const large = M.describe({ task: { ...task, quantity: '9007199254740993', batch_quantity: '9223372036854775807' }, execution: null }, new Map()).join('\n');
  assert(large.includes('计划应做：9,007,199,254,740,993 件 · 批次：9,223,372,036,854,775,807 件'));
}
// 整道完工偏差直接消费共同执行投影；逐次报工结束和剩余安排不冒充完成。
const deviation = { state: 'available', as_of: '2026-09-09T10:00:00', finish_deviation_minutes: 20,
  elapsed_since_planned_minutes: null, forecast_deviation_minutes: null, due: true, complete: true,
  unclosed: false, late_open: false, finish_late: true, forecast_late: false };
const complete = { task: { ...base, task_ref: 'completed', batch_id: 'B1', sequence: 20, process_label: '车削', start: '2026-09-09T08:00:00', end: '2026-09-09T09:00:00' },
  deviation,
  execution: { execution_state: 'complete', confirmed_finish: '2026-09-09T09:20:00', known_completed_quantity: 1, remaining_quantity: 0, completion_basis: 'complete_reports', data_gaps: [] } };
const early = { ...complete, deviation: { ...deviation, finish_deviation_minutes: -1.5, finish_late: false }, execution: { ...complete.execution, confirmed_finish: '2026-09-09T08:58:30' } };
const unknown = { ...complete, deviation: { ...deviation, state: 'partial', finish_deviation_minutes: null, finish_late: false }, execution: { ...complete.execution, confirmed_finish: null } };
const partial = { ...complete, deviation: { ...deviation, finish_deviation_minutes: null, elapsed_since_planned_minutes: 60, forecast_deviation_minutes: 40,
  complete: false, unclosed: true, late_open: true, finish_late: false, forecast_late: true }, execution: { ...complete.execution, execution_state: 'partial', confirmed_finish: null,
  reports: [{ actual_end: '2026-09-09T09:30:00' }], remaining_plan: { end: '2026-09-09T09:40:00' } } };
assert.equal(M.finishDeviation(complete), '延后 20 分钟'); assert.equal(M.finishDeviation(early), '提前 1.5 分钟');
assert.equal(M.finishDeviation({ ...complete, deviation: { ...deviation, finish_deviation_minutes: 0, finish_late: false }, execution: { ...complete.execution, confirmed_finish: complete.task.end } }), '按计划完成');
assert.equal(M.finishDeviation(unknown), '缺少确认完工时间，请核对现场完工记录'); assert.equal(M.finishDeviation(partial), null);
assert(M.describe(complete, new Map()).includes('整道完工偏差：延后 20 分钟'));
assert.deepEqual(JSON.parse(JSON.stringify(M.deadlines(partial))), { finishLate: false, unclosed: true, forecastLate: true });
assert.equal(M.metrics({ execution_summary: { scope: 'full_response_cohort', complete: 3, pending: 0, reported: 1, average_finish_deviation_minutes: 9.25, known_finish_count: 2 }, items: [complete, early, unknown, partial] }).average, 9.25);
const boundary = { ...complete, deviation: { ...deviation, finish_deviation_minutes: 10, finish_late: false },
  execution: { ...complete.execution, confirmed_finish: '2026-09-09T09:10:00.060000' } };
assert.equal(M.finishDeviation(boundary), '延后 10 分钟');
assert.equal(M.deadlines(boundary).finishLate, false, 'The shared rounded deviation controls the 10 minute boundary');
const report = { report_ref: 'actual-on-other-resource', actual_start: '2026-09-09T08:10:00', actual_end: '2026-09-09T09:20:00' };
const located = M.graphLocations({ rows: [
  { kind: 'actual', top: 0, height: 88, item: complete, baseline: true, reports: [] },
  { kind: 'actual', top: 300, height: 88, item: complete, baseline: false, reports: [report] }
] }).get(complete.task.task_ref);
assert.equal(located.start, M.instant(report.actual_start)); assert.equal(located.end, M.instant(report.actual_end));
assert.equal(located.y, 333); assert.equal(located.reported, true);
const equalEnd = { ...report, report_ref: 'same-end-second', actual_start: '2026-09-09T08:15:00' };
const sameEndLocation = M.graphLocations({ rows: [
  { kind: 'actual', top: 300, height: 88, item: complete, baseline: false, reports: [report, equalEnd] },
  { kind: 'actual', top: 500, height: 88, item: complete, baseline: false, reports: [equalEnd] },
  { kind: 'actual', top: 600, height: 88, item: complete, baseline: true, reports: [] }
] }).get(complete.task.task_ref);
assert.equal(sameEndLocation.start, M.instant(report.actual_start)); assert.equal(sameEndLocation.y, 333);
assert.equal(sameEndLocation.reported, true, 'Equal latest ends keep the first report and prior row; an unreported baseline cannot replace it');
const fallback = M.graphLocations({ rows: [{ kind: 'actual', top: 0, height: 88, item: complete, baseline: true, reports: [] }] }).get(complete.task.task_ref);
assert.equal(fallback.start, M.instant(complete.task.start)); assert.equal(fallback.reported, false);
const shortReport = { ...report, actual_start: '2026-10-12T08:00:00.000001', actual_end: '2026-10-12T08:00:00.000002' };
const shortMark = M.marks({ kind: 'actual', item: complete, baseline: false, reports: [shortReport] })[0];
assert.equal(shortMark.kind, 'actual'); assert(shortMark.end > shortMark.start, 'A positive microsecond report is not collapsed to a point');
console.log('FB field contract, original identity, null/zero and actual descriptions passed');
