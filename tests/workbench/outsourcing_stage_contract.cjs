'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const names = ['OutsourcingContract.js', 'OutsourcingSession.js', 'OutsourcingControls.jsx'];
const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })), check_combined: true }).outputs;
let state, result, nextState;
const window = { ResourceControls: {}, WorkbenchListControls: {}, APSResourceSession: { useQuery: () => ({ result, loading: false }) } };
const React = { Fragment: 'fragment', createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
  useState: initial => [state || (typeof initial === 'function' ? initial() : initial), value => { nextState = value; }] };
const context = vm.createContext({ window, React, console, Date, URLSearchParams });
outputs.forEach(output => vm.runInContext(output.code, context, { filename: output.path }));
const C = window.OutsourcingContract, S = window.OutsourcingSession;
const ref = c => c.repeat(48), row = { operation_ref: ref('a'), batch_ref: ref('b'), supplier_ref: ref('c'), piece: null,
  sequence: 10, business_code: 'B1_10', label: '热处理', can_register: true, issues: [], batch: null, supplier: null };
const clone = value => JSON.parse(JSON.stringify(value));
const equal = (actual, expected) => assert.deepEqual(clone(actual), expected);
assert.equal(C.query('targets', { query: '批次 P1' }).query, '批次 P1');
for (const bad of [null, {}, 1, 'x'.repeat(201), 'x\0']) assert.throws(() => C.query('targets', { query: bad }));
assert.throws(() => C.query('receipts', { query: 'P1' }));
assert.equal(S.memberConflict(row, { ...row, piece: 'A' }), '不同分件');
assert.equal(S.memberConflict(row, { ...row, batch_ref: ref('d') }), '不同批次');
assert.equal(S.memberConflict(row, { ...row, supplier_ref: ref('d') }), '不同供应商');
assert.equal(S.memberConflict(row, { ...row, sequence: 30, operation_ref: ref('d') }), '');
const draft = { kind: 'merged', sent: '2026-09-07T09:00:00', planned: '2026-09-09T12:00:00', returned: '',
  confirmedState: 'in_transit', declared_operator: '物流员', reason: '已核实' };
assert.throws(() => S.input(draft, [row, { ...row, operation_ref: ref('d'), piece: 'A' }], null), /同一分件/);

function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return tree && typeof tree === 'object' && 'type' in tree ? [tree, ...nodes(tree.props.children)] : [];
}
function render() { return nodes(window.OutsourcingControls.TargetPicker({ api: {}, mode: 'merged', selected: [row], onSelect() {}, onMode() {}, disabled: false })); }
state = { page: 2, size: 2, query: 'heat', snapshot_ref: 'old-read-token' };
result = { meta: { snapshot_ref: 'same-read-token' }, data: { items: [row, { ...row, piece: 'A', operation_ref: ref('d') }],
  page: { number: 2, size: 2, total: 6, pages: 3 } } };
let tree = render();
const checkboxes = tree.filter(node => node.type === 'input' && node.props.type === 'checkbox');
assert.equal(checkboxes[0].props.disabled, false); assert.equal(checkboxes[1].props.disabled, true);
tree.find(node => node.type === 'input' && node.props.type === 'search').props.onChange({ target: { value: 'B2' } });
equal(nextState, { page: 1, size: 2, query: 'B2' });
const pager = tree.find(node => node.type === window.OutsourcingControls.Pager);
pager.props.onSize(20); equal(nextState, { page: 1, size: 20, query: 'heat' });
pager.props.onPage(3); equal(nextState, { page: 3, size: 2, query: 'heat', snapshot_ref: 'same-read-token' });
console.log(JSON.stringify({ failed: 0, verified: ['query-contract', 'piece-selection', 'input-guard', 'search-clears-page-token', 'size-clears-page-token', 'paging-retains-snapshot'] }));
