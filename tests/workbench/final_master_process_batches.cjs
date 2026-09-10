'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Module = require('node:module');
const ready = JSON.parse(fs.readFileSync(process.argv[2]));
const files = ['migrated_process_batch_probe.cjs', 'migrated_process_batch_support.cjs',
  'migrated_process_batch_visual.cjs', 'migrated_process_batch_unknown.cjs',
  'migrated_process_batch_recovery.cjs', 'migrated_process_batch_files.mjs', 'migrated_process_batch_oracle.py', 'final_master_process_recovery.cjs',
  'final_master_process_support.cjs', 'final_master_metadata_guard_support.py'];
const sources = files.map(name => ({path: 'tests/workbench/' + name,
  sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname, name))).digest('hex')}));
const filename = path.join(__dirname, files[0]), original = fs.readFileSync(filename, 'utf8');
const anchor = '  await page.goto(ready.resource_url); await page.locator(\'.hb-tile\').first().waitFor();';
assert.equal(original.split(anchor).length, 2, 'Expected one explicit fresh-entry setup in the original probe');
const replacement = '  p.step(\'goto\', \'about:blank\', \'Independent scenario; F5 restoration is tested by final_master_context_restore\');\n'
  + '  await page.goto(\'about:blank\');\n' + anchor;
const oldReceipt = 'd.getByText(/已取得原文件请求的完成回执/)';
const newReceipt = 'd.getByText(kind === \'hours\' ? \'已核实原文件回执；导入不代替工时阶段的人工确认。\' : \'已取得原文件请求的完成回执，工艺确认状态以重新读取的详情为准。\', {exact: true})';
assert.equal(original.split(oldReceipt).length, 2, 'Expected one original receipt label assertion');
const oldSupport = "require('./migrated_process_batch_support.cjs')", newSupport = "require('./final_master_process_support.cjs')";
assert.equal(original.split(oldSupport).length, 2);
const adapted = original.replace(anchor, replacement).replace(oldReceipt, newReceipt).replace(oldSupport, newSupport);
const generated = path.join(ready.root, 'final-master-process-batch-executed.cjs');
fs.writeFileSync(generated, adapted);
const recoveryFilename = path.join(__dirname, 'migrated_process_batch_recovery.cjs');
const recoveryAdapted = fs.readFileSync(path.join(__dirname, 'final_master_process_recovery.cjs'), 'utf8');
const recoveryGenerated = path.join(ready.root, 'final-master-process-batch-recovery-executed.cjs');
fs.writeFileSync(recoveryGenerated, recoveryAdapted);
fs.writeFileSync(path.join(ready.root, 'final-master-process-batch-probe-sources.json'), JSON.stringify({
  binding: 'New execution of the existing real input/click/SQLite oracle through the complete current workbench entry',
  build_id: ready.assets.build_id, sources, input_method: 'Explicit click/pressSequentially/select/download steps recorded by original Probe',
  harness_adaptations: [{before: anchor, after: replacement, reason: 'Same-URL goto now correctly restores history; independent business scenarios explicitly enter through about:blank'},
    {before: oldReceipt, after: newReceipt, files: [files[0]], reason: 'Exact current route/hours receipt labels from ProcessFileActions.jsx:117; original receipt/SQLite assertions unchanged'},
    {before: oldSupport, after: newSupport, reason: 'New tracking rows require separate append-only owner/pair/lineage validation; every other original assertion remains in OriginalProbe.validate'},
    {dependency: 'migrated_process_batch_recovery.cjs', replacement: 'final_master_process_recovery.cjs', reason: 'Deterministic real-server response loss and blocked original lookup, adds F5 recovery; avoids CDP 16-byte/s header-delivery timeout without synthetic responses'}],
  executed_source: {path: generated, sha256: crypto.createHash('sha256').update(adapted).digest('hex')},
  executed_recovery_source: {path: recoveryGenerated, sha256: crypto.createHash('sha256').update(recoveryAdapted).digest('hex')},
  limitation: 'The original replace case proves protected rejection only; unprotected replace success remains a separate pending atomic action'
}, null, 2) + '\n');
const executed = new Module(filename, module);
executed.filename = filename; executed.paths = module.paths;
const recovered = new Module(recoveryFilename, module);
recovered.filename = recoveryFilename; recovered.paths = module.paths;
recovered.exports = require('./final_master_process_recovery.cjs'); recovered.loaded = true;
Module._cache[recoveryFilename] = recovered;
executed._compile(adapted, filename);
