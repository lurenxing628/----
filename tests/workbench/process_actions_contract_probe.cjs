'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), calls = [];
const context = { console, window: null, Number, Map, Set, JSON, Date, Error, Object, Array };
context.window = context;
vm.createContext(context);
for (const file of ['resource-contract.js', 'ResourceTableFilterModel.js', 'ResourceMaterialContract.js', 'ProcessContract.js', 'ProcessActionContract.js', 'ProcessFileContract.js'])
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8'), context);
const A = context.APSProcessActions, P = context.APSProcessContract, M = context.ResourceTableFilterModel, F = context.APSProcessFiles;
const r = n => n.toString(16).padStart(48, '0'), k = n => n.toString(16).padStart(64, '0'), t = 'x'.repeat(32);
const scope = { query: '0', stage: 'hours', page: 3, size: 20, sort: [{ field: 'label', direction: 'asc' }, { field: 'operation_count', direction: 'desc' }],
  column_filters: { business_code: { mode: 'exclude', values: [k(1)] }, label: { mode: 'include', values: [k(0)] } } };
const plain = value => JSON.parse(JSON.stringify(value));
assert.deepEqual(plain(A.facetScope(scope, 'label')), { query: '0', stage: 'hours', column_filters: { business_code: scope.column_filters.business_code } });
assert.deepEqual(plain(scope.column_filters.label), { mode: 'include', values: [k(0)] });
assert.deepEqual(plain(M.toolbarScope({ ...scope, status: 'active', category: 'internal', source: 'production' })), { query: '0', status: 'active', category: 'internal', source: 'production' });
const request = { scope, refs: [r(2), r(1)], snapshot_ref: t, page_size: 20 };
assert.deepEqual(plain(A.deleteBody(request)), { scope: plain(A.scope(scope)), refs: request.refs, snapshot_ref: t, page_size: 20 });
assert(!('page' in A.deleteBody(request).scope));
assert.throws(() => A.deleteBody({ ...request, refs: [r(1), r(1)] }));
assert.throws(() => A.scope({ ...scope, column_filters: [] }));
assert.throws(() => A.scope({ ...scope, column_filters: { unknown: { mode: 'include', values: [] } } }));
assert.deepEqual(plain(P.ordering({ sort: [] })), []);
assert.deepEqual(plain(P.ordering({ sort: 'label', direction: 'desc' })), [{ field: 'label', direction: 'desc' }]);
assert.throws(() => P.ordering({ sort: [{ field: 'label', direction: 'asc' }, { field: 'label', direction: 'desc' }] }));
assert.deepEqual(plain(A.createInput({ business_code: ' 00001 ', label: ' Name ', route_raw: ' 5 Turn\n', remark: '' })), { business_code: '00001', label: 'Name', route_raw: ' 5 Turn\n' });
assert.throws(() => A.createInput({ business_code: '', label: 'Name', route_raw: '', remark: '' }));
assert(A.createReason({ write_token: t, capabilities: { 'process.create': true } }, 'demo'));
assert.equal(A.createReason({ write_token: t, capabilities: { 'process.create': true } }, 'production'), '');
const receipt = { ok: true, result: 'committed', receipt_ref: t, replayed: false, warnings: [], data: { entity_ref: r(9), business_code: '00001', workflow: { origin: 'managed', ready: false, stage: 'route' } } };
const intent = { kind: 'process', action: 'create', ref: null, input: { business_code: '00001' } };
assert.equal(A.receipt(receipt, intent).entity_ref, r(9));
assert.throws(() => A.receipt({ ...receipt, result: 'partial' }, intent));
assert.throws(() => A.receipt({ ...receipt, data: { ...receipt.data, entity_ref: null } }, intent));
assert.throws(() => A.receipt({ ...receipt, data: { ...receipt.data, business_code: 'OTHER' } }, intent));
const bulkIntent = { kind: 'process_bulk', action: 'confirm', ref: t };
const bulk = { ...receipt, data: { deleted_count: 2, rows: request.refs.map(entity_ref => ({ entity_ref, result: 'committed' })) } };
assert.equal(A.receipt(bulk, bulkIntent, request.refs).deleted_count, 2);
assert.throws(() => A.receipt(bulk, bulkIntent, request.refs.slice().reverse()));
assert.throws(() => A.receipt({ ...bulk, data: { ...bulk.data, deleted_count: 1 } }, bulkIntent));
assert.throws(() => A.receipt({ ...bulk, data: { deleted_count: 2, rows: [bulk.data.rows[0], bulk.data.rows[0]] } }, bulkIntent));
assert.deepEqual(plain(A.restored(intent)), { mode: 'create', recovery: true });
assert.deepEqual(plain(A.restored(bulkIntent)), { mode: 'bulk', recovery: true });
context.APSResourceAPI = { create: () => Object.fromEntries(['query', 'execute', 'preview', 'lookup', 'readPending', 'savePending', 'clearPending', 'choices', 'download'].map(method => [method, (...args) => { calls.push({ method, args }); return args; }])) };
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/ProcessAPI.js'), 'utf8'), context);
const api = context.APSProcessAPI.create();
api.list('part', scope);
assert.equal(calls.at(-1).args[0], 'entities/part');
assert.deepEqual(JSON.parse(calls.at(-1).args[1].sort), scope.sort);
assert.deepEqual(JSON.parse(calls.at(-1).args[1].column_filters), scope.column_filters);
api.facets('part', { scope: A.facetScope(scope, 'label'), column: 'label', query: '0', page: 2, size: 50, snapshot_ref: t });
assert.equal(calls.at(-1).args[0], 'process-table/facets/label');
assert.deepEqual(JSON.parse(calls.at(-1).args[1].scope), plain(A.facetScope(scope, 'label')));
assert.equal(calls.at(-1).args[1].size, 50);
api.facetSelection('part', { scope: A.facetScope(scope, 'label'), column: 'label', query: '0', size: 50, snapshot_ref: t });
assert.equal(calls.at(-1).args[0], 'process-table/facet-selection/label');
api.command('process', 'create', null, { input: {}, write_token: t });
assert.equal(calls.at(-1).args[0], 'process/parts/create');
api.command('process_bulk', 'confirm', t, { input: { preview_ref: t } });
assert.equal(calls.at(-1).args[0], 'process/parts/bulk-confirm');
assert.throws(() => api.command('process', 'delete', r(1), {}));
assert.throws(() => api.command('process_bulk', 'confirm', t, { input: { preview_ref: 'y'.repeat(32) } }));
api.bulkPreview(A.deleteBody(request));
assert.equal(calls.at(-1).args[0], 'process/parts/bulk-preview');
api.filePreview('hours', 'export', { format: 'csv', selection: 'filtered' });
assert.equal(calls.at(-1).args[0], 'process-files/hours/export-preview');
api.fileDownload('hours', false, { export_ref: t });
assert.equal(calls.at(-1).args[0], 'process-files/hours/export');
assert.deepEqual(plain(calls.at(-1).args[1]), { export_ref: t });
const confirmation = { preview_ref: t, discard_group_refs: [r(3)], confirm_zero_unit_hours: true };
api.command('process_route_import', 'confirm', t, { input: confirmation });
assert.equal(calls.at(-1).args[0], 'process-files/route/confirm');
assert.deepEqual(plain(calls.at(-1).args[1].input), confirmation);
assert.deepEqual(plain(F.exportBody(request, 'explicit', 'csv')), { ...plain(A.listContext(request)), selection: 'explicit', format: 'csv', refs: request.refs });
const targetRequest = { ...request, target_ref: r(2), scope: {} };
assert.deepEqual(plain(F.exportBody(targetRequest, 'explicit', 'csv')), { scope: {}, snapshot_ref: t, page_size: 20, selection: 'explicit', format: 'csv', refs: [r(2)], target_ref: r(2) });
assert.throws(() => F.exportBody(targetRequest, 'filtered', 'csv'));
assert.throws(() => F.exportBody(request, 'selected', 'csv'));
assert.throws(() => F.confirmInput({ preview_ref: t, affected_groups: [{ ref: r(3) }], zero_review_required: true }, [], false));
assert.throws(() => F.confirmInput({ preview_ref: t, affected_groups: [{ ref: r(3) }], zero_review_required: true }, [r(3)], false));
assert.deepEqual(plain(F.confirmInput({ preview_ref: t, affected_groups: [{ ref: r(3) }], zero_review_required: true }, [r(3)], true)), confirmation);
const fileReceipt = { ...receipt, data: { kind: 'hours', rows: [{ row: 2, result: 'committed', entity_ref: r(2), business_code: '00001', sequence: '9223372036854775807' }], summary: { new: 0, update: 1, unchanged: 0, delete: 0, rejected: 0 }, affected_refs: [r(2)], skipped_count: 0, skipped_refs: [], skipped_rows: [] } };
const fileIntent = { kind: 'process_hours_import', action: 'confirm', ref: t };
assert.equal(F.receipt(fileReceipt, fileIntent, 'hours').rows[0].sequence, '9223372036854775807');
assert.throws(() => F.receipt({ ...fileReceipt, result: 'partial' }, fileIntent, 'hours'));
assert.throws(() => F.receipt(fileReceipt, fileIntent, 'hours', undefined, r(1)));
assert.throws(() => F.receipt({ ...fileReceipt, data: { ...fileReceipt.data, affected_refs: [r(1)] } }, fileIntent, 'hours'));
assert.throws(() => F.receipt({ ...fileReceipt, data: { ...fileReceipt.data, rows: [{ ...fileReceipt.data.rows[0], sequence: 9007199254740992 }] } }, fileIntent, 'hours'));
assert.throws(() => F.receipt(fileReceipt, fileIntent, 'hours', { rows: [{ row: 2, entity_ref: r(2), business_code: 'OTHER' }] }));
const envelope = data => ({ ok: true, schema_version: 1, data, meta: { source: 'production', time_basis: 'factory_local', snapshot_ref: t, request_ref: 'test', as_of: '2026-09-09T12:00:00' }, warnings: [] });
const fileRow = { row: 2, business_code: '00001', entity_ref: r(2), sequence: '9223372036854775807', action: 'update', result: 'update', before: { unit_hours: 1 }, after: { unit_hours: 0 }, changes: { unit_hours: { before: 1, after: 0 } }, reference_count: 0, requires_confirmation: true, errors: [], route_summary: null };
const filePreview = { kind: 'hours', operation: 'process_hours_import.confirm', preview_ref: t, expires_at: '2099-01-01T00:00:00Z', commit_policy: 'atomic', can_confirm: true,
  format: 'csv', mode: 'upsert', template_version: 1, file_sha256: 'a'.repeat(64), instructions: '空白不补零', zero_review_required: true, scope: {},
  write_context: { write_token: t, capabilities: { 'process_hours_import.confirm': true }, blocked_reasons: [] }, summary: fileReceipt.data.summary,
  rows: [fileRow], columns: [{ key: 'unit_hours', label: '单件工时' }], affected_groups: [], skipped_count: 0, skipped_refs: [], skipped_rows: [] };
