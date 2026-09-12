'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const babel = require(path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'));
const React = { createElement(type, props, ...children) {
  const values = { ...props, children: children.flat(Infinity) };
  return typeof type === 'function' ? type(values) : { type, props: values };
} };
const context = vm.createContext({ window: {}, React });
for (const name of ['WorkbenchTerms.js', 'WorkbenchReferences.jsx']) {
  const source = fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8');
  vm.runInContext(name.endsWith('.jsx') ? babel.transform(source, { presets: ['react'] }).code : source, context);
}
const T = context.window.WorkbenchTerms, Ref = context.window.WorkbenchReference, ErrorBox = context.window.WorkbenchError;
function text(tree, omitReferences = false) {
  if (tree === null || tree === undefined || tree === false) return '';
  if (typeof tree !== 'object') return String(tree);
  if (omitReferences && tree.type === 'details' && tree.props.className === 'wb-ref') return '';
  return tree.props.children.map(child => text(child, omitReferences)).join('\n');
}
assert.equal(T.overdue_count, '预计超期批次');
assert.equal(T.total_tardiness_hours, '总拖期');
assert.equal(T.candidate, '候选方案');
assert.equal(T.actions.save, '保存');
assert.deepEqual(JSON.parse(JSON.stringify(T)), {
  overdue_count: '预计超期批次', delay_hours: '超期时长', total_tardiness_hours: '总拖期', utilization: '利用率',
  candidate: '候选方案', official_plan: '正式计划', trial: '试调',
  actions: { add: '新增', save: '保存', confirm: '确认', cancel: '取消', clear: '清除', import: '导入', export: '导出', download: '下载' }
});
assert(Object.isFrozen(T));
assert(Object.isFrozen(T.actions));
assert.equal(Ref({}), null);
assert.equal(Ref({ entries: { '资源编号': null, '请求编号': '' } }), null);
const hash = '0123456789abcdef'.repeat(3);
const refs = Ref({ entries: { '运行编号': hash, '请求编号': 'request-123' } });
assert.equal(refs.type, 'details');
assert.equal(refs.props.className, 'wb-ref');
assert.equal(refs.props.open, undefined);
assert(text(refs).includes(hash));
assert.equal(text(refs, true), '');
assert(text(Ref({ value: 0 })).includes('0'));
assert(text(Ref({ value: '<script>bad()</script>' })).includes('<script>bad()</script>'));
assert.equal(Ref({ value: 'r1' }).props.dangerouslySetInnerHTML, undefined);
assert.equal(ErrorBox({ error: null }), null);
const original = Object.freeze({ message: '请先填写批次数量。', code: 'quantity.required', request_key: hash });
const business = ErrorBox({ error: original, fields: [{ path: 'quantity', message: original.message }] });
assert.equal(text(business, true).match(/请先填写批次数量。/g).length, 1);
assert(!text(business, true).includes(hash));
assert(!text(business, true).includes('quantity.required'));
assert(text(business).includes(hash));
assert(text(business).includes('quantity.required'));
for (const message of ['工艺表.xlsx 缺少工序列，请修正后重试。', 'route_template.xlsx 缺少工序列，请修正后重试。', '无法读取 aps.db，请检查文件是否仍在原位置。']) {
  const tree = ErrorBox({ error: { message, code: 'file.invalid' } });
  assert(text(tree, true).includes(message), 'Keep actionable file context');
  assert(!text(tree, true).includes('file.invalid'));
  assert(text(tree).includes('file.invalid'));
}
for (const message of ['HTTP 503: request_failed', 'TypeError: 无法读取', '{"message":"bad"}', '[1,2]', '{}', '引用 ' + hash + ' 已过期', 'request_failed', '资格检查 qualification.empty']) {
  const tree = ErrorBox({ error: { message }, fallback: '保存未完成，请重试。' });
  assert(text(tree, true).includes('保存未完成，请重试。'));
  assert(!text(tree, true).includes(message));
  assert(text(tree).includes(message));
}
const filtered = ErrorBox({ error: { message: '必填项未完成。' }, hideMessage: true, fields: [
  { path: 'quantity', message: '请填写数量。' }, { path: 'due_date', message: '请选择交期。' }, { path: 'due_date', message: '请选择交期。' }
], excludePaths: ['quantity'] });
assert(!text(filtered, true).includes('请填写数量。'));
assert(!text(filtered, true).includes('必填项未完成。'));
assert.equal(text(filtered, true).match(/请选择交期。/g).length, 1);
const diagnosticOnly = ErrorBox({ error: original, hideMessage: true });
assert.equal(text(diagnosticOnly, true).trim(), '');
assert(text(diagnosticOnly).includes(hash));
process.stdout.write('WorkbenchTerms and references contracts passed (isolated React element fixture).\n');
