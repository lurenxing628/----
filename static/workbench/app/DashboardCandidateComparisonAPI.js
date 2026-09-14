(function () {
  'use strict';

  const C = window.DashboardContract,
    A = window.RunCandidateAPI,
    D = window.DashboardAnalysisAPI;
  const {
    shape,
    number,
    count,
    nullable
  } = D;
  function context(value = {}) {
    C.check(shape(value, [], ['run_ref', 'candidate_ref', 'range_start', 'range_end', 'batch_ref']), '候选方案比较条件无效，本页内容没有变化。请重新选择排产记录和候选方案。');
    for (const key of ['run_ref', 'candidate_ref', 'batch_ref']) if (value[key] !== undefined) C.check(C.ref(value[key]));
    C.check(!value.candidate_ref || value.run_ref);
    if (value.range_start !== undefined || value.range_end !== undefined) C.check(A.time(value.range_start) && A.time(value.range_end) && value.range_start < value.range_end);
    return {
      ...value
    };
  }
  function delivery(row) {
    C.check(C.object(row) && C.ref(row.batch_ref) && C.text(row.batch_id) && ['overdue', 'on_time', 'unknown'].includes(row.risk) && ['operation_count', 'scheduled_operation_count', 'unscheduled_operation_count', 'task_count', 'invalid_task_count'].every(k => count(row[k])) && typeof row.schedule_complete === 'boolean' && nullable(A.time)(row.planned_finish) && nullable(number)(row.delay_hours) && nullable(v => typeof v === 'boolean')(row.is_overdue) && Array.isArray(row.issues) && (row.risk === 'unknown' ? row.delay_hours === null && row.is_overdue === null : row.schedule_complete && row.planned_finish !== null && row.delay_hours !== null && row.delay_hours >= 0 && row.is_overdue === (row.risk === 'overdue')));
  }
  function summary(value, rows) {
    const unknown = rows.filter(row => row.risk === 'unknown').length,
      late = rows.filter(row => row.is_overdue === true).length;
    C.check(shape(value, ['batch_count', 'overdue_count', 'known_overdue_count', 'unknown_count', 'total_tardiness_hours', 'changeovers']) && value.batch_count === rows.length && value.unknown_count === unknown && value.known_overdue_count === late && value.overdue_count === (unknown ? null : late) && nullable(number)(value.total_tardiness_hours) && (unknown ? value.total_tardiness_hours === null : Math.abs(value.total_tardiness_hours - rows.reduce((sum, row) => sum + row.delay_hours, 0)) < 0.000001) && shape(value.changeovers, ['value', 'reason']) && nullable(count)(value.changeovers.value) && (value.changeovers.value === null ? C.text(value.changeovers.reason) : value.changeovers.reason === null));
  }
  function delta(value, first, second) {
    C.check(first === null || second === null ? value === null : number(value) && Math.abs(value - (second - first)) < 0.000001);
  }
  function validate(payload, workspace, baseline) {
    const d = D.envelope(payload),
      expected = (workspace.batch_ref ? [workspace.batch_ref] : baseline.generation.input.batch_refs).slice().sort();
    C.check(shape(d, ['candidate', 'generation', 'baseline', 'time_scope', 'batch_ref', 'batch_refs', 'capture_sha256', 'batches', 'resources', 'summary', 'machine_changes', 'resource_scope_complete', 'resource_scope_unknown_rows', 'basis', 'capabilities']) && C.equal(d.candidate, workspace.candidate) && C.equal(d.generation, baseline.generation) && C.equal(d.baseline, baseline.baseline) && C.equal(d.time_scope, baseline.time_scope) && d.batch_ref === workspace.batch_ref && C.equal(d.batch_refs, expected) && typeof d.capture_sha256 === 'string' && /^[a-f0-9]{64}$/.test(d.capture_sha256) && C.equal(d.capabilities, {
      view: true,
      adopt: false,
      edit_draft: false,
      report_actual: false
    }) && C.equal(d.basis, {
      comparison: 'candidate_minus_admission_official',
      batch_scope: 'admission_selected_batches',
      delivery: 'complete_captured_batch_operations',
      resources: 'same_range_daily_peak_available_occupancy',
      changeovers: 'same_range_scheduled_operation_type_changes',
      current_entities_consulted: false
    }) && Array.isArray(d.batches) && d.batches.length === expected.length && C.equal(d.batches.map(row => row.batch_ref).slice().sort(), expected) && Array.isArray(d.resources) && typeof d.resource_scope_complete === 'boolean' && count(d.resource_scope_unknown_rows) && d.resource_scope_complete === (d.resource_scope_unknown_rows === 0));
    d.batches.forEach(row => {
      delivery(row.before);
      delivery(row.after);
      C.check(row.batch_ref === row.before.batch_ref && row.batch_ref === row.after.batch_ref && row.batch_id === row.before.batch_id && row.batch_id === row.after.batch_id);
      delta(row.delay_delta_hours, row.before.delay_hours, row.after.delay_hours);
    });
    summary(d.summary.before, d.batches.map(row => row.before));
    summary(d.summary.after, d.batches.map(row => row.after));
    delta(d.summary.changeover_delta, d.summary.before.changeovers.value, d.summary.after.changeovers.value);
    d.resources.forEach(row => {
      C.check(C.ref(row.resource_ref));
      D.pressure(row.before);
      D.pressure(row.after);
      delta(row.delta, row.before.peak_utilization, row.after.peak_utilization);
    });
    C.check(new Set(d.resources.map(row => row.resource_ref)).size === d.resources.length);
    const changes = d.machine_changes,
      rows = baseline.comparisons.filter(row => expected.includes(row.batch_ref));
    const changed = rows.filter(row => row.delta.machine_changed === true).map(row => row.operation_ref),
      unknown = rows.filter(row => row.delta.machine_changed === null).length;
    C.check(shape(changes, ['count', 'known_count', 'unknown_count', 'operation_refs', 'basis']) && changes.known_count === changed.length && changes.unknown_count === unknown && changes.count === (unknown ? null : changed.length) && C.equal(changes.operation_refs, changed) && changes.basis === 'matched_operation_permanent_identity');
    return d;
  }
  function create(fetcher = window.fetch.bind(window)) {
    return {
      async read(workspace, baseline, signal) {
        const scope = window.RunBaselineAPI.scope(workspace);
        C.check(scope.range_start && scope.range_end, '请先填写两个方案共同的开始和结束时间。');
        const value = await D.request('/api/workbench/v1/dashboard/candidates/' + workspace.candidate.candidate_ref + '/comparison?' + new URLSearchParams(scope), fetcher, signal);
        validate(value, workspace, baseline);
        return value;
      }
    };
  }
  window.DashboardCandidateComparisonAPI = {
    create,
    validate,
    context
  };
})();
