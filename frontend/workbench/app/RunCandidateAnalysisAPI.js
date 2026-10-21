(function () {
  'use strict';
  const A = window.RunCandidateAPI, { check, ref, time, shape, envelope } = A;
  const count = v => Number.isSafeInteger(v) && v >= 0;
  const number = v => typeof v === 'number' && Number.isFinite(v);
  const text = v => typeof v === 'string' && v.length > 0;
  function equal(a, b) {
    if (a === b) return true;
    if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((v, i) => equal(v, b[i]));
    return a !== null && b !== null && typeof a === 'object' && typeof b === 'object'
      && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => equal(a[key], b[key]));
  }
  const refs = values => Array.isArray(values) && values.every(ref) && new Set(values).size === values.length;
  const reason = v => shape(v, ['code', 'message']) && text(v.code) && text(v.message);
  const keys = ['overdue_count', 'total_tardiness_hours', 'changed_operation_count', 'machine_change_count'];
  function metric(m, key) {
    const deliveryFields = keys.slice(0, 2).includes(key) ? ['state', 'due_eligible_count', 'excluded_due_count', 'invalid_due_count',
      'due_evaluation_count', 'known_due_count', 'unknown_due_count', 'known_count'] : [];
    check(shape(m, ['value', 'known_subtotal', 'unknown_count', 'total_count', 'reason', ...deliveryFields])
      && (deliveryFields.length && m.known_subtotal === null || number(m.known_subtotal) && m.known_subtotal >= 0)
      && count(m.unknown_count) && count(m.total_count)
      && m.unknown_count <= m.total_count && (m.value === null || number(m.value) && m.value >= 0)
      && (m.reason === null || reason(m.reason)) && (key === 'total_tardiness_hours' || count(m.known_subtotal))
      && (!deliveryFields.length || ['complete', 'partial', 'unavailable', 'not_applicable'].includes(m.state)
        && deliveryFields.slice(1).every(k => count(m[k]))));
  }
  function delivery(row, batch, available = true) {
    check(window.DeliveryProjectionContract.row(row, !available) && row.batch_ref === batch.batch_ref && row.batch_id === batch.batch_id);
  }
  function analysis(payload, candidateRef, runRef) {
    const d = envelope(payload);
    check(shape(d, ['candidate_ref', 'run_ref', 'baseline', 'batch_refs', 'batches', 'metrics', 'before_metrics', 'delivery_deltas', 'operations', 'basis', 'capabilities'])
      && d.candidate_ref === candidateRef && ref(d.run_ref) && (!runRef || d.run_ref === runRef)
      && refs(d.batch_refs) && Array.isArray(d.batches)
      && equal(d.batches.map(row => row.batch_ref), d.batch_refs) && shape(d.metrics, keys)
      && shape(d.before_metrics, keys.slice(0, 2)) && shape(d.delivery_deltas, keys.slice(0, 2))
      && equal(d.basis, { scope: 'full_candidate_and_full_admission_baseline', batch_scope: 'admission_selected_batches',
        operation_identity: 'permanent_operation_reference', comparison: 'candidate_minus_admission_official', current_entities_consulted: false, recommendation: null })
      && equal(d.capabilities, { view: true, adopt: false, edit_draft: false, report_actual: false }));
    const b = d.baseline;
    check(shape(b, ['baseline_ref', 'version', 'captured_at', 'kind', 'available', 'captured_task_count', 'comparison_available', 'reason'])
      && b.kind === 'admission_official' && typeof b.available === 'boolean' && count(b.captured_task_count)
      && A.version(b.version) && time(b.captured_at)
      && typeof b.comparison_available === 'boolean' && (b.available ? ref(b.baseline_ref) && b.version !== null : b.baseline_ref === null && b.version === null && b.captured_task_count === 0)
      && (b.comparison_available ? b.reason === null : reason(b.reason)));
    d.batches.forEach(row => {
      check(shape(row, ['batch_ref', 'batch_id', 'part_label', 'before', 'after', 'delay_delta_hours', 'finish_delta_hours', 'change_kinds'])
        && text(row.batch_id) && Array.isArray(row.change_kinds) && row.change_kinds.every(text)
        && [row.delay_delta_hours, row.finish_delta_hours].every(v => v === null || number(v)));
      delivery(row.before, row, b.available); delivery(row.after, row); check(row.before.due_date === row.after.due_date);
    });
    for (const key of keys.slice(0, 2)) {
      metric(d.metrics[key], key); metric(d.before_metrics[key], key);
      check(d.delivery_deltas[key] === null || number(d.delivery_deltas[key]));
    }
    const o = d.operations, lists = ['operation_refs', 'changed_operation_refs', 'machine_changed_operation_refs', 'unknown_operation_refs', 'machine_unknown_operation_refs'];
    check(shape(o, [...lists, 'issues']) && lists.every(key => refs(o[key])) && Array.isArray(o.issues));
    const all = new Set(o.operation_refs);
    const issueRefs = new Set(o.issues.map(row => row.operation_ref));
    check(lists.slice(1).every(key => o[key].every(value => all.has(value))) && issueRefs.size === o.issues.length
      && o.unknown_operation_refs.every(value => issueRefs.has(value)));
    o.issues.forEach(row => check(shape(row, ['operation_ref', 'reasons']) && all.has(row.operation_ref) && Array.isArray(row.reasons) && row.reasons.length && row.reasons.every(reason)));
    keys.slice(2).forEach(key => metric(d.metrics[key], key));
    return d;
  }
  function history(payload, candidateRef, runRef) {
    const d = envelope(payload);
    check(shape(d, ['candidate_ref', 'run_ref', 'items', 'total', 'state', 'basis']) && d.candidate_ref === candidateRef
      && ref(d.run_ref) && (!runRef || d.run_ref === runRef) && Array.isArray(d.items) && d.total === d.items.length
      && d.state === (d.total ? 'available' : 'empty') && d.basis === 'original_candidate_receipts_and_official_adoption_audits');
    d.items.forEach(row => {
      check(shape(row, ['receipt_ref', 'request_key', 'candidate_ref', 'run_ref', 'committed_at_utc', 'row_count', 'official_plan', 'adoption', 'can_open', 'evidence_gaps'])
        && /^[a-f0-9]{32}$/.test(row.receipt_ref) && text(row.request_key) && row.candidate_ref === candidateRef && row.run_ref === d.run_ref
        && text(row.committed_at_utc) && /Z$/.test(row.committed_at_utc) && Number.isFinite(Date.parse(row.committed_at_utc)) && count(row.row_count) && row.row_count > 0
        && shape(row.official_plan, ['plan_ref', 'version', 'label']) && ref(row.official_plan.plan_ref) && count(row.official_plan.version) && row.official_plan.version > 0
        && row.official_plan.label === '正式计划 v' + row.official_plan.version && Array.isArray(row.evidence_gaps) && row.evidence_gaps.every(reason)
        && row.can_open === (row.evidence_gaps.length === 0));
      if (row.adoption === null) check(!row.can_open);
      else check(shape(row.adoption, ['reason', 'declared_operator', 'application_operator', 'adopted_at', 'baseline_ref', 'baseline_version'])
        && ['reason', 'declared_operator', 'application_operator'].every(key => text(row.adoption[key])) && time(row.adoption.adopted_at)
        && (row.adoption.baseline_ref === null ? row.adoption.baseline_version === null : ref(row.adoption.baseline_ref) && count(row.adoption.baseline_version)));
    });
    check(new Set(d.items.map(row => row.receipt_ref)).size === d.total && new Set(d.items.map(row => row.official_plan.plan_ref)).size === d.total);
    return d;
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function read(candidateRef, runRef, leaf, validate, signal) {
      check(ref(candidateRef) && (!runRef || ref(runRef)));
      const controller = new AbortController(), abort = () => controller.abort();
      if (signal) { if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true }); }
      const timer = setTimeout(abort, 60000);
      try {
        const response = await fetcher('/api/workbench/v1/scheduling/candidates/' + candidateRef + '/' + leaf,
          { method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal });
        const json = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json';
        const value = json ? await response.json() : null;
        if (!response.ok) {
          const error = value && value.error;
          throw Object.assign(new Error(error && text(error.message) ? error.message : '候选方案资料读取失败，请刷新后重试。'), { code: error && error.code || 'invalid_response', status: response.status });
        }
        check(response.status === 200 && json); validate(value, candidateRef, runRef); return value;
      } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
    }
    return window.APSReadBoundary.verified({ ...A.create(fetcher), analysis: (candidateRef, runRef, signal) => read(candidateRef, runRef, 'analysis', analysis, signal),
      adoptions: (candidateRef, runRef, signal) => read(candidateRef, runRef, 'adoptions', history, signal) }, ['analysis', 'adoptions']);
  }
  function adapter(value) {
    return window.APSReadBoundary.checked(A.adapter(value), { analysis, adoptions: history });
  }
  window.RunCandidateAnalysisAPI = { create, adapter, analysis, history };
})();
