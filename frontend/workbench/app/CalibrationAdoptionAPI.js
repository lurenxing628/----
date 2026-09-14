(function () {
  'use strict';
  const BASE = '/api/workbench/v1/calibration/', ACTION = 'calibration.adopt', rejected = new WeakSet();
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
  const key = v => typeof v === 'string' && /^calibration-[a-f0-9]{48}$/.test(v);
  const text = v => typeof v === 'string' && v.length > 0;
  const number = v => typeof v === 'number' && Number.isFinite(v) && v >= 0;
  const equal = (a, b) => canonical(a) === canonical(b);
  function canonical(v) { return JSON.stringify(v, (_, value) => object(value) ? Object.keys(value).sort().reduce((out, k) => { out[k] = value[k]; return out; }, {}) : value); }
  function check(value, message = '读到的采用结果不完整或来源不一致，没有确认采用。') { if (!value) throw new Error(message); }
  function input(value, confirmed = false) {
    check(object(value) && Object.keys(value).length === (confirmed ? 3 : 2) && (!confirmed || value.confirm === true) && typeof value.reason === 'string' && value.reason.trim()
      && Array.from(value.reason).length <= 2000 && !value.reason.includes('\0'), '请填写 1 到 2000 字的采用原因。');
    check(typeof value.declared_operator === 'string' && value.declared_operator.trim() && Array.from(value.declared_operator).length <= 100
      && !value.declared_operator.includes('\0'), '请填写 1 到 100 字的经办人。');
    return { reason: value.reason.trim(), declared_operator: value.declared_operator.trim(), ...(confirmed ? { confirm: true } : {}) };
  }
  const bindingFields = ['template_operation_ref', 'template_revision', 'template_snapshot', 'part_ref', 'part_no', 'part_name', 'sequence', 'operation_label', 'source',
    'old_unit_hours', 'suggested_unit_hours', 'sample_count', 'eligible_sample_count', 'candidate_count', 'excluded_count', 'sample_refs', 'sample_revisions', 'exclusion_reasons', 'method_version'];
  function binding(row) {
    check(object(row) && bindingFields.every(k => Object.prototype.hasOwnProperty.call(row, k)) && ref(row.template_operation_ref) && ref(row.part_ref)
      && Number.isInteger(row.template_revision) && row.template_revision > 0 && text(row.template_snapshot) && text(row.method_version)
      && [row.old_unit_hours, row.suggested_unit_hours].every(v => v === null || number(v))
      && ['sample_count', 'eligible_sample_count', 'candidate_count', 'excluded_count'].every(k => Number.isInteger(row[k]) && row[k] >= 0)
      && row.sample_count <= 20 && row.sample_count <= row.eligible_sample_count && row.eligible_sample_count <= row.candidate_count
      && row.excluded_count === row.candidate_count - row.sample_count && Array.isArray(row.sample_refs) && row.sample_refs.length === row.sample_count
      && row.sample_refs.every(ref) && new Set(row.sample_refs).size === row.sample_count && Array.isArray(row.sample_revisions)
      && row.sample_revisions.length === row.sample_count && row.sample_revisions.every((r, i) => object(r) && r.sample_ref === row.sample_refs[i]
        && text(r.sample_revision) && r.template_revision === row.template_revision && Array.isArray(r.report_revision_refs) && r.report_revision_refs.every(ref))
      && Array.isArray(row.exclusion_reasons));
    return Object.fromEntries(bindingFields.map(k => [k, row[k]]));
  }
  const issues = value => Array.isArray(value) && value.every(v => object(v) && text(v.code) && text(v.message));
  function preview(value, original, intent) {
    const d = value && value.data, m = value && value.meta, c = d && d.write_context, v = d && d.validation;
    check(value && value.ok === true && value.schema_version === 1 && Array.isArray(value.warnings) && !value.warnings.length
      && m && m.source === 'production' && m.time_basis === 'factory_local' && text(m.as_of) && object(d)
      && d.template_operation_ref === original.template_operation_ref && d.generated_at === m.as_of
      && d.effect_scope === 'future_template_use_only' && equal(d.input, input(intent)) && object(v) && typeof v.can_adopt === 'boolean'
      && issues(v.issues) && object(c) && object(c.capabilities) && issues(c.blocked_reasons));
    check(equal(binding(d.suggestion), binding(original)), '模板、原定额或完工记录已变化，请点「刷新所选模板」后重新预检。');
    const row = d.suggestion;
    check(row.suggestion_ref === row.template_operation_ref && row.operation_ref === row.template_operation_ref && Array.isArray(d.samples)
      && d.samples.length === row.sample_count && d.samples.every((sample, i) => object(sample) && sample.sample_ref === row.sample_refs[i]
        && sample.execution_operation_ref === sample.sample_ref && sample.template_operation_ref === row.template_operation_ref
        && sample.template_revision === row.template_revision && ref(sample.lineage_evidence_ref) && sample.selected === true && sample.eligible === true
        && sample.sample_revision === row.sample_revisions[i].sample_revision && equal(sample.report_revision_refs, row.sample_revisions[i].report_revision_refs)
        && number(sample.effective_processing_hours) && number(sample.completed_quantity) && sample.completed_quantity > 0 && number(sample.unit_hours)
        && sample.unknown_record_count === 0 && Array.isArray(sample.exclusion_reasons) && !sample.exclusion_reasons.length && Array.isArray(sample.reports)));
    if (v.can_adopt) check(v.issues.length === 0 && c.blocked_reasons.length === 0 && c.capabilities[ACTION] === true && text(c.write_token)
      && text(c.expires_at) && c.expires_at > d.generated_at && d.quota_lock === null && row.sample_count >= 5 && number(row.suggested_unit_hours));
    else check(v.issues.length > 0 && c.capabilities[ACTION] === false && c.write_token === null && c.expires_at === null && equal(v.issues, c.blocked_reasons));
    if (d.quota_lock !== null) check(object(d.quota_lock) && d.quota_lock.template_operation_ref === original.template_operation_ref
      && d.quota_lock.locked === true && ref(d.quota_lock.adoption_ref) && number(d.quota_lock.locked_unit_hours));
    return d;
  }
  function receipt(value, intent) {
    const d = value && value.data, s = intent && intent.baseline;
    check(object(intent) && key(intent.request_key) && s && value && value.ok === true && value.result === 'committed'
      && typeof value.receipt_ref === 'string' && /^[a-f0-9]{32}$/.test(value.receipt_ref) && typeof value.replayed === 'boolean'
      && Array.isArray(value.warnings) && !value.warnings.length && object(d) && ref(d.adoption_ref) && d.template_operation_ref === s.template_operation_ref
      && d.request_key === intent.request_key && d.reason === intent.input.reason && d.declared_operator === intent.input.declared_operator && d.confirmed === true
      && text(d.application_operator) && text(d.adopted_at) && text(d.generated_at)
      && d.old_unit_hours === s.old_unit_hours && d.new_unit_hours === s.suggested_unit_hours && d.template_revision_before === s.template_revision
      && d.template_revision_after === s.template_revision + Number(s.old_unit_hours !== s.suggested_unit_hours)
      && d.method_version === s.method_version && d.sample_count === s.sample_count && equal(d.sample_refs, s.sample_refs)
      && equal(d.sample_revisions, s.sample_revisions) && d.locked === true && d.effect_scope === 'future_template_use_only');
    return value;
  }
  function failure(value, status) {
    const e = value && value.error;
    const valid = object(value) && value.ok === false && [false, 'unknown'].includes(value.committed) && object(e) && text(e.code) && text(e.message)
      && Array.isArray(e.fields) && typeof e.retryable === 'boolean' && typeof e.request_ref === 'string' && /^[a-f0-9]{32}$/.test(e.request_ref);
    const error = new Error(valid ? e.message : window.WorkbenchTerms.outcomes.pending('采用')); error.code = valid ? e.code : 'invalid_response'; error.status = status;
    if (valid && value.committed === false && [400, 404, 409, 422, 503].includes(status) && !['request_key_conflict', 'receipt_not_found'].includes(e.code)) rejected.add(error);
    error.notFound = valid && value.committed === false && status === 404 && e.code === 'receipt_not_found';
    return error;
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(path, body, signal) {
      const controller = new AbortController(), abort = () => controller.abort();
      if (signal) { signal.addEventListener('abort', abort, { once: true }); if (signal.aborted) abort(); }
      const timer = setTimeout(abort, 30000);
      try {
        const response = await fetcher(BASE + path, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal,
          ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
        if (response.status === 404 && !(response.headers.get('Content-Type') || '').includes('application/json') && path.endsWith('/adopt-preview'))
          throw new Error(window.WorkbenchTerms.outcomes.unavailable + '仍可以核对完工记录和导出。');
        check((response.headers.get('Content-Type') || '').split(';')[0].toLowerCase() === 'application/json');
        const value = await response.json(); if (!response.ok) throw failure(value, response.status);
        check(response.status === 200); return value;
      } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
    }
    return {
      async preview(row, values, signal) { const original = binding(row), intent = input(values);
        return preview(await request(original.template_operation_ref + '/adopt-preview', { input: intent }, signal), original, intent); },
      async adopt(intent, token) { check(text(token)); return receipt(await request(intent.baseline.template_operation_ref + '/adopt', {
        write_token: token, request_key: intent.request_key, input: input(intent.input, true) }), intent); },
      async lookup(intent, signal) {
        check(key(intent.request_key) && ref(intent.baseline.template_operation_ref));
        try { return receipt(await request(intent.baseline.template_operation_ref + '/adopt/receipts/' + intent.request_key, undefined, signal), intent); }
        catch (e) { if (e.notFound) return null; throw e; }
      }
    };
  }
  window.CalibrationAdoptionAPI = { create, preview, receipt, binding, input, check, ref, key, equal, isRejected: e => rejected.has(e) };
})();
