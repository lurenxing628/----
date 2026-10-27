(function () {
  'use strict';
  const T = window.APSWorkbenchTransport, BASE = '/api/workbench/v1/trial/scenarios/', ACTION = 'trial.scenario.adopt';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v), text = v => typeof v === 'string';
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), key = v => text(v) && /^trial-adoption-[a-f0-9]{48}$/.test(v);
  const token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v), positive = v => Number.isSafeInteger(v) && v > 0;
  function check(v, message = '读到的采用数据不完整或对不上，这次没有确认采用。请刷新重试。') { if (!v) throw new Error(message); }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
  }
  function equal(a, b) {
    const canonical = v => JSON.stringify(v, (_, x) => object(x) ? Object.keys(x).sort().reduce((o, k) => { o[k] = x[k]; return o; }, {}) : x);
    return canonical(a) === canonical(b);
  }
  const DAYS = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  function time(v) {
    if (!text(v) || !/^(?!0000)\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.(?!000000$)\d{6})?(?![\s\S])/.test(v)) return false;
    const y = (v.charCodeAt(0) - 48) * 1000 + (v.charCodeAt(1) - 48) * 100 + (v.charCodeAt(2) - 48) * 10 + (v.charCodeAt(3) - 48);
    const m = (v.charCodeAt(5) - 48) * 10 + (v.charCodeAt(6) - 48), d = (v.charCodeAt(8) - 48) * 10 + (v.charCodeAt(9) - 48);
    return m >= 1 && m <= 12 && d >= 1 && d <= (m === 2 && y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0) ? 29 : DAYS[m]);
  }
  const issues = v => Array.isArray(v) && v.every(r => shape(r, ['code', 'message', 'severity'], ['task_ref', 'related_task_ref'])
    && text(r.code) && r.code && text(r.message) && r.message && r.severity === 'blocker'
    && ['task_ref', 'related_task_ref'].every(k => r[k] === undefined || r[k] === null || ref(r[k])));
  // 采用范围有两种来源：试调详情（source）不带数据上下文，可采用的预检（overview）恒带数据上下文。
  function scope(v) {
    check(object(v) && ref(v.scenario_ref) && ref(v.draft_ref) && v.scenario_ref !== v.draft_ref && positive(v.task_count) && v.scope_complete === true
      && shape(v.baseline, ['plan_ref', 'version']) && (v.baseline.plan_ref === null ? v.baseline.version === null : ref(v.baseline.plan_ref) && positive(v.baseline.version)));
    return { scenario_ref: v.scenario_ref, draft_ref: v.draft_ref, baseline: v.baseline, task_count: v.task_count, scope_complete: true };
  }
  function overview(v) {
    check(window.RunAdoptionAPI.contextRef(v.data_context_ref));
    return { ...scope(v), data_context_ref: v.data_context_ref };
  }
  function sameScope(a, b) {
    return a.scenario_ref === b.scenario_ref && a.draft_ref === b.draft_ref && a.task_count === b.task_count
      && a.scope_complete === b.scope_complete && a.baseline.plan_ref === b.baseline.plan_ref && a.baseline.version === b.baseline.version;
  }
  function source(scenarioRef, data) {
    check(ref(scenarioRef) && object(data) && data.scenario_ref === scenarioRef && data.status === 'saved'
      && data.tasks_complete === true && Array.isArray(data.tasks) && data.tasks.length === data.task_count,
    '请先完整读取所选的试调方案；不能采用其他记录或不完整的内容。');
    return scope({ ...data, scope_complete: true });
  }
  // 信封已由 transport 校验；采用预检和回执查询都不该带提示。
  function content(v) { check(!v.warnings.length); return v.data; }
  function previewResult(v, original) {
    const d = content(v), c = d && d.write_context, validation = d && d.validation;
    check(object(d) && d.scenario_ref === original.scenario_ref && shape(validation, ['status', 'can_adopt', 'issues']) && issues(validation.issues)
      && shape(c, ['write_token', 'expires_at', 'capabilities', 'blocked_reasons']) && shape(c.capabilities, [ACTION]) && issues(c.blocked_reasons));
    if (validation.can_adopt === true) {
      check(shape(d, ['scenario_ref', 'draft_ref', 'baseline', 'task_count', 'scope_complete', 'validation', 'write_context', 'data_context_ref'])
        && sameScope(overview(d), original) && validation.status === 'valid' && !validation.issues.length && c.capabilities[ACTION] === true
        && token(c.write_token) && time(c.expires_at) && c.expires_at > v.meta.as_of && !c.blocked_reasons.length);
    } else check(shape(d, ['scenario_ref', 'validation', 'write_context']) && validation.can_adopt === false && validation.status === 'blocked'
      && validation.issues.length > 0 && equal(validation.issues, c.blocked_reasons) && c.capabilities[ACTION] === false && c.write_token === null && c.expires_at === null);
    return d;
  }
  function input(v) {
    check(shape(v, ['confirm', 'reason', 'declared_operator']) && v.confirm === true, '请勾选确认正式采用。');
    for (const [name, limit] of [['reason', 1000], ['declared_operator', 100]]) check(text(v[name]) && v[name].trim()
      && Array.from(v[name].trim()).length <= limit && !v[name].includes('\0'), '请填写采用原因（1 至 1000 字）和经办人（1 至 100 字）。');
    return { confirm: true, reason: v.reason.trim(), declared_operator: v.declared_operator.trim() };
  }
  function receipt(v, intent) {
    const d = v && v.data, p = d && d.official_plan, s = overview(intent.preview);
    check(key(intent.request_key) && intent.scenario_ref === s.scenario_ref && equal(input(intent.input), intent.input)
      && shape(v, ['ok', 'result', 'data', 'receipt_ref', 'replayed', 'warnings']) && v.ok === true && v.result === 'committed'
      && text(v.receipt_ref) && /^[a-f0-9]{32}$/.test(v.receipt_ref) && typeof v.replayed === 'boolean' && Array.isArray(v.warnings) && !v.warnings.length
      && shape(d, ['scenario_ref', 'draft_ref', 'row_count', 'official_plan']) && d.scenario_ref === s.scenario_ref && d.draft_ref === s.draft_ref && d.row_count === s.task_count
      && shape(p, ['plan_ref', 'version', 'kind', 'is_current_official', 'display_name', 'baseline_ref', 'completeness', 'capabilities', 'blocked_reasons', 'source_scenario_ref', 'source_draft_ref'])
      && ref(p.plan_ref) && ![s.scenario_ref, s.draft_ref, s.baseline.plan_ref].includes(p.plan_ref) && positive(p.version) && p.version > (s.baseline.version === null ? 0 : s.baseline.version)
      && p.kind === 'official' && p.is_current_official === true && p.display_name === '正式计划 v' + p.version && p.completeness === 'complete'
      && p.source_scenario_ref === s.scenario_ref && p.source_draft_ref === s.draft_ref && p.baseline_ref === s.baseline.plan_ref
      && equal(p.capabilities, { view: true, edit_draft: false, adopt: false, report_actual: true }) && Array.isArray(p.blocked_reasons) && !p.blocked_reasons.length);
    return v;
  }
  function lookupResult(v, intent) {
    const d = content(v);
    if (d?.state === 'not_observed') {
      check(shape(d, ['state', 'receipt', 'may_be_in_flight', 'can_retry_automatically']) && d.receipt === null
        && typeof d.may_be_in_flight === 'boolean' && d.can_retry_automatically === false);
      return { state: 'not_observed', receipt: null, may_be_in_flight: d.may_be_in_flight, can_retry_automatically: false };
    }
    check(shape(d, ['state', 'receipt']) && d.state === 'committed'); return receipt(d.receipt, intent);
  }
  // original 由 source() 从完整读取的试调方案构造；预检、采用和回执查询都按 30 秒等待。
  async function preview(original, signal) {
    return previewResult(await T.preview(BASE + original.scenario_ref + '/adopt-preview', {}, { signal, timeout: 30000 }), original);
  }
  async function adopt(intent, writeToken) {
    check(key(intent.request_key) && intent.phase === 'pending' && token(writeToken)); overview(intent.preview);
    const target = BASE + intent.scenario_ref + '/adoption-commands/' + intent.request_key;
    return receipt(await T.command(BASE + intent.scenario_ref + '/adopt', { write_token: writeToken, request_key: intent.request_key, input: input(intent.input) },
      { timeout: 30000, expect: target }), intent);
  }
  async function lookup(intent, signal) {
    check(key(intent.request_key) && ref(intent.scenario_ref));
    return lookupResult(await T.read(BASE + intent.scenario_ref + '/adoption-commands/' + intent.request_key,
      { data_context_ref: intent.preview.data_context_ref }, { signal, timeout: 30000 }), intent);
  }
  window.TrialAdoptionAPI = { preview, adopt, lookup, source, overview, sameScope, receipt, input, check, shape, key, equal };
})();
