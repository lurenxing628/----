'use strict';

// The archived DS bundle also contains old workbench page bootstraps.
// Keep exact component statement slices, never evaluate the archived bundle.
function componentOnly(source, babel) {
  const firstLine = source.split('\n', 1)[0];
  const metadata = JSON.parse(firstLine.split('@ds-bundle: ')[1].split(' */')[0]);
  const paths = new Set(metadata.components.map(item => item.sourcePath));
  const names = new Set(metadata.components.map(item => item.name));
  const ast = babel.transform(source, { ast: true, code: false, sourceType: 'script' }).ast;
  const top = ast.program.body;
  if (top.length !== 1 || top[0].type !== 'ExpressionStatement' ||
      top[0].expression.type !== 'CallExpression' ||
      top[0].expression.callee.type !== 'ArrowFunctionExpression') {
    throw new Error('Unsupported archived DS wrapper; inspect before updating the projection');
  }
  const body = top[0].expression.callee.body;
  if (body.type !== 'BlockStatement') throw new Error('Expected DS block');
  const selected = [], foundPaths = new Set(), foundNames = new Set();
  for (const node of body.body) {
    let keep = false;
    if (node.type === 'TryStatement') {
      const statements = node.handler && node.handler.body.body;
      const call = statements && statements.length === 1 && statements[0].expression;
      const record = call && call.type === 'CallExpression' && call.arguments[0];
      const field = record && record.type === 'ObjectExpression' && record.properties.find(item => item.key.name === 'path');
      if (!field || field.value.type !== 'StringLiteral') throw new Error('Unknown DS source wrapper');
      const name = field.value.value;
      if (paths.has(name)) {
        if (foundPaths.has(name)) throw new Error('Duplicate DS component: ' + name);
        foundPaths.add(name); keep = true;
      } else if (!name.startsWith('ui_kits/workbench/')) {
        throw new Error('Unexpected DS embedded source: ' + name);
      }
    } else if (node.type === 'VariableDeclaration') {
      keep = node.declarations.every(item => ['__ds_ns', '__ds_scope'].includes(item.id.name));
    } else if (node.type === 'ExpressionStatement' && node.expression.type === 'AssignmentExpression') {
      const left = node.expression.left, right = node.expression.right;
      if (left.type === 'MemberExpression' && left.object.name === '__ds_ns') {
        const name = left.property.name;
        if (name === '__errors') keep = true;
        else if (names.has(name) && right.type === 'MemberExpression' &&
            right.object.name === '__ds_scope' && right.property.name === name) {
          if (foundNames.has(name)) throw new Error('Duplicate DS export: ' + name);
          foundNames.add(name); keep = true;
        }
      }
    }
    if (keep) selected.push(source.slice(node.start, node.end));
    else if (node.type !== 'TryStatement') throw new Error('Unknown DS top-level statement: ' + node.type);
  }
  if (foundPaths.size !== paths.size || foundNames.size !== names.size) {
    throw new Error('DS component/export coverage mismatch');
  }
  return '/* Component-only projection of the pinned DS bundle. */\n(() => {\n' + selected.join('\n\n') + '\n})();';
}

module.exports = { componentOnly };
