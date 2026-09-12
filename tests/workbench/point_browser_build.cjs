'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), input = JSON.parse(fs.readFileSync(0, 'utf8')), output = path.resolve(input.output);
assert(!output.startsWith(root + path.sep), 'Never publish shared assets');
fs.mkdirSync(output, {recursive: true});
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchGuards.js',
  'resource-contract.js', 'CalendarContract.js', 'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'resource-session.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx',
  'PointGanttModel.js', 'PointGantt.jsx', 'PlanGanttModel.js', 'PlanLayout.jsx', 'PlanGanttCanvas.jsx', 'PlanGantt.jsx', 'PlanDetailsUI.jsx',
  'RunCandidateAPI.js', 'RunCandidateModel.js', 'RunCandidateControls.jsx', 'RunBaselineAPI.js', 'RunBaselineModel.js', 'RunBaselineControls.jsx', 'RunCandidateGantt.jsx',
  'TrialContract.js', 'TrialAPI.js', 'TrialExport.js', 'TrialControls.jsx', 'TrialViewState.js', 'TrialGantt.jsx', 'TrialDetails.jsx', 'TrialStyles.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js',
  'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchNumberControls.jsx'];
const sources = files.map(name => ({path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')}));
sources.push({path: 'point_browser_host.jsx', code: fs.readFileSync(path.join(__dirname, 'point_browser_host.jsx'), 'utf8')});
const built = compile({babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true});
const urls = [];
for (const item of built.outputs) {
  const name = path.basename(item.path) + '.js'; fs.writeFileSync(path.join(output, name), item.code); urls.push('/assets/' + name);
}
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const shared = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-'));
const applicationScripts = new Set([...manifest.scripts, manifest.theme_script].filter(name => name.startsWith('workbench/app/')));
for (const item of manifest.files) {
  if (applicationScripts.has(item.path)) continue;
  const bytes = fs.readFileSync(path.join(root, 'static', item.path));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), item.sha256, 'Shared asset hash drift');
  const target = path.join(output, item.path); fs.mkdirSync(path.dirname(target), {recursive: true}); fs.writeFileSync(target, bytes);
}
const styleEvidence = manifest.styles.map(name => {
  const original = manifest.files.find(item => item.path === name);
  assert(original, 'Style must exist in the shared asset manifest: ' + name);
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(output, name))).digest('hex'), original.sha256, 'Private point build retains the exact shared stylesheet');
  return {path: name, sha256: original.sha256};
});
const styles = styleEvidence.map(item => '<link rel="stylesheet" href="/assets/' + item.path + '">').join('');
const scripts = shared.map(name => '/assets/' + name).concat(urls).map(url => '<script src="' + url + '"></script>').join('');
fs.writeFileSync(path.join(output, 'index.html'), '<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + styles + '</head><body class="aps-workbench"><div id="point-root"></div>' + scripts + '</body></html>');
fs.writeFileSync(path.join(output, 'build-evidence.json'), JSON.stringify({target: built.target, global_build: false, shared_build: manifest.build_id, styles: styleEvidence,
  sources: sources.map(row => ({path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex')}))}, null, 2));
console.log(output);
