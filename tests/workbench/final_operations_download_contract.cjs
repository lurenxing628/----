'use strict';
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('frontend/workbench/app/SystemMaintenanceAPI.js', 'utf8');
const row = { record_kind: 'backup_file', backup_ref: 'a'.repeat(48), filename: 'aps_backup_验收.db', size_bytes: 64 }, input = { snapshot_ref: 'b'.repeat(48) };
const bytes = Buffer.alloc(64); bytes.write('SQLite format 3\u0000');
let clicked = 0, fetched = 0, lastURL = '', variation = '';
const headers = () => ({ 'Content-Type': 'application/vnd.sqlite3', 'Content-Length': '64', 'X-APS-Backup-Ref': row.backup_ref,
  'Content-Disposition': "attachment; filename=aps-backup.db; filename*=UTF-8''" + encodeURIComponent(row.filename) });
const document = { body: { appendChild() {} }, createElement() { return { click() { clicked++; }, remove() {} }; } };
const host = { window: {}, Blob, AbortController, URLSearchParams, setTimeout: () => 1, clearTimeout() {}, document,
  URL: { createObjectURL() { return 'blob:private-test'; }, revokeObjectURL() {} } };
vm.runInNewContext(source, host);
async function fetcher(url) {
  fetched++;
  lastURL = url; let payload = bytes, meta = headers(), status = 200;
  if (variation === 'empty') payload = Buffer.alloc(0);
  if (variation === 'magic') payload = Buffer.alloc(64);
  if (variation === 'size') meta['Content-Length'] = '63';
  if (variation === 'mime') meta['Content-Type'] = 'text/html';
  if (variation === 'filename') meta['Content-Disposition'] = "attachment; filename*=UTF-8''aps_backup_wrong.db";
  if (variation === 'reference') meta['X-APS-Backup-Ref'] = 'c'.repeat(48);
  if (variation === 'bad-encoding') meta['Content-Disposition'] = "attachment; filename*=UTF-8''%GG";
  if (variation === 'json' || variation === 'disguised-json') {
    status = 409; payload = JSON.stringify({ ok: false, committed: false, error: { code: 'snapshot_stale', message: 'original range changed' } });
    if (variation === 'json') meta['Content-Type'] = 'application/json';
  }
  return { ok: status === 200, status, headers: { get(name) { return meta[name] || null; } }, async blob() { return new Blob([payload], { type: meta['Content-Type'] }); } };
}
(async () => {
  const api = host.window.SystemMaintenanceAPI.create(fetcher);
  const good = await api.downloadBackup(row, input);
  assert.deepEqual(JSON.parse(JSON.stringify(good)), { filename: row.filename, bytes: 64 }); assert.equal(clicked, 1);
  assert(lastURL.includes('/backups/' + row.backup_ref + '/download?snapshot_ref=')); assert(!lastURL.includes('验收'));
  const rejected = [];
  for (const name of ['empty', 'magic', 'size', 'mime', 'filename', 'reference', 'bad-encoding', 'json', 'disguised-json']) {
    variation = name; await assert.rejects(() => api.downloadBackup(row, input)); rejected.push(name); assert.equal(clicked, 1);
  }
  const beforeEvents = fetched;
  for (const record_kind of ['restore_event', 'cleanup_event']) await assert.rejects(() => api.downloadBackup({ ...row, record_kind, event_ref: 'c'.repeat(32) }, input));
  assert.equal(fetched, beforeEvents); assert.equal(clicked, 1);
  const readContext = { source: 'current', tab: 'logs', page_size: 10, records: { logs: { filters: { query: 'retained' }, page: 2, snapshot_ref: 'original-read-ref', selection: { key: 'original-record-key' } } } };
  const parsed = host.window.SystemMaintenanceAPI.pageContext(readContext); assert.equal(parsed.records.logs.selection.key, 'original-record-key');
  assert.equal(parsed.records.logs.snapshot_ref, undefined); assert.equal(parsed.records.logs.page, 2);
  let invalidContexts = 0;
  for (const value of [{ ...readContext, confirm: true }, { ...readContext, request_key: 'not-a-read-context' },
    { ...readContext, page_size: 11 }, { ...readContext, records: { logs: { page: 0 } } },
    { ...readContext, records: { logs: { selection: { key: 'row', write_token: 'forbidden' } } } }]) {
    assert.throws(() => host.window.SystemMaintenanceAPI.pageContext(value)); invalidContexts++;
  }
  process.stdout.write(JSON.stringify({ passed: 1, rejected, browser_downloads: clicked, invalidContexts, event_rejections: 2 }) + '\n');
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
