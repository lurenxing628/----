'use strict';
// Inventory visible deletion actions in the current application sources, including dialogs.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const babel = require(path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'));
function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'tokens', 'comments'].includes(key)) continue;
    if (Array.isArray(value)) value.forEach(item => walk(item, visit));
    else if (value && typeof value === 'object') walk(value, visit);
  }
}
function text(node) {
  const values = [];
  walk(node, item => { if (['StringLiteral', 'JSXText'].includes(item.type)) values.push(item.value); });
  return values.join(' ');
}
const inventory = [], directory = path.join(root, 'frontend/workbench/app');
for (const file of fs.readdirSync(directory).filter(name => name.endsWith('.jsx'))) {
  const code = fs.readFileSync(path.join(directory, file), 'utf8');
  const ast = babel.transform(code, { ast: true, code: false, parserOpts: { plugins: ['jsx'] } }).ast;
  walk(ast, node => {
    if (node.type === 'ArrayExpression' && node.elements.some(item => item && item.type === 'StringLiteral' && /删除/.test(item.value))) {
      const values = node.elements.filter(item => item && item.type === 'StringLiteral').map(item => item.value);
      // Action descriptors are [handler, icon, visible label], rather than JSX literals.
      if (values.length === 3 && /^open/.test(values[0])) {
        assert.equal(values[1], 'trash-2', file + ':' + node.loc.start.line + ' deletion descriptor');
        inventory.push({ file, line: node.loc.start.line, kind: 'descriptor', label: values[2] });
      }
    }
    if (node.type !== 'JSXElement') return;
    const opening = node.openingElement, name = opening.name.name || opening.name.property && opening.name.property.name;
    if (!['Button', 'button', 'ControlButton'].includes(name)) return;
    const visible = text(node.children), label = visible + text(opening.attributes.filter(item => item.name && item.name.name === 'aria-label'));
    if (!/删除/.test(label) || /检查删除范围/.test(label)) return;
    const icon = opening.attributes.find(item => item.name && item.name.name === 'icon');
    const location = file + ':' + opening.loc.start.line;
    assert(icon && text(icon).split(/\s+/).includes('trash-2'), location + ' must use the shared trash icon');
    assert(/删除/.test(visible), location + ' must keep visible deletion text');
    inventory.push({ file, line: opening.loc.start.line, kind: 'button', label: visible.trim() });
  });
}
assert(inventory.length >= 17, 'Deletion inventory unexpectedly lost an application entry');
process.stdout.write(JSON.stringify({ scope: 'current-app-deletion-action-inventory', inventory }, null, 2) + '\n');
