'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const window = {}, clone = value => JSON.parse(JSON.stringify(value));
const statusCode = compile({
  sources: [{ path: 'SystemRestoreStatus.js', code: fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/SystemRestoreStatus.js'), 'utf8') }],
  check_combined: false,
}).outputs[0].code;
const R = vm.runInNewContext(statusCode, { window }).default;
const current = { result_source: 'external_maintenance_journal', action: 'restore', state: 'succeeded', restart_required: true,
  database_origin: 'selected_backup', restart_scope: 'restoring_process', references_require_reload: true,
  source_verification: { basis: 'original_file_content_and_sqlite', target: 'verified', protection: 'captured', sqlite_integrity: 'passed' } };
assert.deepEqual(clone(R.sourceFacts(current)), [['所选备份内容', '与原文件内容一致'], ['保护副本内容', '已读取原文件内容'], ['SQLite 完整性', '完整性检查通过']]);
assert.equal(R.describe({ state: 'restart_required', request_key: 'req_1' }, { ...current, request_key: 'req_1', terminal: true }).uncertain, false);
assert.deepEqual(clone(R.host({
  ok: true, schema_version: 1,
  meta: { source: 'production', result_source: 'external_maintenance_journal' },
  data: { kind: 'restore_host', host: { state: 'ready', operations_available: true } }
})), { state: 'ready', operations_available: true });
assert.equal(R.referencePath('a'.repeat(32), 'job'), '/jobs/' + 'a'.repeat(32));
assert.throws(() => R.referencePath('bad', 'job'));
console.log('System original content and SQLite status contracts passed.');
