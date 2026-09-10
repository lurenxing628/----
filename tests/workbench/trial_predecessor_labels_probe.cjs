'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(0, 'utf8'));
const vendor = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor');
const context = vm.createContext({ console }); context.window = context; context.self = context;
vm.runInContext(fs.readFileSync(path.join(vendor, 'react-18.3.1.js'), 'utf8'), context);
const names = ['PointContract.js', 'ResourceControls.jsx', 'TrialControls.jsx', 'TrialGantt.jsx', 'TrialDetails.jsx'];
const sources = names.map(name => ({ path: 'frontend/workbench/app/' + name,
  code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(vendor, 'babel-7.29.0.min.js'), sources, check_combined: true });
for (const source of compiled.outputs) vm.runInContext(source.code, context, { filename: source.path });

function freeze(value) {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}
function nodes(value, predicate) {
  if (Array.isArray(value)) return value.flatMap(item => nodes(item, predicate));
  if (!value || typeof value !== 'object') return [];
  return (predicate(value) ? [value] : []).concat(nodes(value.props && value.props.children, predicate));
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value === null || value === undefined || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props && value.props.children) : String(value);
}

const before = JSON.stringify(input.data), data = freeze(input.data), navigation = [];
const Button = context.TrialControls.Button;
assert.equal(Button, context.ResourceControls.Button, 'Use the real shared Button');
function links(selected) {
  const tree = context.TrialDetails({ data, selected, commands: {}, onSelect: ref => navigation.push(ref),
    onEditing: () => {}, onRecheck: () => {} });
  return nodes(tree, node => node.type === Button && node.props.icon === 'chevron-left');
}
const original = data.tasks.find(row => row.task_ref === input.selected).predecessor_refs;
const rendered = links(input.selected), labels = rendered.map(text);
assert.deepEqual(labels, input.labels, 'Visible predecessor identities must be exact and complete');
assert.equal(rendered.length, original.length);
let wrapContracts = 0;
rendered.forEach((element, index) => {
  assert.equal(element.key, original[index], 'Keep original ref order and key');
  const wrapper = Button(element.props), buttons = nodes(wrapper, node => node.type === 'button');
  assert.equal(buttons.length, 1);
  const button = buttons[0], label = input.labels[index];
  assert.equal(button.props.title, label); assert.equal(button.props['aria-label'], label);
  assert.equal(wrapper.props.title, label); assert.equal(text(button), label);
  assert.equal(button.props.className, 'btn'); assert.equal(button.props.type, 'button');
  const icons = nodes(button, node => node.type === context.ResourceControls.Icon);
  assert.equal(icons.length, 1); assert.equal(icons[0].props.name, 'chevron-left');
  const style = button.props.style;
  assert.equal(style.minWidth, 0); assert.equal(style.maxWidth, '100%');
  assert.equal(style.height, 'auto'); assert.equal(style.whiteSpace, 'normal'); assert.equal(style.textAlign, 'left');
  const spans = nodes(button, node => node.type === 'span' && text(node) === label);
  assert.equal(spans.length, 1); assert.equal(spans[0].props.style.minWidth, 0);
  assert.equal(spans[0].props.style.overflowWrap, 'anywhere'); assert.equal(spans[0].props.style.wordBreak, 'break-word');
  wrapContracts++;
  button.props.onClick();
  assert.equal(navigation[index], original[index], 'Navigate by the original ref, never label or index');
  if (input.follow_labels) assert.deepEqual(links(navigation[index]).map(text), input.follow_labels[index]);
});
assert.deepEqual(navigation, original); assert.equal(JSON.stringify(data), before);
console.log(JSON.stringify({ labels, navigation, wrap_contracts: wrapContracts, real_button: true,
  source_unchanged: true, browser_geometry_verified: false, compile_target: compiled.target }));
