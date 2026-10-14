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
assert.deepEqual(clone(R.legacyDigests(current)), []);
const legacy = { ...current, source_verification: { basis: 'legacy_record', target: 'unavailable', protection: 'not_checked', sqlite_integrity: 'unavailable' },
  target_sha256: 'a'.repeat(64), protection_sha256: null };
assert.strictEqual(R.operation(legacy), legacy);
assert.deepEqual(clone(R.legacyDigests(legacy)), [['历史所选备份 SHA-256', legacy.target_sha256]]);
const legacyWithoutDigest = clone(legacy); delete legacyWithoutDigest.target_sha256; delete legacyWithoutDigest.protection_sha256;
assert.strictEqual(R.operation(legacyWithoutDigest), legacyWithoutDigest);
assert.deepEqual(clone(R.legacyDigests(legacyWithoutDigest)), []);
for (const patch of [value => { delete value.source_verification; }, value => { value.source_verification.target = 'verified-by-sha'; },
  value => { value.source_verification.sqlite_integrity = true; }, value => { value.target_sha256 = 'a'.repeat(64); }]) {
  const value = clone(current); patch(value); assert.throws(() => R.operation(value));
}
const brokenLegacy = clone(legacy); brokenLegacy.target_sha256 = 'wrong'; assert.throws(() => R.operation(brokenLegacy));
const saved = clone(legacy); R.operation(legacy); R.sourceFacts(legacy); R.legacyDigests(legacy); assert.deepEqual(legacy, saved);
console.log('System original content, SQLite status and optional legacy SHA contracts passed.');
