'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { compile } = require('../../scripts/workbench/compile.cjs');
const repo = path.resolve(__dirname, '../..'), root = path.resolve(process.argv[2]);
assert(!root.startsWith(repo + path.sep) && root !== repo, 'Only a private temporary build is allowed');
const output = path.join(root, 'piece_main_build'), statics = path.join(output, 'static');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const order = JSON.parse(fs.readFileSync(path.join(repo, 'scripts/workbench/build-order.json')));
const sources = [order.theme].concat(order.live).map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(repo, 'frontend/workbench/app', name), 'utf8') }));
assert.equal(sources.at(-1).path, 'app/main.jsx');
const built = compile({ babel_path: path.join(repo, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const manifestPath = path.join(repo, 'static/workbench/asset-manifest.json'), raw = fs.readFileSync(manifestPath), shared = JSON.parse(raw);
const files = [];
function emit(relative, bytes) {
  const target = path.join(statics, relative); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, bytes);
  files.push({ path: relative, sha256: hash(bytes), bytes: Buffer.byteLength(bytes) });
}
const replacing = new Set([...shared.scripts, shared.theme_script].filter(relative => relative.startsWith('workbench/app/')));
for (const item of shared.files.filter(item => !replacing.has(item.path))) {
  const bytes = fs.readFileSync(path.join(repo, 'static', item.path)); assert.equal(hash(bytes), item.sha256); emit(item.path, bytes);
}
const scripts = shared.scripts.filter(name => !replacing.has(name));
for (const item of built.outputs) {
  const relative = 'workbench/app/' + path.basename(item.path) + '.js'; emit(relative, item.code);
  if (item.path !== sources[0].path) scripts.push(relative);
}
assert.equal(new Set(scripts).size, scripts.length, 'Private build contains duplicate script entries');
assert.deepEqual(scripts.filter(relative => /\/main(?:\.jsx)?\.js$/.test(relative)), ['workbench/app/main.jsx.js'], 'Private build must load exactly one recompiled main');
assert([...replacing].every(relative => !scripts.includes(relative)), 'Shared application scripts must not execute alongside their recompiled replacements');
const manifest = { ...shared, files, scripts, theme_script: 'workbench/app/' + path.basename(built.outputs[0].path) + '.js', build_id: 'piece-main-' + hash(JSON.stringify(files)).slice(0, 20), inputs: [] };
const styles = shared.styles.map(relative => {
  const original = shared.files.find(item => item.path === relative); assert(original, 'Style is absent from shared asset manifest: ' + relative);
  assert.equal(hash(fs.readFileSync(path.join(statics, relative))), original.sha256, 'Shared style changed: ' + relative);
  return { path: relative, sha256: original.sha256 };
});
emit('workbench/asset-manifest.json', JSON.stringify(manifest, null, 2));
fs.cpSync(path.join(repo, 'templates/workbench'), path.join(output, 'templates/workbench'), { recursive: true });
assert.deepEqual(fs.readFileSync(manifestPath), raw, 'Global assets changed while copying shared runtime');
const evidence = { target: built.target, global_build: false, main_source_used: true, root: output, static: statics, templates: path.join(output, 'templates'), build_id: manifest.build_id,
  sources: sources.map(row => ({ path: 'frontend/workbench/' + row.path, sha256: hash(row.code) })), styles, shared_manifest_sha256: hash(raw) };
fs.writeFileSync(path.join(root, 'piece_main_build.json'), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify({ build_id: manifest.build_id, source_count: sources.length, main_source_used: true }));
