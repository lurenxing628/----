'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = path.resolve(JSON.parse(fs.readFileSync(0, 'utf8')).output);
assert(!output.startsWith(root + path.sep) && output !== root);
fs.mkdirSync(output, { recursive: true });
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const sources = order.live.filter(name => name !== 'main.jsx').map(name => ({ path: 'app/' + name,
  code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
sources.push({ path: 'piece_presentation_host.jsx', code: fs.readFileSync(path.join(__dirname, 'piece_presentation_host.jsx'), 'utf8') });
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const urls = [], hash = value => crypto.createHash('sha256').update(value).digest('hex');
for (const item of built.outputs) {
  const name = path.basename(item.path) + '.js'; fs.writeFileSync(path.join(output, name), item.code); urls.push('/assets/' + name);
}
const raw = fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')), manifest = JSON.parse(raw);
const shared = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-'));
for (const item of manifest.files.filter(item => !item.path.startsWith('workbench/app/'))) {
  const bytes = fs.readFileSync(path.join(root, 'static', item.path)); assert.equal(hash(bytes), item.sha256);
  const target = path.join(output, item.path); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, bytes);
}
const styles = manifest.styles.map(name => '<link rel="stylesheet" href="/assets/' + name + '">').join('');
const scripts = shared.map(name => '/assets/' + name).concat(urls).map(url => '<script src="' + url + '"></script>').join('');
fs.writeFileSync(path.join(output, 'index.html'), '<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + styles + '</head><body class="aps-workbench"><div id="piece-root"></div>' + scripts + '</body></html>');
assert.deepEqual(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')), raw);
fs.writeFileSync(path.join(output, 'build-evidence.json'), JSON.stringify({ target: built.target, global_build: false, main_page: false,
  shared_manifest_sha256: hash(raw), sources: sources.map(row => ({ path: row.path, sha256: hash(row.code) })) }, null, 2));
