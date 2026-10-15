(function () {
  'use strict';
  const A = window.RunCandidateAPI, P = window.PointContract, { ref, time } = A;
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const shape = (v, keys) => object(v) && keys.length === Object.keys(v).length && keys.every(k => Object.prototype.hasOwnProperty.call(v, k));
  const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
  const finite = v => typeof v === 'number' && Number.isFinite(v), nullable = fn => v => v === null || fn(v);
  const token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  const reason = v => shape(v, ['code', 'message']) && text(v.code) && text(v.message);
  const gaps = v => Array.isArray(v) && v.every(g => shape(g, ['field', 'code', 'message']) && Object.values(g).every(text));
  const resource = v => v === null || shape(v, ['ref', 'label']) && nullable(ref)(v.ref) && nullable(text)(v.label);
  const statuses = ['matched', 'newly_scheduled', 'unscheduled', 'baseline_only', 'not_comparable'];
  const deltaKeys = ['start_hours', 'end_hours', 'elapsed_hours', 'machine_changed', 'operator_changed', 'supplier_changed', 'effective_processing_hours'];
  function check(ok) { if (!ok) throw new Error('原安排对照缺失，或者跟当前候选方案范围不一致，没有显示上次结果。请点「刷新原安排」。'); }
  function equal(a, b) {
    if (a === b) return true;
    return object(a) && object(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => equal(a[k], b[k]))
      || Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => equal(v, b[i]));
  }
  function scope(data) {
    const q = {}, t = data.time_scope;
    check(ref(data.candidate.candidate_ref) && object(t));
    if (t.range_start !== null || t.range_end !== null) { q.range_start = t.range_start; q.range_end = t.range_end; }
    if (data.batch_ref !== null) q.batch_ref = data.batch_ref;
    // A baseline read owns its own snapshot. Never accept or forward a workspace token.
    return A.workspaceScope(data.candidate.candidate_ref, q);
  }
  function resourceIdentity(side, kind) {
    const value = side[kind];
    if (value !== null) return value.ref === null ? undefined : value.ref;
    return side.data_gaps.some(gap => gap.field === kind || gap.field === kind + '.ref') ? undefined : null;
  }
  function interval(v, baseline) {
    const keys = ['row_ref', 'start', 'end', 'elapsed_hours', 'source', 'machine', 'operator', 'supplier', 'effective_processing_hours', 'data_gaps'];
    check(shape(v, keys.concat(baseline ? ['interval_comparable'] : ['locked'], P.isPoint(v) ? P.fields : [])) && ref(v.row_ref)
      && [v.start, v.end].every(nullable(time)) && nullable(finite)(v.elapsed_hours)
      && ['machine', 'operator', 'supplier'].every(k => resource(v[k])) && v.effective_processing_hours === null && gaps(v.data_gaps));
    if (baseline) check(typeof v.interval_comparable === 'boolean' && (['internal', 'external'].includes(v.source)
      || v.source === null && v.data_gaps.some(gap => gap.field === 'source')));
    else check(time(v.start) && time(v.end) && ['internal', 'external'].includes(v.source) && typeof v.locked === 'boolean');
  }
  function comparison(row, q, seen, segments, candidateRefs) {
    check(A.shape(row, ['operation_ref', 'row_ref', 'batch_ref', 'batch_label', 'part_label', 'sequence', 'process_label', 'piece_id', 'quantity', 'batch_quantity', 'due_date',
      'execution_at_generation', 'data_gaps', 'candidate', 'baseline_segments', 'selected_at_admission', 'candidate_operation_status', 'status',
      'comparison_available', 'delta', 'execution_affected', 'improvement_assessment', 'reasons'], ['process_type_ref', 'process_type_label']) && ref(row.operation_ref) && !seen.has(row.operation_ref)
      && nullable(ref)(row.batch_ref) && (!q.batch_ref || row.batch_ref === q.batch_ref) && typeof row.selected_at_admission === 'boolean'
      && typeof row.execution_affected === 'boolean' && row.improvement_assessment === null && statuses.includes(row.status)
      && ['batch_label', 'part_label', 'process_label', 'due_date'].every(k => nullable(text)(row[k])) && A.quantityContext(row, true)
      && (row.process_type_ref === undefined || nullable(ref)(row.process_type_ref))
      && (row.process_type_label === undefined || nullable(text)(row.process_type_label))
      && Array.isArray(row.reasons) && row.reasons.every(reason) && Array.isArray(row.baseline_segments));
    seen.add(row.operation_ref);
    for (const value of row.baseline_segments) { interval(value, true); check(!segments.has(value.row_ref)); segments.add(value.row_ref); }
    const c = row.candidate, b = row.baseline_segments;
    check(typeof row.comparison_available === 'boolean' && shape(row.delta, deltaKeys)
      && ['start_hours', 'end_hours', 'elapsed_hours', 'effective_processing_hours'].every(key => nullable(finite)(row.delta[key]))
      && ['machine_changed', 'operator_changed', 'supplier_changed'].every(key => row.delta[key] === null || typeof row.delta[key] === 'boolean'));
    if (c) { interval(c, false); check(row.row_ref === c.row_ref && !candidateRefs.has(c.row_ref) && row.candidate_operation_status === 'scheduled'); candidateRefs.add(c.row_ref); }
    else check(row.row_ref === null && [null, 'skipped', 'unscheduled'].includes(row.candidate_operation_status));
    const e = row.execution_at_generation;
    check(e === null || object(e) && nullable(text)(e.execution_state) && nullable(text)(e.data_quality));
    if (q.range_start && c) {
      const sides = [c].concat(b);
      check(sides.some(v => v.start === null || v.end === null || v.start === v.end && !P.isPoint(v))
        || sides.some(v => P.overlaps(v, q.range_start, q.range_end)));
    }
  }
  function validate(payload, workspace) {
    const q = scope(workspace);
    check(shape(payload, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && payload.ok === true && payload.schema_version === 1
      && shape(payload.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of']) && /^[a-f0-9]{32}$/.test(payload.meta.request_ref)
      && payload.meta.source === 'production' && payload.meta.time_basis === 'factory_local' && token(payload.meta.snapshot_ref) && time(payload.meta.as_of)
      && Array.isArray(payload.warnings) && payload.warnings.every(reason));
    const d = payload.data;
    check(shape(d, ['candidate', 'generation', 'baseline', 'comparisons', 'operation_count', 'full_operation_count', 'rows_complete', 'counts',
      'execution_affected_count', 'time_scope', 'batch_ref', 'delta_basis', 'duration_basis', 'improvement_assessment', 'capabilities', 'data_gaps'])
      && equal(d.candidate, workspace.candidate) && d.batch_ref === workspace.batch_ref && d.rows_complete === true
      && count(d.operation_count) && count(d.full_operation_count) && d.operation_count <= d.full_operation_count && d.full_operation_count <= 40000
      && Array.isArray(d.comparisons) && d.operation_count === d.comparisons.length && d.improvement_assessment === null
      && d.delta_basis === 'candidate_minus_admission_baseline' && d.duration_basis === 'elapsed_wall_clock_hours_not_effective_processing'
      && equal(d.capabilities, { view: true, adopt: false, edit_draft: false, report_actual: false, export: false })
      && Array.isArray(d.data_gaps) && d.data_gaps.every(reason));
    check(equal(d.time_scope, { range_start: q.range_start || null, range_end: q.range_end || null, interval: 'half_open_overlap',
      membership: 'either_side_overlap', counterpart_policy: 'retain_complete_counterpart', time_basis: 'factory_local',
      unplanned_policy: 'included_without_time_interval', unknown_or_zero_interval_policy: 'included_without_time_interval' }));
    if (!q.range_start && !q.batch_ref) check(d.operation_count === d.full_operation_count);
    const g = d.generation, wg = workspace.generation;
    check(shape(g, ['run_ref', 'accepted_at', 'finished_at', 'metadata_basis', 'execution_basis', 'current_entities_consulted', 'formal_version_allocated', 'input', 'source_verification'])
      && ['run_ref', 'accepted_at', 'finished_at', 'metadata_basis', 'execution_basis', 'current_entities_consulted', 'formal_version_allocated'].every(k => g[k] === wg[k])
      && g.metadata_basis === 'captured_at_run_admission' && g.execution_basis === 'captured_at_run_admission'
      && g.current_entities_consulted === false && g.formal_version_allocated === false && object(g.input)
      && Object.keys(wg.input).every(k => equal(g.input[k], wg.input[k]))
      && shape(g.source_verification, ['facts_content_verified', 'baseline_matches_archived_schedule', 'execution_verified_at',
        'input_source_verified', 'candidate_content_verified'])
      && g.source_verification.facts_content_verified === true && typeof g.source_verification.input_source_verified === 'boolean'
      && g.source_verification.baseline_matches_archived_schedule === true && g.source_verification.execution_verified_at === 'run_admission'
      && g.source_verification.candidate_content_verified === true);
    const b = d.baseline, seen = new Set(), segments = new Set(), candidateRefs = new Set();
    check(shape(b, ['baseline_ref', 'version', 'captured_at', 'kind', 'available', 'captured_task_count', 'comparison_available', 'reason'])
      && b.kind === 'admission_official' && typeof b.available === 'boolean' && count(b.captured_task_count) && b.captured_task_count <= 20000
      && b.version === wg.baseline.version && b.captured_at === wg.baseline.captured_at && b.baseline_ref === wg.baseline.baseline_ref
      && (b.available ? ref(b.baseline_ref) : b.baseline_ref === null && b.captured_task_count === 0));
    d.comparisons.forEach(row => comparison(row, q, seen, segments, candidateRefs));
    check(object(d.counts) && Object.keys(d.counts).every(key => statuses.includes(key) && count(d.counts[key]))
      && count(d.execution_affected_count) && typeof b.comparison_available === 'boolean'
      && (b.reason === null || reason(b.reason))
      && segments.size <= b.captured_task_count && [...segments].every(r => !candidateRefs.has(r)));
    if (!q.range_start && !q.batch_ref) check(segments.size === b.captured_task_count);
    const rows = new Map(d.comparisons.map(r => [r.operation_ref, r]));
    workspace.tasks.forEach(t => {
      const row = rows.get(t.operation_ref), c = row && row.candidate;
      check(c && ['row_ref', 'start', 'end', 'machine', 'operator', 'supplier', 'source', 'locked', 'data_gaps', ...P.fields].every(k => equal(c[k], t[k])));
      check(A.operationKeys.filter(k => !['execution_at_generation', 'data_gaps'].includes(k)).every(k => equal(row[k], t[k]))
        && A.executionKeys.every(k => equal(row.execution_at_generation[k], t.execution_at_generation[k])));
    });
    return d;
  }
  function create(fetcher = window.fetch.bind(window)) {
    return { async read(workspace, signal) {
      const q = scope(workspace), controller = new AbortController(), abort = () => controller.abort();
      if (signal) { if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true }); }
      const timer = setTimeout(abort, 60000);
      try {
        const response = await fetcher('/api/workbench/v1/scheduling/candidates/' + workspace.candidate.candidate_ref + '/baseline?' + new URLSearchParams(q),
          { method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal });
        const json = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json';
        const payload = json ? await response.json() : null;
        if (!response.ok) throw new Error(payload && payload.error && text(payload.error.message) ? payload.error.message : '原安排读取失败，没有显示上次结果。请点「刷新原安排」。');
        check(response.status === 200 && json); validate(payload, workspace); return payload;
      } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
    } };
  }
  window.RunBaselineAPI = { create, validate, scope, resourceIdentity };
})();
