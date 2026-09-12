'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { compile } = require('../../scripts/workbench/compile.cjs');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(0, 'utf8')), output = path.resolve(input.output);
assert(!output.startsWith(root + path.sep), 'EK only builds in its private temporary directory');
fs.mkdirSync(output, { recursive: true });
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const files = [order.theme].concat(order.live.filter(name => !['PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx'].includes(name)));
files.splice(files.indexOf('PlanContract.js'), 0, 'PointContract.js');
files.splice(files.indexOf('PlanGanttModel.js'), 0, 'PointGanttModel.js', 'PointGantt.jsx');
const sources = files.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const urls = [];
for (const item of built.outputs) {
  const name = path.basename(item.path) + '.js'; fs.writeFileSync(path.join(output, name), item.code); urls.push('/assets/' + name);
}
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const shared = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-'));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
for (const item of manifest.files) {
  if (item.path.startsWith('workbench/app/')) continue;
  const bytes = fs.readFileSync(path.join(root, 'static', item.path));
  assert.equal(hash(bytes), item.sha256, 'Shared asset changed during isolated build');
  const target = path.join(output, item.path); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, bytes);
}
const navigation = JSON.parse(execFileSync(path.join(root, '.venv/bin/python'), ['-B', '-c',
  'import json; from web.routes.workbench.navigation_metadata import VIEW_TITLES, VIEW_ALIASES, navigation_groups; print(json.dumps(dict(titles=VIEW_TITLES, nav_groups=navigation_groups(), view_aliases=VIEW_ALIASES)))'], { cwd: root, env: process.env, encoding: 'utf8' }));
const supportedViews = ['dashboard', 'process', 'batches', 'run', 'analysis', 'gantt', 'delay', 'field', 'fieldgantt', 'review', 'reports', 'calib', 'basedata', 'system', 'trial'];
assert.deepEqual(Object.keys(navigation.titles).sort(), supportedViews.slice().sort(), 'Independent 15-view support contract');
const boot = { schema_version: 1, entry_url: '/', trial_url: '/trial', view: 'fieldgantt', enabled_views: supportedViews,
  ...navigation, help_url: '/scheduler/config/manual', instance_label: '独立点工序测试数据' };
const appStyles = order.styles.map(name => {
  const source = path.join(root, 'frontend/workbench/app/styles', name), bytes = fs.readFileSync(source), file = 'current-' + name;
  fs.writeFileSync(path.join(output, file), bytes);
  sources.push({ path: 'app/styles/' + name, code: bytes.toString('utf8') });
  return '<link rel="stylesheet" href="/assets/' + file + '">';
}).join('');
const styles = manifest.styles.filter(name => !name.startsWith('workbench/app/')).map(name => '<link rel="stylesheet" href="/assets/' + name + '">').join('') + appStyles;
const scripts = shared.map(name => '/assets/' + name).concat(urls).map(url => '<script src="' + url + '"></script>').join('');
fs.writeFileSync(path.join(output, 'index.html'), '<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + styles + '</head><body class="aps-workbench"><div id="root"></div><script id="workbench-boot" type="application/json">' + JSON.stringify(boot) + '</script>' + scripts + '</body></html>');
fs.writeFileSync(path.join(output, 'build-evidence.json'), JSON.stringify({ target: built.target, global_build: false, main_source: 'frontend/workbench/app/main.jsx',
  shared_build: manifest.build_id, sources: sources.map(row => ({ path: row.path, sha256: hash(row.code) })) }, null, 2));
console.log(output);
