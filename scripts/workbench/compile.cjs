'use strict';

const fs = require('node:fs');
const vm = require('node:vm');
const { componentOnly } = require('./ds-projection.cjs');

function selectDeclarations(source, names, babel, filename) {
  const ast = babel.transform(source, { filename, ast: true, code: false,
    sourceType: 'script', parserOpts: { plugins: ['jsx'] } }).ast;
  const requested = new Set(names);
  const selected = [];
  for (const node of ast.program.body) {
    const declared = node.type === 'FunctionDeclaration' ? [node.id.name] :
      node.type === 'VariableDeclaration' ? node.declarations.map(item => item.id.name) : [];
    if (!declared.some(name => requested.has(name))) continue;
    if (!declared.every(name => requested.has(name))) throw new Error('Mixed declaration: ' + filename);
    declared.forEach(name => requested.delete(name));
    selected.push(source.slice(node.start, node.end));
  }
  if (requested.size) throw new Error('Missing shared declarations: ' + [...requested].join(', '));
  return selected.join('\n\n');
}

function compile(request) {
  const babel = require(request.babel_path);
  if (babel.version !== '7.29.0') throw new Error('Unexpected Babel version: ' + babel.version);
  const outputs = request.sources.map(item => {
    let source = item.component_only ? componentOnly(item.code, babel) : item.code;
    if (item.declarations) source = selectDeclarations(source, item.declarations, babel, item.path);
    const moduleSource = item.source_type === 'module';
    const result = babel.transform(source, { filename: item.path, sourceType: moduleSource ? 'module' : 'script',
      presets: [['env', { targets: { chrome: '109' }, modules: moduleSource ? 'commonjs' : false, useBuiltIns: false }],
        ['react', { runtime: 'classic', development: false, useSpread: true }]],
      comments: true, compact: false, sourceMaps: false });
    new vm.Script(result.code, { filename: item.path });
    return { path: item.path, code: result.code };
  });
  if (request.check_combined) new vm.Script(outputs.map(item => item.code).join('\n;\n'));
  return { babel_version: babel.version, target: { chrome: '109' }, outputs };
}

if (require.main === module) {
  try {
    process.stdout.write(JSON.stringify(compile(JSON.parse(fs.readFileSync(0, 'utf8')))));
  } catch (error) {
    process.stderr.write('Workbench compile failed: ' + error.message + '\n');
    process.exitCode = 1;
  }
}

module.exports = { compile, selectDeclarations };
