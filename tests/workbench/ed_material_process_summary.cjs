'use strict';
// Summarize retained live evidence; never writes application data or repository assets.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const root = path.resolve(process.argv[2]), repo = path.resolve(__dirname, '../..');
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
assert.equal(read('isolation.json').root, root);
const report = read('ed-report.json'), ready = read('server-ready.json'), final = read('server-final.json');
const before = read('business-before.json'), after = read('business-after.json');
const metadata = new Set(['WorkbenchEntityRefs', 'WorkbenchCommandReceipts', 'WorkbenchProcessOperationConfirmations', 'WorkbenchProcessWorkflow']);
const materials = new Set(Object.values(ready.expected.ed.states).map(s => s.material));
const parts = new Set(Object.values(ready.expected.ed.states).map(s => s.part));
const changed = [];
for (const [table, old] of Object.entries(before)) {
  const current = after[table];
  if (JSON.stringify(old) === JSON.stringify(current)) continue;
  changed.push({table, old_rows: old.length, current_rows: current.length});
  if (metadata.has(table)) continue;
  assert.equal(current.length, old.length, 'No original business rows may be added or removed: ' + table);
  old.forEach((row, index) => {
    const fields = table === 'Materials' && materials.has(row.material_id) ? ['name', 'spec', 'stock_qty'] :
      table === 'PartOperations' && parts.has(row.part_no) && row.seq === 10 ? ['unit_hours'] :
      table === 'ExternalGroups' && parts.has(row.part_no) && row.start_seq === 20 ? ['total_days'] : [];
    const kept = Object.fromEntries(Object.entries(current[index]).filter(([key]) => !fields.includes(key)));
    assert.deepEqual(kept, Object.fromEntries(Object.entries(row).filter(([key]) => !fields.includes(key))), table + ':' + index);
  });
}
for (const old of before.WorkbenchCommandReceipts) assert.deepEqual(after.WorkbenchCommandReceipts.find(r => r.request_key === old.request_key), old);
const files = ['ResourceForms.jsx', 'ProcessStageEditor.jsx', 'ProcessSourceEditor.jsx', 'ProcessHoursEditor.jsx'].map(name => {
  const file = path.join(repo, 'frontend/workbench/app', name);
  return {path: file, sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')};
});
const dialogs = report.screenshots.filter(s => s.layout && s.layout.scope !== 'no-active-dialog');
const summary = {root, baseline_build_id: ready.assets.build_id, candidate_assets: ready.assets.ed_candidates || [], stable_files: files,
  browser: report.browser, summary: report.summary, preservation: {tables_checked: Object.keys(before).length,
    all_original_business_rows_retained: true, original_receipts_retained: true, changed_tables: changed},
  visual: {captured_states: report.screenshots.length, dialog_states: dialogs.length,
    clipping: dialogs.flatMap(s => s.layout.clipping).length, unexpected_overlap: dialogs.flatMap(s => s.layout.overlaps).length,
    text_contrast_failures: dialogs.flatMap(s => s.contrast.failures).length,
    minimum_text_contrast: Math.min(...dialogs.map(s => s.contrast.minimum)),
    checked_input_values: dialogs.flatMap(s => s.layout.controlContrast || []).length,
    minimum_input_contrast: Math.min(...dialogs.flatMap(s => s.layout.controlContrast || []).map(c => c.ratio)),
    input_contrast_failures: dialogs.flatMap(s => s.layout.controlContrast || []).filter(c => !c.passes).length,
    scoped_editable_date_inputs: dialogs.reduce((sum, s) => sum + s.layout.dateInputs, 0)},
  pageerrors: report.pageerrors, external_requests: report.external, recoveries: report.recoveries,
  material_return: report.material_return, filtered_paging: report.filtered_paging,
  isolation: {stopped: final.stopped, frozen_assets_unchanged: final.assets_unchanged, violations: final.isolation_violations,
    loaded_python_source_changes: final.python_sources.changed},
  acceptance: {complete: false, page_retention: report.material_return.every(r => Number(r.page_after_save) === r.original_page),
    pending: ['Formal host rebuild and frozen formal-asset rerun', 'Material list original page retention in shared ResourceWorkspace',
      'Material remark editing absent in resource-contract whitelist', 'Merged-group null member cycle incorrectly warned by backend projection',
      'Shared light breadcrumb/pager text contrast below 4.5']}};
fs.writeFileSync(path.join(root, 'ed-summary.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify({root, ...summary.summary, preservation: summary.preservation, visual: summary.visual,
  integration_files: files, acceptance: summary.acceptance}, null, 2));
