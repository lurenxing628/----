'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), base = path.join(root, 'frontend/workbench/app');
const React = { createElement: (type, props, ...children) => ({ type, props: props || {}, children }), Fragment: 'fragment' };
const context = { React, window: { React, ResourceControls: {}, ReportControls: {}, WorkbenchFormat: {
  number: (value) => value == null ? '未知' : String(value), dateTime: value => value == null ? '未知' : value.replace('T', ' ')
} } };
vm.createContext(context);
const files = ['ReportEvidence.jsx', 'ReportTable.jsx', 'ReportControls.jsx', 'CalibrationControls.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: files.map(file => ({ path: file, code: fs.readFileSync(path.join(base, file), 'utf8') })), check_combined: true });
for (const output of built.outputs) vm.runInContext(output.code, context);
const E = context.window.ReportEvidence, T = context.window.ReportTable;
context.window.WorkbenchReference = function WorkbenchReference() {};
assert.equal(E.noFeedback({ records: 0 }), true);
for (const summary of [{ records: 1 }, { records: null }, {}, null]) assert.equal(E.noFeedback(summary), false);
assert.equal(T.text(0), '0'); assert.equal(T.text(null), '未知');
const missing = E.actualValue(null, true);
assert.equal(missing.props['aria-label'], '暂无现场数据');
assert.equal(missing.children.join(''), '—');
assert.equal(E.actualValue(0, true), '0'); assert.equal(E.actualValue(null, false), '未知');
const tree = E.StructuredFacts({ value: { completed_quantity: 0, actual_start: null, raw_values: { remark: '保留来源' }, operation_ref: 'a'.repeat(48) } });
const flat = JSON.stringify(tree);
assert(flat.includes('本次完成数量')); assert(flat.includes('保留来源')); assert(flat.includes('未知'));
assert(!flat.includes('[object Object]'));
const reference = 'A1'.repeat(16), arrayReference = 'c3'.repeat(16), businessCode = 'b2'.repeat(16), requestKey = 'request-retained-in-full';
const diagnostic = E.StructuredFacts({ value: { code: 'missing_hours', rule: 'quota.minimum_samples', rule_code: 'R17',
  request_key: requestKey, diagnostic_code: 0, completed_quantity: 0, raw_values: {
    fingerprint: reference, batch_code: businessCode, operation_code: businessCode, remark: reference,
    description: '说明 ' + reference, completed_quantity: 0, operation_refs: [reference, null, 0], untyped_values: [arrayReference, 0]
  } } });
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  return value && typeof value === 'object' ? [value, ...nodes(value.children)] : [];
}
function visibleText(value) {
  if (Array.isArray(value)) return value.map(visibleText).join('');
  if (value && typeof value === 'object') return value.type === context.window.WorkbenchReference ? '' : visibleText(value.children);
  return value == null ? '' : String(value);
}
const referenceNodes = nodes(diagnostic).filter(node => node.type === context.window.WorkbenchReference);
const retained = Object.assign({}, ...referenceNodes.map(node => node.props.entries));
assert.equal(retained['原因代码'], 'missing_hours'); assert.equal(retained['规则'], 'quota.minimum_samples');
assert.equal(retained['规则代码'], 'R17'); assert.equal(retained['请求编号'], requestKey);
assert.equal(retained['诊断代码'], 0); assert.equal(retained.fingerprint, reference);
assert.equal(JSON.stringify(retained.operation_refs), JSON.stringify([reference, null, 0]));
assert(referenceNodes.some(node => node.props.value === arrayReference), 'Hexadecimal references inside raw arrays must also be collected');
const visible = visibleText(diagnostic);
for (const value of ['missing_hours', 'quota.minimum_samples', 'R17', requestKey]) assert(!visible.includes(value));
assert(visible.includes(businessCode), 'Business codes must remain visible even when they look hexadecimal');
assert(visible.includes('备注' + reference), 'A business remark is not an internal reference');
assert(visible.includes('说明 ' + reference), 'Only a complete hexadecimal value is collected');
assert(visible.includes('本次完成数量0')); assert(!visible.includes('fingerprint'));
assert(!visible.includes(arrayReference));
const calls = [];
context.window.WorkbenchListControls = { Pager: () => null };
const reportPage = context.window.ReportControls.Page({ page: { number: 2, size: 10, pages: 4, total: 31 }, onChange: patch => calls.push(patch) });
assert.deepEqual(Array.from(reportPage.props.sizes), [10, 20, 50]);
reportPage.props.onSize(20); reportPage.props.onPage(3);
assert.equal(JSON.stringify(calls), '[{"page":1,"size":20},{"page":3}]');
const calibration = context.window.CalibrationControls.Page({ page: { number: 1, size: 37, total_pages: 2, total: 40 }, onChange() {} });
assert.deepEqual(Array.from(calibration.props.sizes), [10, 20, 37, 50]); assert.equal(calibration.props.pages, 2);
for (const file of ['ReportDetail.jsx', 'CalibrationDetail.jsx']) {
  const source = fs.readFileSync(path.join(base, file), 'utf8');
  assert(source.includes('WorkbenchDetailPanel'), file); assert(!source.includes('<pre'), file);
}
const workspace = fs.readFileSync(path.join(base, 'ReportWorkspace.jsx'), 'utf8');
assert(workspace.includes('role="tablist"')); assert(workspace.includes('onClick={() => target !== mode && go(target, true)}'));
assert(!workspace.includes('if (target === mode) return;'), 'Returning to a source in the same workspace must remain possible');
assert(workspace.includes('returnTo: { view: mode, context: currentContext() }'));
process.stdout.write('reports-review display contracts passed\n');
