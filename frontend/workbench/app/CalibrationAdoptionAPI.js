(function () {
  'use strict';
  const T = window.APSWorkbenchTransport, C = window.CalibrationAPI, BASE = '/api/workbench/v1/calibration/', ACTION = 'calibration.adopt';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
  const key = v => typeof v === 'string' && /^calibration-[a-f0-9]{48}$/.test(v);
  const text = v => typeof v === 'string' && v.length > 0;
  const number = v => typeof v === 'number' && Number.isFinite(v) && v >= 0;
  const equal = (a, b) => T.equal(a, b);
  function check(value, message = '读到的采用结果不完整或来源不一致，没有确认采用。') { if (!value) throw new Error(message); }
  // 采用表单的唯一校验点：只认原因和经办人两项，校验后去掉首尾空白。
  function input(draft) {
    check(object(draft) && Object.keys(draft).length === 2 && typeof draft.reason === 'string' && draft.reason.trim()
      && Array.from(draft.reason).length <= 2000 && !draft.reason.includes('\0'), '请填写 1 到 2000 字的采用原因。');
    check(typeof draft.declared_operator === 'string' && draft.declared_operator.trim() && Array.from(draft.declared_operator).length <= 100
      && !draft.declared_operator.includes('\0'), '请填写 1 到 100 字的经办人。');
    return { reason: draft.reason.trim(), declared_operator: draft.declared_operator.trim() };
  }
  // 确认采用的负载由已校验的填写内容加上用户确认构成。
  const confirmation = filled => ({ ...filled, confirm: true });
  // 采用绑定的纯投影：行已在明细读取、采用预检或本机记录读取边界按 CalibrationAPI.validBinding 校验过。
  const binding = row => Object.fromEntries(C.bindingFields.map(k => [k, row[k]]));
  const issues = value => Array.isArray(value) && value.every(v => object(v) && text(v.code) && text(v.message));
  // filled 是 input() 规整过的填写内容，original 是所选模板行的采用绑定。
  function previewResult(value, original, filled) {
    const d = value && value.data, m = value && value.meta, c = d && d.write_context, v = d && d.validation;
    check(!value.warnings.length && object(d) && d.template_operation_ref === original.template_operation_ref && d.generated_at === m.as_of
      && d.effect_scope === 'future_template_use_only' && equal(d.input, filled) && object(v) && typeof v.can_adopt === 'boolean'
      && issues(v.issues) && object(c) && object(c.capabilities) && issues(c.blocked_reasons) && C.validBinding(d.suggestion));
    check(equal(binding(d.suggestion), original), '模板、原定额或完工记录已变化，请点「刷新所选模板」后重新预检。');
    const row = d.suggestion;
    check(row.suggestion_ref === row.template_operation_ref && row.operation_ref === row.template_operation_ref && Array.isArray(d.samples)
      && d.samples.length === row.sample_count && d.samples.every((sample, i) => object(sample) && sample.sample_ref === row.sample_refs[i]
        && sample.execution_operation_ref === sample.sample_ref && sample.template_operation_ref === row.template_operation_ref
        && sample.template_revision === row.template_revision && ref(sample.lineage_evidence_ref) && sample.selected === true && sample.eligible === true
        && sample.sample_revision === row.sample_revisions[i].sample_revision && equal(sample.report_revision_refs, row.sample_revisions[i].report_revision_refs)
        && number(sample.effective_processing_hours) && number(sample.completed_quantity) && sample.completed_quantity > 0 && number(sample.unit_hours)
        && sample.unknown_record_count === 0 && Array.isArray(sample.exclusion_reasons) && !sample.exclusion_reasons.length && Array.isArray(sample.reports)));
    if (v.can_adopt) check(v.issues.length === 0 && c.blocked_reasons.length === 0 && c.capabilities[ACTION] === true && text(c.write_token)
      && text(c.expires_at) && c.expires_at > d.generated_at && row.sample_count >= 5 && row.suggested_unit_hours !== null);
    else check(v.issues.length > 0 && c.capabilities[ACTION] === false && c.write_token === null && c.expires_at === null && equal(v.issues, c.blocked_reasons));
    if (d.latest_adoption !== null) check(object(d.latest_adoption) && d.latest_adoption.template_operation_ref === original.template_operation_ref
      && ref(d.latest_adoption.adoption_ref) && number(d.latest_adoption.new_unit_hours) && text(d.latest_adoption.adopted_at));
    return d;
  }
  // intent 是本存储读到或刚登记的采用记录，baseline 与 input 都已校验过。
  function receipt(value, intent) {
    const d = value && value.data, s = intent.baseline;
    check(value && value.ok === true && value.result === 'committed'
      && typeof value.receipt_ref === 'string' && /^[a-f0-9]{32}$/.test(value.receipt_ref) && typeof value.replayed === 'boolean'
      && Array.isArray(value.warnings) && !value.warnings.length && object(d) && ref(d.adoption_ref) && d.template_operation_ref === s.template_operation_ref
      && d.request_key === intent.request_key && d.reason === intent.input.reason && d.declared_operator === intent.input.declared_operator && d.confirmed === true
      && text(d.application_operator) && text(d.adopted_at) && text(d.generated_at)
      && d.old_unit_hours === s.old_unit_hours && d.new_unit_hours === s.suggested_unit_hours && d.template_revision_before === s.template_revision
      && d.template_revision_after === s.template_revision + Number(s.old_unit_hours !== s.suggested_unit_hours)
      && d.method_version === s.method_version && d.sample_count === s.sample_count && equal(d.sample_refs, s.sample_refs)
      && equal(d.sample_revisions, s.sample_revisions) && d.effect_scope === 'future_template_use_only');
    return value;
  }
  // 预检、采用和回执查询都按 30 秒等待；回执还没记下时 lookup 返回 null。
  // row 是明细读取已校验的建议行，filled 是 input() 规整过的填写内容。
  async function preview(row, filled, signal) {
    const original = binding(row);
    return previewResult(await T.preview(BASE + original.template_operation_ref + '/adopt-preview', { input: filled }, { signal, timeout: 30000 }), original, filled);
  }
  // intent 是本存储登记的采用记录（input 已带确认），writeToken 已由 previewResult 核过。
  async function adopt(intent, writeToken) {
    return receipt(await T.command(BASE + intent.baseline.template_operation_ref + '/adopt', { write_token: writeToken, request_key: intent.request_key, input: intent.input },
      { timeout: 30000, expect: '/api/workbench/v1/commands/' + intent.request_key }), intent);
  }
  async function lookup(intent, signal) {
    const value = await T.lookup(BASE + intent.baseline.template_operation_ref + '/adopt/receipts/' + intent.request_key, { signal, timeout: 30000 });
    return value === null ? null : receipt(value, intent);
  }
  window.CalibrationAdoptionAPI = { preview, adopt, lookup, receipt, binding, input, confirmation, check, key, equal };
})();