assert.equal(F.preview(envelope(filePreview), 'hours', 'csv', targetRequest).data.rows[0].sequence, '9223372036854775807');
assert.throws(() => F.preview(envelope({ ...filePreview, rows: [{ ...fileRow, sequence: 9007199254740992 }] }), 'hours', 'csv', targetRequest));
assert.throws(() => F.preview(envelope(filePreview), 'hours', 'xlsx', targetRequest));
assert.throws(() => F.preview(envelope(filePreview), 'hours', 'csv', { ...targetRequest, target_ref: r(1) }));
assert.throws(() => F.preview(envelope({ ...filePreview, rows: [{ ...fileRow, before: { entity_key: 'hidden' } }] }), 'hours', 'csv', targetRequest));
assert.throws(() => F.preview(envelope({ ...filePreview, rows: [{ ...fileRow, route_summary: { counts: { operations: 1, recognized: 0, unknown: 0 }, diagnostics: [], can_confirm_route: true } }] }), 'hours', 'csv', targetRequest));
assert.equal(F.receipt(fileReceipt, fileIntent, 'hours', filePreview).skipped_count, 0);
assert.deepEqual(plain(F.hoursCounts(filePreview)), { changed: 1, skipped: 0, unchanged: 0, rejected: 0 });
const skip = { row: 3, code: 'calibration_quota_locked', template_operation_ref: r(30), adoption_ref: r(31), reason: 'Verified calibration', message: 'Locked quota preserved' };
const { row: skipRowNumber, ...skipReason } = skip;
const skippedRow = { ...plain(fileRow), row: skipRowNumber, sequence: 5, result: 'unchanged', action: 'unchanged',
  before: { unit_hours: 3 }, after: { unit_hours: 3 }, changes: {}, requires_confirmation: false, skip_reason: skipReason };
