'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const window = {}, clone = value => JSON.parse(JSON.stringify(value));
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/SystemRestoreStatus.js'), 'utf8'), { window });
const R = window.SystemRestoreStatus;
const current = { result_source: 'external_maintenance_journal', action: 'restore', state: 'succeeded', restart_required: true,
  database_origin: 'selected_backup', restart_scope: 'restoring_process', references_require_reload: true,
  source_verification: { basis: 'original_file_content_and_sqlite', target: 'verified', protection: 'captured', sqlite_integrity: 'passed' } };
assert.strictEqual(R.operation(current), current);
assert.deepEqual(clone(R.sourceFacts(current)), [['所选备份内容', '与原文件内容一致'], ['保护副本内容', '已读取原文件内容'], ['SQLite 完整性', '完整性检查通过']]);
// The only verification basis is original file content plus SQLite; the removed legacy_record basis fails loudly.
for (const patch of [value => { delete value.source_verification; }, value => { value.source_verification.target = 'verified-by-sha'; },
  value => { value.source_verification.sqlite_integrity = true; },
  value => { value.source_verification = { basis: 'legacy_record', target: 'unavailable', protection: 'not_checked', sqlite_integrity: 'unavailable' }; }]) {
  const value = clone(current); patch(value); assert.throws(() => R.operation(value));
}
const saved = clone(current); R.operation(current); R.sourceFacts(current); assert.deepEqual(current, saved);
console.log('System original content and SQLite status contracts passed.');
