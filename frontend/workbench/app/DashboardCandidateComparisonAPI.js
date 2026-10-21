(function () {
  'use strict';
  const C = window.DashboardContract, A = window.RunCandidateAPI, D = window.DashboardAnalysisAPI;
  const { shape, number, count, nullable } = D;
  function context(value = {}) {
    C.check(shape(value, [], ['run_ref', 'candidate_ref', 'range_start', 'range_end', 'batch_ref']), '候选方案比较条件无效，本页内容没有变化。请重新选择排产记录和候选方案。');
    for (const key of ['run_ref', 'candidate_ref', 'batch_ref']) if (value[key] !== undefined) C.check(C.ref(value[key]));
    C.check(!value.candidate_ref || value.run_ref);
    if (value.range_start !== undefined || value.range_end !== undefined) C.check(A.time(value.range_start) && A.time(value.range_end) && value.range_start < value.range_end);
    return { ...value };
  }
  function delivery(row, available = true) {
    C.check(window.DeliveryProjectionContract.row(row, !available));
  }
  function baselineIdentity(value, expected) {
    return shape(value, ['baseline_ref', 'version', 'captured_at', 'kind', 'available', 'captured_task_count', 'comparison_available', 'reason'])
      && ['baseline_ref', 'version', 'captured_at', 'kind'].every(key => C.equal(value[key], expected[key]))
      && typeof value.available === 'boolean' && count(value.captured_task_count) && typeof value.comparison_available === 'boolean'
      && (value.reason === null || C.object(value.reason) && C.text(value.reason.code) && C.text(value.reason.message));
  }
  function summary(value, batchCount) {
    C.check(window.DeliveryProjectionContract.summary(value) && value.batch_count === batchCount
      && shape(value.changeovers, ['value', 'reason']) && nullable(count)(value.changeovers.value)
      && (value.changeovers.value === null ? C.text(value.changeovers.reason) : value.changeovers.reason === null));
  }
  function delta(value) { C.check(value === null || number(value)); }
  function tradeoffs(value, data) {
    C.check(shape(value, ['recommendation_version', 'scope', 'benefits', 'costs', 'all_differences'])
      && value.recommendation_version === 'decision-recommendation-v1' && value.scope === 'admission_selected_batches'
      && ['benefits', 'costs', 'all_differences'].every(key => Array.isArray(value[key]))
      && value.benefits.length <= 3 && value.costs.length <= 3);
    value.all_differences.forEach(item => {
      C.check(window.RecommendationContract.entry(item) && item.metric_version === (item.source === 'archived_resource_calendar' ? data.resource_common.metric_version : 'decision-preparation-v4'), '所选候选的取舍资料缺项，请刷新。');
      item.supporting_refs.forEach(target => {
        const drill = target.drill;
        C.check(target.candidate_ref === data.candidate.candidate_ref && drill.candidate_ref === data.candidate.candidate_ref
          && drill.selected_candidate_ref === data.candidate.candidate_ref && drill.reference_candidate_ref === null
          && drill.run_ref === data.generation.run_ref && drill.comparison_mode === 'admission_official'
          && (drill.resource_view === undefined || drill.resource_view === 'selected_batches'), '取舍支撑与当前所选候选不一致，请刷新。');
        ['range_start', 'range_end'].forEach(key => C.check(drill[key] === undefined || drill[key] === data.time_scope[key], '取舍支撑的比较时间窗已变化，请刷新。'));
      });
      C.check(item.sample_compared_batch_refs.every(ref => data.batch_refs.includes(ref)), '取舍的共同完成批次超出当前比较范围，请刷新。');
    });
    ['benefits', 'costs'].forEach((key, index) => C.check(value[key].every(item =>
      item.direction === (index ? 'worse' : 'better') && value.all_differences.some(entry => C.equal(entry, item))), '主要取舍与完整差值不一致，请刷新。'));
  }
  function validate(payload, workspace, baseline) {
    const d = D.envelope(payload), expected = (workspace.batch_ref ? [workspace.batch_ref] : baseline.generation.input.batch_refs).slice().sort();
    C.check(shape(d, ['candidate', 'generation', 'baseline', 'time_scope', 'batch_ref', 'batch_refs', 'batches', 'resources', 'summary',
      'resource_common', 'machine_changes', 'resource_scope_complete', 'resource_scope_unknown_rows', 'basis', 'capabilities', 'tradeoffs'])
      && C.equal(d.candidate, workspace.candidate) && C.equal(d.generation, baseline.generation) && baselineIdentity(d.baseline, baseline.baseline)
      && C.equal(d.time_scope, baseline.time_scope) && d.batch_ref === workspace.batch_ref && C.equal(d.batch_refs, expected)
      && C.equal(d.capabilities, { view: true, adopt: false, edit_draft: false, report_actual: false })
      && C.equal(d.basis, { comparison: 'candidate_minus_admission_official', batch_scope: 'admission_selected_batches',
        delivery: 'complete_captured_batch_operations', resources: 'same_range_daily_peak_available_occupancy',
        changeovers: 'same_range_scheduled_operation_type_changes', current_entities_consulted: false })
      && Array.isArray(d.batches) && d.batches.length === expected.length && C.equal(d.batches.map(row => row.batch_ref).sort(), expected)
      && Array.isArray(d.resources) && typeof d.resource_scope_complete === 'boolean' && count(d.resource_scope_unknown_rows)
      && d.resource_scope_complete === (d.resource_scope_unknown_rows === 0));
    d.batches.forEach(row => { delivery(row.before, d.baseline.available); delivery(row.after); C.check(row.batch_ref === row.before.batch_ref && row.batch_ref === row.after.batch_ref
      && row.batch_id === row.before.batch_id && row.batch_id === row.after.batch_id && Array.isArray(row.change_kinds));
      delta(row.delay_delta_hours); delta(row.finish_delta_hours); });
    summary(d.summary.before, d.batches.length); summary(d.summary.after, d.batches.length);
    delta(d.summary.changeover_delta);
    d.resources.forEach(row => { C.check(C.ref(row.resource_ref) && ['machine', 'operator'].includes(row.kind)); D.pressure(row.before); D.pressure(row.after); delta(row.delta); });
    C.check(new Set(d.resources.map(row => row.resource_ref)).size === d.resources.length
      && window.ResourceProjectionContract.common(d.resource_common, 'archived_resource_calendar')
      && C.equal(d.resource_common.batch_refs, d.batch_refs) && d.resource_common.resource_view === 'selected_batches');
    const changes = d.machine_changes;
    C.check(shape(changes, ['count', 'known_count', 'unknown_count', 'operation_refs', 'basis']) && count(changes.known_count)
      && count(changes.unknown_count) && nullable(count)(changes.count) && Array.isArray(changes.operation_refs) && changes.operation_refs.every(C.ref)
      && changes.basis === 'matched_operation_permanent_identity');
    tradeoffs(d.tradeoffs, d);
    return d;
  }
  function create(fetcher = window.fetch.bind(window)) {
    return { async read(workspace, baseline, signal) {
      const scope = window.RunBaselineAPI.scope(workspace);
      C.check(scope.range_start && scope.range_end, '请先填写两个方案共同的开始和结束时间。');
      const value = await D.request('/api/workbench/v1/dashboard/candidates/' + workspace.candidate.candidate_ref + '/comparison?' + new URLSearchParams(scope), fetcher, signal);
      validate(value, workspace, baseline); return value;
    } };
  }
  window.DashboardCandidateComparisonAPI = { create, validate, context };
})();