const mixedPreview = { ...plain(filePreview), rows: [plain(fileRow), skippedRow], summary: { ...filePreview.summary, unchanged: 1 },
  skipped_count: 1, skipped_refs: [skip.template_operation_ref], skipped_rows: [skip] };
const mixedReceipt = { ...plain(fileReceipt), data: { ...plain(fileReceipt.data), summary: mixedPreview.summary,
  rows: [plain(fileReceipt.data.rows[0]), { row: 3, result: 'unchanged', entity_ref: r(2), business_code: '00001', sequence: 5, skip_reason: skipReason }],
  skipped_count: 1, skipped_refs: [skip.template_operation_ref], skipped_rows: [skip] } };
const allSkippedPreview = { ...plain(mixedPreview), rows: [plain(skippedRow)], summary: { new: 0, update: 0, unchanged: 1, delete: 0, rejected: 0 } };
const allSkippedReceipt = { ...plain(mixedReceipt), result: 'unchanged', data: { ...plain(mixedReceipt.data), rows: [plain(mixedReceipt.data.rows[1])], summary: allSkippedPreview.summary } };
let skipRejections = 0;
function rejectSkipPreview(data, label) {
  assert.throws(() => F.preview(envelope(data), 'hours', 'csv', targetRequest), /工时锁定/, label);
  skipRejections++;
}
function rejectSkipReceipt(value, preview, label) {
  assert.throws(() => F.receipt(value, fileIntent, 'hours', preview), /工时锁定|实际导入数量/, label);
  skipRejections++;
}
for (const [preview, value] of [[filePreview, fileReceipt], [mixedPreview, mixedReceipt], [allSkippedPreview, allSkippedReceipt]]) {
  assert.equal(F.preview(envelope(preview), 'hours', 'csv', targetRequest).data.skipped_count, preview.skipped_rows.length);
  assert.equal(F.receipt(value, fileIntent, 'hours', preview).skipped_count, preview.skipped_rows.length);
  assert.equal(F.receipt(value, fileIntent, 'hours').skipped_count, preview.skipped_rows.length);
  for (const key of ['skipped_count', 'skipped_refs', 'skipped_rows']) {
    const invalidPreview = plain(preview), invalidReceipt = plain(value);
    delete invalidPreview[key]; delete invalidReceipt.data[key];
    rejectSkipPreview(invalidPreview, 'missing preview ' + key);
    rejectSkipReceipt(invalidReceipt, preview, 'missing receipt ' + key);
    rejectSkipReceipt(invalidReceipt, undefined, 'recovered receipt missing ' + key);
  }
}
assert.deepEqual(plain(F.hoursCounts(mixedPreview)), { changed: 1, skipped: 1, unchanged: 0, rejected: 0 });
assert.deepEqual(plain(F.hoursCounts(allSkippedReceipt.data)), { changed: 0, skipped: 1, unchanged: 0, rejected: 0 });
const invalidSkips = [
  ['count mismatch', d => { d.skipped_count = 0; }],
  ['count type', d => { d.skipped_count = '1'; }],
  ['foreign template ref', d => { d.skipped_refs[0] = r(99); }],
  ['duplicate skip', d => { d.skipped_rows.push(plain(d.skipped_rows[0])); d.skipped_refs.push(d.skipped_refs[0]); d.skipped_count++; }],
  ['unknown file row', d => { d.skipped_rows[0].row = 999; }],
  ['missing row reason', d => { delete d.rows[1].skip_reason; }],
  ['unreported row reason', d => { d.skipped_count = 0; d.skipped_refs = []; d.skipped_rows = []; }],
  ...['code', 'template_operation_ref', 'adoption_ref', 'reason', 'message'].map(key => ['missing skip ' + key, d => { delete d.skipped_rows[0][key]; }]),
  ...['code', 'template_operation_ref', 'adoption_ref', 'reason', 'message'].map(key => ['row reason mismatch ' + key, d => { d.rows[1].skip_reason[key] = 'different'; }]),
];
for (const [label, damage] of invalidSkips) {
  const invalidPreview = plain(mixedPreview), invalidReceipt = plain(mixedReceipt);
  damage(invalidPreview); damage(invalidReceipt.data);
  rejectSkipPreview(invalidPreview, label);
  rejectSkipReceipt(invalidReceipt, mixedPreview, label);
  rejectSkipReceipt(invalidReceipt, undefined, 'recovered ' + label);
}
for (const damage of [d => { d.rows[1].requires_confirmation = true; }, d => { d.rows[1].after.unit_hours = 99; },
  d => { d.rows[1].changes = { unit_hours: { before: 3, after: 99 } }; }]) {
  const invalid = plain(mixedPreview); damage(invalid); rejectSkipPreview(invalid, 'locked row cannot change');
}
const changedReason = plain(mixedReceipt);
changedReason.data.skipped_rows[0].reason = changedReason.data.rows[1].skip_reason.reason = 'Another reason';
rejectSkipReceipt(changedReason, mixedPreview, 'receipt reason must match preview');
console.log('process-hours-skip-contract: zero/mixed/allskip passed; strict rejections=' + skipRejections);
const body = F.exportBody(request, 'explicit', 'csv');
const exported = { kind: 'hours', export_ref: t, expires_at: '2099-01-01T00:00:00Z', selection: 'explicit', scope: body.scope, target_ref: null, row_count: 130, part_count: 2, format: 'csv', columns: [{ key: 'business_code', label: '图号' }] };
assert.equal(F.exportPreview(envelope(exported), 'hours', body).data.row_count, 130);
assert.throws(() => F.exportPreview(envelope({ ...exported, part_count: 1 }), 'hours', body));
assert.throws(() => F.exportPreview(envelope({ ...exported, kind: 'route' }), 'route', body));
assert.throws(() => F.exportPreview(envelope({ ...exported, format: 'xlsx' }), 'hours', body));
const detailBody = F.exportBody(targetRequest, 'explicit', 'csv');
assert.equal(F.exportPreview(envelope({ ...exported, scope: {}, target_ref: r(2), part_count: 1 }), 'hours', detailBody).data.part_count, 1);
assert.throws(() => F.exportPreview(envelope({ ...exported, target_ref: r(2), part_count: 1 }), 'hours', detailBody));
console.log('process-actions-contract: scopes, original identities, atomic receipts, file confirmations and API encoding passed');
