(function () {
  'use strict';
  const BASE = '/api/workbench/v1/', ACTION = 'scheduling.candidate.adopt';
  const PENDING_KEY = 'aps_workbench_candidate_adoption_pending_v1', EVENT = PENDING_KEY + '_changed';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  const key = v => text(v) && /^adoption-[a-f0-9]{48}$/.test(v), rejections = new WeakSet();
  function check(valid, message = '读到的采用数据不完整，请刷新重试。') { if (!valid) throw new Error(message); }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
  }
  function time(v) {
    if (!text(v) || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(v)) return false;
    const d = new Date(v + 'Z'); return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 19) === v;
  }
  const issues = v => Array.isArray(v) && v.every(r => shape(r, ['code', 'message', 'severity']) && text(r.code) && text(r.message) && r.severity === 'blocker');
  function summary(v) {
    return shape(v, ['candidate_ref', 'run_ref', 'baseline', 'task_count', 'scope_complete']) && ref(v.candidate_ref) && ref(v.run_ref)
      && shape(v.baseline, ['plan_ref', 'version']) && (v.baseline.plan_ref === null ? v.baseline.version === null : ref(v.baseline.plan_ref) && count(v.baseline.version) && v.baseline.version > 0)
      && count(v.task_count) && v.task_count > 0 && v.scope_complete === true;
  }
  function overview(v) {
    const result = { candidate_ref: v.candidate_ref, run_ref: v.run_ref, baseline: v.baseline, task_count: v.task_count, scope_complete: v.scope_complete };
    check(summary(result)); return result;
  }
  function preview(v, candidateRef) {
    check(shape(v, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && v.ok === true && v.schema_version === 1 && Array.isArray(v.warnings) && v.warnings.length === 0
      && shape(v.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of']) && /^[a-f0-9]{32}$/.test(v.meta.request_ref)
      && v.meta.source === 'production' && v.meta.time_basis === 'factory_local' && token(v.meta.snapshot_ref) && time(v.meta.as_of));
    const d = v.data, c = d && d.write_context, validation = d && d.validation;
    check(ref(candidateRef) && object(d) && d.candidate_ref === candidateRef && shape(validation, ['status', 'can_adopt', 'issues']) && issues(validation.issues)
      && shape(c, ['write_token', 'expires_at', 'capabilities', 'blocked_reasons']) && shape(c.capabilities, [ACTION]) && issues(c.blocked_reasons));
    if (validation.can_adopt === true) {
      check(shape(d, ['candidate_ref', 'run_ref', 'baseline', 'task_count', 'scope_complete', 'validation', 'write_context']) && summary(overview(d))
        && validation.status === 'valid' && validation.issues.length === 0 && c.capabilities[ACTION] === true && token(c.write_token)
        && time(c.expires_at) && c.expires_at > v.meta.as_of && c.blocked_reasons.length === 0);
    } else check(shape(d, ['candidate_ref', 'validation', 'write_context']) && validation.can_adopt === false && validation.status === 'blocked'
      && validation.issues.length > 0 && c.capabilities[ACTION] === false && c.write_token === null && c.expires_at === null && c.blocked_reasons.length > 0);
    return d;
  }
  function input(v) {
    check(shape(v, ['confirm', 'reason', 'declared_operator']) && v.confirm === true, '请勾选确认后再正式采用。');
    for (const [name, limit] of [['reason', 1000], ['declared_operator', 100]]) {
      check(text(v[name]) && v[name].trim().length > 0 && Array.from(v[name]).length <= limit && !v[name].includes('\x00'), '请填写采用原因和经办人。');
    }
    return { confirm: true, reason: v.reason.trim(), declared_operator: v.declared_operator.trim() };
  }
  function receipt(v, intent) {
    const d = v && v.data, p = d && d.official_plan, s = intent && intent.preview;
    check(validIntent(intent) && shape(v, ['ok', 'result', 'data', 'warnings', 'receipt_ref', 'replayed']) && v.ok === true && v.result === 'committed'
      && text(v.receipt_ref) && /^[a-f0-9]{32}$/.test(v.receipt_ref) && typeof v.replayed === 'boolean' && Array.isArray(v.warnings) && v.warnings.length === 0
      && shape(d, ['candidate_ref', 'run_ref', 'official_plan', 'row_count']) && d.candidate_ref === intent.candidate_ref && d.run_ref === s.run_ref && d.row_count === s.task_count
      && shape(p, ['plan_ref', 'version', 'kind', 'is_current_official', 'display_name', 'source_run_ref', 'baseline_ref', 'completeness', 'capabilities', 'blocked_reasons'])
      && ref(p.plan_ref) && p.plan_ref !== intent.candidate_ref && p.plan_ref !== s.baseline.plan_ref && count(p.version) && p.version > (s.baseline.version || 0)
      && p.kind === 'official' && p.is_current_official === true && p.display_name === '正式计划 v' + p.version && p.source_run_ref === s.run_ref
      && p.baseline_ref === s.baseline.plan_ref && p.completeness === 'complete' && shape(p.capabilities, ['view', 'edit_draft', 'adopt', 'report_actual'])
      && p.capabilities.view === true && p.capabilities.edit_draft === false && p.capabilities.adopt === false && p.capabilities.report_actual === true
      && Array.isArray(p.blocked_reasons) && p.blocked_reasons.length === 0);
    return v;
  }
  function lookup(v, intent) {
    if (shape(v, ['ok', 'state', 'receipt', 'may_be_in_flight', 'message']) && v.ok === true && v.state === 'not_recorded'
      && v.receipt === null && v.may_be_in_flight === true && text(v.message)) return null;
    return receipt(v, intent);
  }
  function failure(v, status, requestKey) {
    const e = v && v.error, valid = shape(v, ['ok', 'committed', 'error']) && v.ok === false && [false, 'unknown'].includes(v.committed)
      && shape(e, ['code', 'message', 'fields', 'retryable', 'request_ref'], ['request_key', 'result_target']) && text(e.code) && text(e.message)
      && Array.isArray(e.fields) && e.fields.every(f => shape(f, ['path', 'message']) && text(f.path) && text(f.message))
      && typeof e.retryable === 'boolean' && text(e.request_ref) && /^[a-f0-9]{32}$/.test(e.request_ref)
      && (e.request_key === undefined && e.result_target === undefined || key(requestKey) && e.request_key === requestKey && e.result_target === BASE + 'commands/' + requestKey);
    const error = new Error(valid ? e.message : window.WorkbenchTerms.outcomes.pending('采用')); error.code = valid ? e.code : 'invalid_response';
    if (valid && v.committed === false && [400, 409, 422, 503].includes(status) && e.code !== 'request_key_conflict') rejections.add(error);
    return error;
  }
  function validIntent(v) {
    if (!shape(v, ['schema_version', 'candidate_ref', 'request_key', 'input', 'preview', 'phase']) || v.schema_version !== 1 || !ref(v.candidate_ref)
      || !key(v.request_key) || !summary(v.preview) || v.preview.candidate_ref !== v.candidate_ref || !['pending', 'rejected'].includes(v.phase)) return false;
    try { return JSON.stringify(input(v.input)) === JSON.stringify(v.input); } catch (_) { return false; }
  }
  function pending(storage) {
    if (storage === undefined) { try { storage = window.localStorage; } catch (_) { throw new Error('读不到上次采用的操作记录，请重新打开页面。'); } }
    function read() {
      let raw; try { raw = storage.getItem(PENDING_KEY); } catch (_) { throw new Error('读不到上次采用的操作记录，不要重新采用。'); }
      if (raw === null) return null;
      let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('本机存的采用操作记录已损坏，已拦下新采用。请不要再操作，联系维护人员。'); }
      check(validIntent(value), '本机存的采用操作记录不完整，已拦下新采用。请不要再操作，联系维护人员。'); return value;
    }
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    function save(value, previous) {
      check(same(read(), previous), '上次采用记录已变化，没有覆盖其他操作。');
      try { if (value === null) storage.removeItem(PENDING_KEY); else storage.setItem(PENDING_KEY, JSON.stringify(value)); }
      catch (_) { throw new Error('存不下采用的操作记录，没有开始新的采用。请重新打开页面。'); }
      check(same(read(), value), '采用的操作记录没有保存，不要重新采用。');
      window.dispatchEvent(new Event(EVENT)); return value;
    }
    return { read,
      begin(value, values, previous = null) {
        check(!previous || validIntent(previous) && previous.phase === 'rejected' && previous.candidate_ref === value.candidate_ref, '上次采用还没确认结果，不能重新提交。');
        const bytes = new Uint8Array(24); window.crypto.getRandomValues(bytes);
        return save({ schema_version: 1, candidate_ref: value.candidate_ref,
          request_key: previous ? previous.request_key : 'adoption-' + Array.from(bytes, n => n.toString(16).padStart(2, '0')).join(''),
          input: input(values), preview: overview(value), phase: 'pending' }, previous);
      },
      reject(intent, error) { check(rejections.has(error), '没有确认拒绝结果，已保留上次操作。'); return save({ ...intent, phase: 'rejected' }, intent); },
      cancelRejected(intent) { check(validIntent(intent) && intent.phase === 'rejected', '结果还没确认，不能丢弃上次操作。'); return save(null, intent); },
      finish(intent, result) { receipt(result, intent); return save(null, intent); }
    };
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(path, body, signal, requestKey) {
      const controller = new AbortController(), abort = () => controller.abort();
      if (signal) { if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true }); }
      const timer = setTimeout(abort, 30000);
      try {
        const response = await fetcher(BASE + path, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
          ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
        check((response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json');
        const value = await response.json(); if (!response.ok) throw failure(value, response.status, requestKey);
        check(response.status === 200); return value;
      } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
    }
    return {
      async preview(candidateRef, signal) { check(ref(candidateRef)); const v = await request('scheduling/candidates/' + candidateRef + '/adopt-preview', {}, signal); preview(v, candidateRef); return v; },
      async adopt(intent, writeToken) {
        check(validIntent(intent) && intent.phase === 'pending' && token(writeToken));
        const v = await request('scheduling/candidates/' + intent.candidate_ref + '/adopt', { write_token: writeToken, request_key: intent.request_key, input: intent.input }, undefined, intent.request_key);
        receipt(v, intent); return v;
      },
      async lookup(intent, signal) { check(validIntent(intent)); const v = await request('commands/' + intent.request_key, undefined, signal, intent.request_key); lookup(v, intent); return v; }
    };
  }
  window.RunAdoptionAPI = { create, preview, receipt, lookup, input, pending, ref, overview, PENDING_KEY, EVENT, isRejected: e => rejections.has(e) };
})();
