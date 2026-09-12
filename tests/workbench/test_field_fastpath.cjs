'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const context = vm.createContext({ window: {}, Date, Blob, URL });
for (const file of ['resource-contract.js', 'WorkbenchFormat.js', 'FieldContract.js', 'FieldDraftModel.js']) vm.runInContext(fs.readFileSync(path.join(app, file), 'utf8'), context, { filename: file });
const C = context.window.FieldContract, M = context.window.FieldDraftModel, plain = value => JSON.parse(JSON.stringify(value));
const ref = character => character.repeat(48), token = 'new-context';
const row = (overrides = {}) => ({ report_ref: ref('1'), revision_ref: ref('2'), operation_ref: ref('3'), recorded_against_task_ref: ref('4'),
  recorded_against_plan_ref: ref('5'), report_no: 'BG-001', completed_quantity: 0, actual_start: '2026-09-12T08:00:00', actual_end: '2026-09-12T09:00:30',
  effective_processing_hours: 0, actual_machine_ref: ref('6'), actual_operator_ref: ref('7'), remark: '上一条业务备注', correction_history: [],
  write_context: { write_token: 'old-report-context' }, request_key: 'must-not-copy', declared_operator: '不得复制的旧声明人', ...overrides });
const task = { task_ref: ref('4'), operation_ref: ref('3'), execution: { reports: [row()], execution_state: 'partial', write_context: { write_token: token, capabilities: { create: true } } } };
const now = new Date(2026, 8, 12, 10, 11, 12);
let checks = 0;
function check(name, run) { run(); checks++; process.stdout.write(name + ' passed\n'); }
check('new suggestions are visible metadata with factory-local values', () => {
  const value = M.initialize({ task, action: 'create', now });
  assert.equal(value.draft.actual_start, '2026-09-12T09:00:30'); assert.equal(value.draft.actual_end, '2026-09-12T10:11:12');
  assert.equal(value.suggestions.actual_start, '同任务上一条实际完工'); assert.equal(value.suggestions.actual_end, '本机当前时间');
});
check('no cross-task, cross-operation or malformed previous record', () => {
  for (const invalid of [{ recorded_against_task_ref: ref('8') }, { operation_ref: ref('9') }, { actual_end: null }, { actual_end: '2026-02-30T09:00:00' }, { actual_start: '2026-09-13T10:00:00' }]) {
    const next = { ...task, execution: { ...task.execution, reports: [row(invalid)] } };
    assert.equal(M.previous(next), null); assert.equal(M.initialize({ task: next, action: 'create', now }).draft.actual_start, '2026-09-12T10:11:12');
  }
});
check('retained, supplement, correct and legacy retain unknown facts', () => {
  const record = row({ actual_start: null, actual_end: null });
  for (const action of ['supplement', 'correct']) { const value = M.initialize({ task, record, action, now }); assert.equal(value.draft.actual_start, ''); assert.equal(value.draft.actual_end, ''); assert.deepEqual(plain(value.suggestions), {}); }
  const legacy = M.initialize({ task, action: 'create', legacy: { event_time: '2026-09-11 09:00:00', quantity_done: null }, now });
  assert.equal(legacy.draft.actual_start, ''); assert.equal(legacy.draft.actual_end, '2026-09-11T09:00:00'); assert.equal(legacy.draft.completed_quantity, ''); assert.deepEqual(plain(legacy.suggestions), {});
  const retained = { draft: C.draft(null), initialDraft: C.draft(null), suggestions: {} };
  assert.deepEqual(plain(M.initialize({ task, action: 'create', retained, now }).draft), plain(retained.draft));
});
check('copy uses editable allowlist and keeps the current declaration', () => {
  const value = M.copyPrevious({ ...C.draft(null), declared_operator: '当前声明人', task_ref: 'forbidden', request_key: 'forbidden' }, task);
  assert.equal(value.completed_quantity, '0'); assert.equal(value.effective_processing_hours, '0'); assert.equal(value.declared_operator, '当前声明人');
  for (const key of ['report_ref', 'revision_ref', 'task_ref', 'operation_ref', 'recorded_against_task_ref', 'write_context', 'request_key']) assert.equal(Object.hasOwn(value, key), false, key);
});
check('unknown and zero remain distinct in real ledger input', () => {
  const value = C.draft(null), input = C.input({ ...value, completed_quantity: '0', effective_processing_hours: '0', report_ref: 'forbidden' }, null, 'create');
  assert.equal(input.actual_start, null); assert.equal(input.actual_end, null); assert.equal(input.completed_quantity, 0); assert.equal(input.effective_processing_hours, 0);
  assert.equal(C.input(value, null, 'create').completed_quantity, null); assert.equal(Object.hasOwn(input, 'report_ref'), false); assert.equal(input.source, 'manual');
});
check('field errors reject malformed dates, impossible order and invalid amounts', () => {
  for (const [key, value] of [['completed_quantity', '1.5'], ['completed_quantity', '-1'], ['effective_processing_hours', 'Infinity'], ['actual_start', '2026-02-30T12:00'], ['actual_end', '2026-01-01T10:00Z']])
    assert.throws(() => C.input({ ...C.draft(null), [key]: value }, null, 'create'), error => error.committed === false && error.fields.some(field => field.path === key));
  assert.throws(() => C.input({ ...C.draft(null), actual_start: '2026-09-12T10:00', actual_end: '2026-09-12T09:00' }, null, 'create'), error => error.fields.some(field => field.path === 'actual_end'));
  assert.throws(() => C.input({ ...C.draft(null), actual_start: '2026-09-12T10:00', actual_end: '2026-09-12T11:00', effective_processing_hours: '2' }, null, 'create'), error => error.fields.some(field => field.path === 'effective_processing_hours'));
  assert.equal(C.input({ ...C.draft(null), actual_start: '2026-09-12T10:00:00', actual_end: '2026-09-12T10:00' }, null, 'create').actual_end, '2026-09-12T10:00:00');
});
check('supplement cannot rewrite facts and correction has explicit revision', () => {
  const original = row(), value = { ...C.draft(original), completed_quantity: '1', reason: '复核原始记录' };
  assert.throws(() => C.input(value, original, 'supplement'), error => error.fields.some(field => field.path === 'completed_quantity'));
  const corrected = C.input(value, original, 'correct'); assert.equal(corrected.original_revision_ref, original.revision_ref); assert.equal(corrected.completed_quantity, 1);
});
check('continuation requires same identity, new write token and remaining capability', () => {
  const identity = { taskRef: task.task_ref, operationRef: task.operation_ref };
  assert.equal(M.continuation({ write_token: 'old-context' }, task, identity), '');
  assert.notEqual(M.continuation({ write_token: token }, task, identity), '');
  assert.notEqual(M.continuation({ write_token: 'old-context' }, task, { ...identity, taskRef: ref('9') }), '');
  assert.notEqual(M.continuation({ write_token: 'old-context' }, { ...task, execution: { ...task.execution, execution_state: 'complete' } }, identity), '');
  assert.notEqual(M.continuation({ write_token: 'old-context' }, { ...task, execution: { ...task.execution, write_context: { write_token: token, capabilities: { create: false } } } }, identity), '');
});
const { compile } = require('../../scripts/workbench/compile.cjs');
const files = fs.readdirSync(app).filter(file => /^Field.*\.(js|jsx)$/.test(file));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: files.map(file => ({ path: file, code: fs.readFileSync(path.join(app, file), 'utf8') })), check_combined: true });
assert.equal(compiled.outputs.length, files.length);
process.stdout.write(JSON.stringify({ passed: true, checks, compiled: files, target: compiled.target }) + '\n');
