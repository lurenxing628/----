'use strict';
// Compile and render the shared feedback component without opening any browser.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'frontend/workbench/app/ResourceForms.jsx'), 'utf8');
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: 'ResourceForms.jsx', code: source }] }).outputs[0].code;
const context = vm.createContext({ React: { Fragment: Symbol('Fragment'), createElement: (type, props, ...children) => ({ type, props: props || {}, children }) } });
context.window = context;
context.APSResourceContract = {};
context.ResourceControls = { Button: () => null, ErrorBox: () => null, Issues: () => null };
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/WorkbenchTerms.js'), 'utf8'), context);
vm.runInContext(compiled, context);
function text(value) {
  if (value === null || value === undefined || typeof value === 'boolean') return '';
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) return value.map(text).join('');
  if (typeof value.type === 'function') return text(value.type({ ...value.props, children: value.children }));
  return text(value.children);
}
const receipt = result => ({ ok: true, result, receipt_ref: 'fixture', data: {}, warnings: [] });
let checks = 0;
function feedback(kind, action, phase = 'done', result = 'committed', explicit) {
  checks++;
  return text(context.ResourceForms.Feedback({ command: { phase, intent: kind ? { kind, action } : undefined, result: receipt(result) }, action: explicit }));
}
for (const kind of ['material', 'op_type', 'machine', 'operator', 'supplier', 'machine_group', 'shift_profile', 'batch']) {
  assert.equal(feedback(kind, 'delete'), '删除已完成。');
  assert.equal(feedback(kind, 'update'), '保存已完成。');
}
for (const kind of ['material_bulk', 'op_type_bulk', 'machine_bulk', 'operator_bulk', 'supplier_bulk', 'process_bulk'])
  assert.equal(feedback(kind, 'confirm'), '删除已完成。');
assert.equal(feedback(null, null, 'done', 'committed', 'delete'), '删除已完成。');
assert.equal(feedback('batch', 'bulk_confirm', 'done', 'committed', 'delete'), '删除已完成。');
assert.equal(feedback('batch', 'bulk_confirm', 'done', 'committed', 'save'), '保存已完成。');
for (const [action, label] of [['delete', '删除'], ['update', '保存'], ['copy', '复制']]) {
  assert.equal(text(context.ResourceForms.Feedback({ command: { phase: 'done', intent: { kind: 'batch', action: 'bulk_confirm' },
    result: { ...receipt('committed'), data: { action } } } })), label + '已完成。'); checks++;
}
assert(feedback('batch', 'bulk_confirm', 'pending').startsWith('上次批次操作'));
assert.equal(feedback('operator', 'machine_permissions'), '设备关联保存已完成。');
assert.equal(feedback('operator', 'unlink'), '解除关联已完成。');
assert.equal(feedback('calendar', 'delete'), '清除日历配置已完成。');
assert.equal(feedback(null, null, 'done', 'committed', 'import'), '导入已完成。');
assert(feedback('material', 'delete', 'pending').startsWith('上次删除的结果还没查到'));
assert.equal(feedback('material', 'delete', 'checking'), '正在查询上次删除的结果…');
assert.equal(feedback('material', 'delete', 'sending'), '正在提交删除，请勿重复操作…');
assert(!feedback('material', 'delete', 'done', 'unchanged').includes('删除已完成'));
assert(feedback('material_bulk', 'confirm', 'done', 'partial').startsWith('部分删除已完成'));
assert.equal(context.ResourceForms.Feedback({ command: null }), null);
process.stdout.write(JSON.stringify({ checks, browser: false, database: false }));
