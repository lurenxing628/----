'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const root = path.resolve(process.argv[2]), repo = path.resolve(__dirname, '../..');
assert(root !== repo && !root.startsWith(repo + path.sep), 'Only private output is allowed');
const output = path.join(root, 'final_planning_build'), statics = path.join(output, 'static');
const target = path.join(statics, 'workbench'), hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
let source = process.env.FINAL_PLANNING_BUILD;
if (!source) {
  source = target;
  execFileSync(process.env.WORKBENCH_PYTHON || path.join(repo, '.venv/bin/python'), ['-B', path.join(repo, 'scripts/workbench/build.py'),
    '--output-dir', target, '--node', process.execPath], { cwd: root, env: process.env, stdio: 'inherit' });
}
source = path.resolve(source);
const manifestBytes = fs.readFileSync(path.join(source, 'asset-manifest.json')), manifest = JSON.parse(manifestBytes);
assert.equal(manifest.target, 'chrome109');
const checked = [];
for (const item of manifest.inputs) {
  const name = path.resolve(repo, item.path); assert(name.startsWith(repo + path.sep));
  assert.equal(hash(fs.readFileSync(name)), item.sha256, 'Build input no longer matches: ' + item.path);
  checked.push(item);
}
for (const item of manifest.files) {
  assert(item.path.startsWith('workbench/') && !item.path.split('/').includes('..'));
  const name = item.path.slice('workbench/'.length), bytes = fs.readFileSync(path.join(source, name));
  assert.equal(hash(bytes), item.sha256, 'Artifact hash differs: ' + item.path);
  assert.equal(bytes.length, item.bytes);
  if (source !== target) { fs.mkdirSync(path.dirname(path.join(target, name)), { recursive: true }); fs.writeFileSync(path.join(target, name), bytes); }
}
fs.mkdirSync(target, { recursive: true });
if (source !== target) fs.writeFileSync(path.join(target, 'asset-manifest.json'), manifestBytes);
fs.cpSync(path.join(repo, 'templates/workbench'), path.join(output, 'templates/workbench'), { recursive: true });
const evidence = { root: output, static: statics, templates: path.join(output, 'templates'), build_id: manifest.build_id,
  target: manifest.target, global_build: false, main_source_used: true, main_script: manifest.scripts.at(-1),
  source_build: source, manifest_sha256: hash(manifestBytes), sources: checked,
  template_sha256: hash(fs.readFileSync(path.join(repo, 'templates/workbench/index.html'))),
  file_count: manifest.files.length, input_count: checked.length };
assert.equal(evidence.main_script, 'workbench/app/main.js');
fs.writeFileSync(path.join(root, 'piece_main_build.json'), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify({ build_id: manifest.build_id, files: manifest.files.length, inputs: checked.length, global_build: false }));
