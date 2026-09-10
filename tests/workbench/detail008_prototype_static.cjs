'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {sha, json} = require('./detail008_prototype_support.cjs');

const root = path.resolve(process.argv[2]);
const report = JSON.parse(fs.readFileSync(path.join(root, 'reachability.json')));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'source-before.json')));
const babelPath = 'ui_kits/workbench/assets/vendor/babel-7.29.0.min.js';
assert.equal(sha(fs.readFileSync(path.join(report.origin, babelPath))), manifest[babelPath].sha256);
const babel = require(path.join(report.origin, babelPath));
const result = {root, origin: report.origin, reachability_sha256: sha(fs.readFileSync(path.join(root, 'reachability.json'))),
  static_probe_sha256: sha(fs.readFileSync(__filename)),
  parser: {path: babelPath, sha256: manifest[babelPath].sha256}, files: [], calls: [], open_definitions: []};
const files = [...new Set(report.served.filter(row => row.status === 200).map(row => row.path))]
  .filter(file => /\.(js|jsx)$/.test(file));
for (const file of files) {
  const raw = fs.readFileSync(path.join(report.origin, file));
  assert.equal(sha(raw), manifest[file].sha256, 'Original source changed after browser proof: ' + file);
  const source = raw.toString();
  result.files.push({path: file, sha256: manifest[file].sha256, has_detail_namespace: source.includes('APSDetail')});
  if (!source.includes('APSDetail')) continue;
  const ast = babel.transform(source, {ast: true, code: false, parserOpts: {plugins: ['jsx']}}).ast;
  function visit(node, functions = []) {
    if (!node || typeof node !== 'object') return;
    const isFunction = /Function/.test(node.type || '');
    const stack = isFunction ? [...functions, node.id?.name || 'anonymous@' + node.loc.start.line] : functions;
    if (node.type === 'CallExpression' && node.callee.type === 'MemberExpression') {
      const callee = source.slice(node.callee.start, node.callee.end);
      if (/^(window\.APSDetail|D)\.open$/.test(callee)) result.calls.push({path: file, line: node.loc.start.line,
        function_stack: stack, code: source.slice(node.start, node.end)});
    }
    if (node.type === 'FunctionDeclaration' && node.id.name === 'open') {
      const code = source.slice(node.start, node.end), digest = sha(code);
      result.open_definitions.push({path: file, line: node.loc.start.line, sha256: digest,
        matches_runtime: digest === report.detail_open_function_sha256});
    }
    for (const [key, value] of Object.entries(node)) {
      if (['loc', 'tokens', 'comments'].includes(key)) continue;
      if (Array.isArray(value)) value.forEach(child => visit(child, stack));
      else if (value && typeof value === 'object') visit(value, stack);
    }
  }
  visit(ast);
}
assert.equal(result.open_definitions.filter(row => row.matches_runtime).length, 1);
assert.equal(result.open_definitions.find(row => row.matches_runtime).path, '_ds_bundle.js');
result.runtime_detail_source = result.open_definitions.find(row => row.matches_runtime);
result.prototype_source_unchanged_for_all_served_scripts = true;
result.production_verification = 'not_run';
json(path.join(root, 'static-call-evidence.json'), result);
console.log(JSON.stringify({root, parsed_namespace_files: result.files.filter(row => row.has_detail_namespace).length,
  calls: result.calls.length, runtime_source: result.runtime_detail_source,
  static_evidence_sha256: sha(fs.readFileSync(path.join(root, 'static-call-evidence.json')))}, null, 2));
