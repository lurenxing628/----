'use strict';
// No browser: the quantity shortcuts in the field editor only fill the draft; the save button is the only write path.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const output = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: ['FieldEditorFields.jsx', 'FieldEditor.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })), check_combined: true });
let slots = [], index = 0;
const state = initial => {
  const at = index++;
  if (!(at in slots)) slots[at] = typeof initial === 'function' ? initial() : initial;
  return [slots[at], value => { slots[at] = typeof value === 'function' ? value(slots[at]) : value; }];
};
const React = { Fragment: 'Fragment', createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), useState: state,
  useRef: value => state(() => ({ current: value }))[0], useEffect() {}, useLayoutEffect() {} };
const window = { APSResourceContract: { object: v => v !== null && typeof v === 'object' && !Array.isArray(v), failure: (message, fields) => Object.assign(new Error(message), { fields }) },
  PointContract: { arrangement: () => true, isPoint: () => false }, WorkbenchFormat: { number: v => String(v), dateTime: v => v, hours: v => String(v) + ' 小时' },
  FieldControls: { Button: 'Button', ErrorBox: 'ErrorBox', Feedback: 'Feedback' }, ResourceControls: { Field: 'Field', Choice: 'Choice', focusFirstInvalid() {} } };
const context = vm.createContext({ React, window, console, Date });
for (const name of ['WorkbenchTerms.js', 'FieldContract.js', 'FieldDraftModel.js']) vm.runInContext(fs.readFileSync(path.join(app, name), 'utf8'), context);
output.outputs.forEach(row => vm.runInContext(row.code, context));
function expand(node) {
  if (Array.isArray(node)) return node.map(expand);
  if (!node || typeof node !== 'object') return node;
  if (typeof node.type === 'function') return expand(node.type(node.props));
  return { ...node, props: { ...node.props, children: expand(node.props.children) } };
}
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props.children)];
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  return value && typeof value === 'object' ? text(value.props.children) : typeof value === 'string' ? value : '';
}
const ref = 'a'.repeat(48), execution = { operation_ref: ref, comparison_task_ref: null, execution_state: 'partial', data_quality: 'complete', target_quantity: 10,
  known_completed_quantity: 3, remaining_quantity: 7, records_complete: true, quantity_complete: true, unknown_record_count: 0, data_gaps: [], reports: [], legacy_facts: [],
  write_context: { write_token: 'token', capabilities: { create: true }, blocked_reasons: [] } };
const task = { task_ref: ref, plan_ref: ref, operation_ref: ref, batch_id: 'B1', operation_label: '车', piece_id: null, quantity: 10, batch_quantity: 10, quantity_basis: 'run_admission',
  quantity_reason: null, planned_start: '2026-09-01T08:00:00', planned_end: '2026-09-01T10:00:00', execution };
let submits = 0;
const command = { locked: false, phase: 'idle', error: null, result: null, submit: async () => { submits += 1; } };
const props = { task, record: null, legacy: null, action: 'create', adapter: {}, command, onDraft() {}, onClose() {}, onDone() {} };
function render() { index = 0; return expand(window.FieldEditor(props)); }
const button = (tree, label) => nodes(tree).find(node => node.type === 'Button' && text(node) === label);
let tree = render();
assert(!button(tree, '剩余全部完工'), '一键写入的按钮已去掉');
assert(!button(tree, '最大') && !button(tree, '最小'), '数量快捷键改成说明用途的名字');
const draft = tree => nodes(tree).find(node => node.type === 'input' && node.props['aria-label'] === '本次完成数量').props.value;
assert.equal(draft(tree), '');
button(tree, '填剩余数').props.onClick(); tree = render();
assert.equal(draft(tree), '7', '填剩余数只把剩余数量填进草稿');
assert.equal(submits, 0, '填剩余数不会写入报工');
button(tree, '填 0').props.onClick(); tree = render();
assert.equal(draft(tree), '0', '填 0 只把 0 填进草稿');
assert.equal(submits, 0, '填 0 不会写入报工');
button(tree, '填剩余数').props.onClick(); tree = render();
const save = nodes(tree).find(node => node.type === 'Button' && node.props.type === 'submit');
assert.equal(text(save), '保存报工', '写入只剩保存按钮这一条路');
// The form ref is a stub; give it the validity checks the save path asks for, then submit through the form.
slots.filter(slot => slot && typeof slot === 'object' && 'current' in slot).forEach(slot => { slot.current = { reportValidity: () => true, scrollIntoView() {}, focus() {} }; });
tree.props.onSubmit({ preventDefault() {} });
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(submits, 1, '保存报工才调用 command.submit');
  console.log('field editor quantity shortcuts fill only; save is the single write path');
})().catch(error => { console.error(error); process.exit(1); });
