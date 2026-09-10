'use strict';
// Existing business assertions run against the actual private full-build server.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Module = require('node:module');
const ready = JSON.parse(fs.readFileSync(process.argv[2]));
const files = ['resource_live_probe.cjs', 'resource_aux_probe.cjs', 'resource_conflicts_probe.cjs',
  'custom_control_actions.cjs', 'resource_files_live_probe.cjs', 'resource_details_live_probe.cjs', 'resource_table_live_probe.cjs'];
const sources = files.map(name => ({path: 'tests/workbench/' + name,
  sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname, name))).digest('hex')}));
const filename = path.join(__dirname, files[0]), original = fs.readFileSync(filename, 'utf8');
const before = "await page.locator('.sidebar-nav').getByRole('link',{name:'基础资料',exact:true}).click();await page.getByRole('button',{name:'MAT-001',exact:true}).waitFor();";
const after = "await page.locator('.sidebar-nav').getByRole('link',{name:'基础资料',exact:true}).click();await page.getByRole('button',{name:'MAT-011',exact:true}).waitFor();equal(await page.getByRole('searchbox',{name:'搜索编号或名称'}).inputValue(),'MAT-011');";
assert.equal(original.split(before).length, 2, 'Expected one original sidebar-return assertion');
let adapted = original.replace(before, after);
const canceledBefore = "row.method==='GET'&&row.error==='net::ERR_ABORTED'";
const canceledAfter = "require('./final_master_probe_support.cjs').isCanceledRead(row.method,row.url,row.error)";
assert.equal(adapted.split(canceledBefore).length, 2);
adapted = adapted.replace(canceledBefore, canceledAfter);
const selectedScope = process.env.FINAL_MASTER_RESOURCE_SCOPE || 'all';
assert(['all', 'calendar'].includes(selectedScope), 'Unknown resource probe scope');
if (selectedScope === 'calendar') {
  const start = "    await run(page,state,'initial-and-pagination',async()=>{";
  const end = '    await resourceFiles(page,state,helpers,root,report);';
  assert.equal(adapted.split(start).length, 2); assert.equal(adapted.split(end).length, 2);
  const first = adapted.indexOf(start), last = adapted.indexOf(end) + end.length;
  assert(last > first);
  adapted = adapted.slice(0, first) + "    const helpers={run,close,type,rail,search,shot,layout,recordExpected:row=>report.expected_failures.push({state,...row})};\n"
    + "    report.selected_scope='calendar'; await auxiliary.calendar(page,state,helpers);\n" + adapted.slice(last);
}
const generated = path.join(ready.root, 'final-master-resource-executed.cjs');
fs.writeFileSync(generated, adapted);
const dependencyFilename = path.join(__dirname, 'resource_files_live_probe.cjs');
const dependencyOriginal = fs.readFileSync(dependencyFilename, 'utf8');
const pythonBefore = "const python=path.resolve(__dirname,'../../.venv/bin/python');";
const pythonAfter = "const python=process.env.FINAL_MASTER_PYTHON;assert(python,'Explicit host Python is required for sealed-source download verification');";
assert.equal(dependencyOriginal.split(pythonBefore).length, 2);
const dependencyAdapted = dependencyOriginal.replace(pythonBefore, pythonAfter);
const dependencyGenerated = path.join(ready.root, 'final-master-resource-files-executed.cjs');
fs.writeFileSync(dependencyGenerated, dependencyAdapted);
fs.writeFileSync(path.join(ready.root, 'final-master-resource-probe-sources.json'), JSON.stringify({
  binding: 'New execution of original business assertions, complete actual entry, no mocked success responses',
  build_id: ready.assets.build_id, sources,
  selected_scope: selectedScope,
  harness_adaptations: [{before, after, reason: 'SH003 now restores the actual MAT-011 filter on sidebar return; it must not reset to MAT-001'},
    {file: 'resource_files_live_probe.cjs', before: pythonBefore, after: pythonAfter,
      reason: 'A sealed source copy contains no virtualenv; use the explicitly supplied real interpreter, with no source fallback'},
    {before: canceledBefore, after: canceledAfter,
      reason: 'Use the independently tested exact ERR_ABORTED read-only query/facet predicate; preserve every raw failure and reject other errors or canceled writes'}],
  executed_source: {path: generated, sha256: crypto.createHash('sha256').update(adapted).digest('hex')},
  executed_dependency: {path: dependencyGenerated, sha256: crypto.createHash('sha256').update(dependencyAdapted).digest('hex')},
  input_method: 'Original probe type helper uses fill(empty) followed by pressSequentially; other fill calls remain fill, not sequential proof',
  limitation: 'Scenario success does not automatically mark every atomic action. Map only asserted actions after inspecting the actual report.'
}, null, 2) + '\n');
const executed = new Module(filename, module);
executed.filename = filename; executed.paths = module.paths;
const dependency = new Module(dependencyFilename, module);
dependency.filename = dependencyFilename; dependency.paths = module.paths;
Module._cache[dependencyFilename] = dependency;
dependency._compile(dependencyAdapted, dependencyFilename); dependency.loaded = true;
executed._compile(adapted, filename);
