'use strict';
// Dialog focus restoration and the tooltip-reason Button, proven without a browser: the DOM is a hand-made tree and
// the focusable predicate is injected, so the rules stay checkable without a layout engine.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'frontend/workbench/app/ResourceControls.jsx'), 'utf8');
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: 'frontend/workbench/app/ResourceControls.jsx', code: source }], check_combined: false });
let checks = 0;
function check(name, run) { run(); checks++; }
function element(type, props, ...children) { return { type, props: { ...(props || {}), children: children.length === 1 ? children[0] : children } }; }
const React = { Fragment: Symbol('Fragment'), createElement: element, createContext: () => ({ Provider: Symbol('Provider') }), useId: () => ':r0:',
  Children: { map: (children, fn) => children == null ? children : (Array.isArray(children) ? children : [children]).map(fn) },
  cloneElement: (node, props) => ({ ...node, props: { ...node.props, ...props } }) };
function node(name, options = {}) {
  return { name, parentElement: options.parent || null, isConnected: options.connected !== false, tabindex: !!options.tabindex, focused: 0, focus() { this.focused++; } };
}
function host() {
  const body = node('body');
  const context = vm.createContext({ console, React, document: { body, activeElement: body } });
  context.window = context;
  vm.runInContext(compiled.outputs[0].code, context, { filename: 'ResourceControls.jsx' });
  // A launcher inside a table cell inside the workspace panel, which is the only container that can take focus.
  const panel = node('panel', { parent: body, tabindex: true }), cell = node('td', { parent: panel }), launcher = node('launcher', { parent: cell });
  return { body, panel, cell, launcher, document: context.document, R: context.ResourceControls };
}
function find(tree, predicate) {
  if (Array.isArray(tree)) return tree.map(item => find(item, predicate)).find(Boolean) || null;
  if (!tree || typeof tree !== 'object') return null;
  if (predicate(tree)) return tree;
  return find(tree.props && tree.props.children, predicate);
}
// Arrays come from the VM realm; rebuild them here so strict deep equality compares values, not prototypes.
const names = origin => Array.from(origin, item => item.name);
const focusable = item => item.isConnected && item.tabindex;
const click = (props, target) => { const event = { currentTarget: target, prevented: 0, preventDefault() { this.prevented++; } }; props.onClick(event); return event; };

check('origin lists the focused launcher and its containers, nearest first, stopping before body', () => {
  const h = host(); h.document.activeElement = h.launcher;
  assert.deepEqual(names(h.R.focusOrigin()), ['launcher', 'td', 'panel']);
});
check('a Button that was activated stands in once focus already dropped to body, and is consumed once', () => {
  const h = host(), calls = [];
  const button = find(h.R.Button({ children: '删除', onClick: () => calls.push('open') }), item => item.type === 'button');
  click(button.props, h.launcher); assert.deepEqual(calls, ['open']);
  h.document.activeElement = h.body;
  assert.deepEqual(names(h.R.focusOrigin()), ['launcher', 'td', 'panel']);
  assert.deepEqual(names(h.R.focusOrigin()), [], 'a later dialog must not inherit an older launcher');
});
check('without a focused element or an activated Button nothing is remembered', () => {
  const h = host(); assert.deepEqual(names(h.R.focusOrigin()), []);
});
check('a launcher React has replaced yields to its nearest still-mounted container instead of body', () => {
  const h = host(); h.launcher.isConnected = false;
  const entry = { origin: [h.launcher, h.cell, h.panel], parent: null };
  assert.equal(h.R.restoreCandidate([entry], false, focusable), h.panel);
  h.launcher.isConnected = true; h.launcher.tabindex = true;
  assert.equal(h.R.restoreCandidate([entry], false, focusable), h.launcher, 'a mounted launcher still wins');
});
check('inside a parent dialog only launchers count, never their containers', () => {
  const h = host(); h.launcher.isConnected = false;
  assert.equal(h.R.restoreCandidate([{ origin: [h.launcher, h.cell, h.panel], parent: null }], true, focusable), null);
});
check('the newest dialog is asked first, then each parent dialog', () => {
  const h = host(), outer = node('outer', { parent: h.body, tabindex: true }), inner = node('inner', { parent: h.body, tabindex: true, connected: false });
  const parent = { origin: [outer], parent: null }, child = { origin: [inner], parent };
  assert.equal(h.R.restoreCandidate([child, parent], false, focusable), outer);
  inner.isConnected = true; assert.equal(h.R.restoreCandidate([child, parent], false, focusable), inner);
});
check('a tooltip-only reason keeps the button focusable through aria-disabled and swallows activation', () => {
  const h = host(), calls = [];
  const tree = h.R.Button({ children: '删除', reason: '请先勾选记录。', reasonDisplay: 'tooltip', onClick: () => calls.push('never') });
  const button = find(tree, item => item.type === 'button');
  assert.equal(button.props['aria-disabled'], true); assert.ok(!button.props.disabled);
  assert.equal(button.props.title, '请先勾选记录。'); assert.equal(button.props['aria-label'], '删除：请先勾选记录。');
  assert.equal(button.props['data-wb-disabled-reason'], '请先勾选记录。');
  const event = click(button.props, h.launcher); assert.equal(event.prevented, 1); assert.deepEqual(calls, []);
  assert.equal(tree.props.className, 'wb-button-host'); assert.equal(tree.props.style, undefined); assert.equal(button.props.style, undefined);
  const busy = find(h.R.Button({ children: '删除', reason: '请先勾选记录。', reasonDisplay: 'tooltip', busy: true }), item => item.type === 'button');
  assert.equal(busy.props.disabled, true); assert.equal(busy.props['aria-disabled'], undefined);
  const forced = find(h.R.Button({ children: '删除', reason: '请先勾选记录。', reasonDisplay: 'tooltip', disabled: true }), item => item.type === 'button');
  assert.equal(forced.props.disabled, true); assert.equal(forced.props['aria-disabled'], undefined);
});
check('an inline reason still disables natively and renders the visible reason', () => {
  const h = host(), tree = h.R.Button({ children: '导出', reason: '请先选择记录。' }), button = find(tree, item => item.type === 'button');
  assert.equal(button.props.disabled, true); assert.equal(button.props['aria-disabled'], undefined);
  assert.equal(tree.props.className, 'wb-button-reason'); assert.ok(find(tree, item => item.type === 'span' && item.props.className === 'wb-reason'));
});
check('a bare button used as an empty-state action never submits an enclosing form', () => {
  const h = host();
  const bare = find(h.R.EmptyState({ kind: 'filtered', action: element('button', { onClick() {} }, '清除筛选') }), item => item.type === 'button');
  assert.equal(bare.props.type, 'button');
  const submit = find(h.R.EmptyState({ kind: 'filtered', action: element('button', { type: 'submit' }, '提交') }), item => item.type === 'button');
  assert.equal(submit.props.type, 'submit', 'an explicit type is the caller\'s decision');
  const shared = find(h.R.EmptyState({ kind: 'filtered', action: element(h.R.Button, { onClick() {} }, '清除筛选') }), item => item.type === h.R.Button);
  assert.equal(shared.props.type, undefined, 'the shared Button already defaults to type="button" itself');
});
process.stdout.write(JSON.stringify({ checks, passed: checks, browser: false, production: false }) + '\n');
