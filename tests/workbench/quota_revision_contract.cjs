'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), ref = 'a'.repeat(48), part = 'b'.repeat(48), sample = 'c'.repeat(48);
const React = { createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
  useState: value => [value, () => {}], useEffect() {}, Fragment: 'fragment' };
const terms = { outcomes: { pending: action => action + '结果待核对', done: (action, message) => action + message }, actions: {} };
const window = { ResourceControls: { Button: 'button', Modal: 'modal' }, CalibrationControls: { text: String, amount: String, unitHours: value => value + ' 小时' },
  WorkbenchFormat: { dateTime: String }, WorkbenchTerms: terms, WorkbenchReference: 'reference', APSResourceContract: {
    object: value => value !== null && typeof value === 'object' && !Array.isArray(value), own: (value, key) => Object.hasOwn(value, key),
    failure: message => new Error(message), receipt: () => 'terminal' }, APSProcessActions: { ref: value => /^[a-f0-9]{48}$/.test(value), token: value => typeof value === 'string' && !!value },
  APSProcessContract: { externalGroup: () => true } };
const context = vm.createContext({ window, React, setTimeout, clearTimeout, AbortController });
const names = ['CalibrationAdoptionAPI.js', 'CalibrationAdoptionControls.jsx', 'ProcessFileContract.js', 'ProcessFilePreview.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: names.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })), check_combined: true });
for (const output of built.outputs) vm.runInContext(output.code, context);
const generated = '2026-10-09T09:00:00', input = { reason: '再次核定', declared_operator: '经办人' };
const suggestion = { template_operation_ref: ref, template_revision: 3, template_snapshot: 'current-template', part_ref: part, part_no: 'P1', part_name: 'Part',
  sequence: 1, operation_label: 'Turning', source: 'internal', old_unit_hours: 3, suggested_unit_hours: 6, sample_count: 5, eligible_sample_count: 5,
  candidate_count: 5, excluded_count: 0, sample_refs: Array.from({ length: 5 }, (_, i) => String(i).repeat(48)),
  sample_revisions: [], exclusion_reasons: [], method_version: 'existing-method', suggestion_ref: ref, operation_ref: ref };
suggestion.sample_revisions = suggestion.sample_refs.map(sample_ref => ({ sample_ref, sample_revision: 'sample-' + sample_ref, template_revision: 3, report_revision_refs: [sample] }));
const samples = suggestion.sample_revisions.map(row => ({ ...row, execution_operation_ref: row.sample_ref, template_operation_ref: ref,
  lineage_evidence_ref: sample, selected: true, eligible: true, effective_processing_hours: 60, completed_quantity: 10, unit_hours: 6,
  unknown_record_count: 0, exclusion_reasons: [], reports: [] }));
const preview = { template_operation_ref: ref, suggestion, generated_at: generated, input, effect_scope: 'future_template_use_only', samples,
  latest_adoption: { template_operation_ref: ref, adoption_ref: 'd'.repeat(48), new_unit_hours: 3, adopted_at: generated },
  validation: { can_adopt: true, issues: [] }, write_context: { write_token: 'token', expires_at: '2026-10-09T09:15:00', capabilities: { 'calibration.adopt': true }, blocked_reasons: [] } };
const envelope = { ok: true, schema_version: 1, warnings: [], meta: { source: 'production', time_basis: 'factory_local', as_of: generated }, data: preview };
const receipt = { ok: true, result: 'committed', receipt_ref: 'e'.repeat(32), replayed: false, warnings: [], data: {
  adoption_ref: 'f'.repeat(48), template_operation_ref: ref, request_key: 'calibration-' + ref, ...input, confirmed: true, application_operator: 'local',
  adopted_at: generated, generated_at: generated, old_unit_hours: 3, new_unit_hours: 6, template_revision_before: 3, template_revision_after: 4,
  method_version: suggestion.method_version, sample_count: 5, sample_refs: suggestion.sample_refs, sample_revisions: suggestion.sample_revisions,
  effect_scope: 'future_template_use_only' } };
const intent = { request_key: receipt.data.request_key, baseline: suggestion, input: { ...input, confirm: true } };
const fetcher = async (url) => ({ status: 200, ok: true, headers: new Map([['Content-Type', 'application/json']]), json: async () => url.endsWith('/adopt-preview') ? envelope : receipt });
function text(node) { if (node == null || typeof node === 'boolean') return ''; if (typeof node !== 'object') return String(node);
  if (Array.isArray(node)) return node.map(text).join(''); if (typeof node.type === 'function') return text(node.type(node.props)); return text(node.props && node.props.children) + (node.type === 'modal' ? text(node.props.footer) : ''); }
(async () => {
  const api = window.CalibrationAdoptionAPI.create(fetcher);
  assert.equal((await api.preview(suggestion, input)).validation.can_adopt, true);
  assert.equal((await api.adopt(intent, 'token')).data.new_unit_hours, 6);
  // Previously saved receipts still render and can be queried after the upgrade.
  receipt.data.locked = true;
  assert.equal((await api.lookup(intent)).data.adoption_ref, receipt.data.adoption_ref);
  const session = { preview, draft: input, consent: true, busy: false };
  const dialog = text(window.CalibrationAdoptionControls.Dialog({ session, detail: { suggestion, samples }, stale: false }));
  assert(dialog.includes('以后可以继续人工修改、导入或采用新建议'));
  assert(dialog.includes('确认采用')); assert(!dialog.includes('锁定')); assert(!dialog.includes('不能再改'));
  const F = window.APSProcessFiles;
  const data = { kind: 'hours', rows: [{ row: 2, entity_ref: part, business_code: 'P1', sequence: 1, result: 'committed' }],
    summary: { new: 0, update: 1, unchanged: 0, delete: 0, rejected: 0 }, affected_refs: [part] };
  assert.equal(F.receipt({ ok: true, result: 'committed', data }, { kind: 'process_hours_import', action: 'confirm' }, 'hours', null, part), data);
  assert.equal(F.hoursCounts(data).changed, 1); assert(!Object.hasOwn(F.hoursCounts(data), 'skipped'));
  console.log('PASS: prior adoption allows new preview, current and old receipts remain readable, revision consent and import counts have no permanent lock.');
})().catch(error => { console.error(error); process.exitCode = 1; });
