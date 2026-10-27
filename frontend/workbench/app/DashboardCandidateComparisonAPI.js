(function () {
  'use strict';
  const C = window.DashboardContract, A = window.RunCandidateAPI, D = window.DashboardAnalysisAPI;
  const { shape, number, count, nullable } = D;
  function context(value) {
    C.check(shape(value, [], ['run_ref', 'candidate_ref', 'range_start', 'range_end', 'batch_ref']), '候选方案比较条件无效，本页内容没有变化。请重新选择排产记录和候选方案。');
    for (const key of ['run_ref', 'candidate_ref', 'batch_ref']) if (value[key] !== undefined) C.check(C.ref(value[key]));
    C.check(!value.candidate_ref || value.run_ref);
    if (value.range_start !== undefined || value.range_end !== undefined) C.check(A.time(value.range_start) && A.time(value.range_end) && value.range_start < value.range_end);
    return { ...value };
  }
  function delivery(row, available = true) {
    C.check(window.DeliveryProjectionContract.row(row, !available));
  }
  function baselineIdentity(value, generation) {
    return shape(value, ['baseline_ref', 'version', 'captured_at', 'kind', 'available', 'captured_task_count', 'comparison_available', 'reason'])
      && value.kind === 'admission_official' && A.version(value.version) && value.captured_at === generation.accepted_at
      && value.available === (value.version !== null) && count(value.captured_task_count) && typeof value.comparison_available === 'boolean'
      && (value.available ? C.ref(value.baseline_ref) : value.baseline_ref === null && value.captured_task_count === 0)
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
  function validate(payload, scope) {
    const d = payload.data;
    C.check(shape(d, ['candidate', 'generation', 'baseline', 'time_scope', 'batch_ref', 'batch_refs', 'batches', 'resources', 'summary',
      'resource_common', 'machine_changes', 'resource_scope_complete', 'resource_scope_unknown_rows', 'basis', 'capabilities', 'tradeoffs']));
    A.summary(d.candidate, scope.run_ref);
    C.check(d.candidate.candidate_ref === scope.candidate_ref, '返回的候选与所选方案不一致，请重新选择。');
    const g = d.generation;
    C.check(shape(g, ['run_ref', 'accepted_at', 'finished_at', 'metadata_basis', 'execution_basis', 'current_entities_consulted', 'formal_version_allocated', 'input'])
      && g.run_ref === d.candidate.run_ref && A.time(g.accepted_at) && (g.finished_at === null || A.time(g.finished_at))
      && g.metadata_basis === 'captured_at_run_admission' && g.execution_basis === 'captured_at_run_admission'
      && g.current_entities_consulted === false && g.formal_version_allocated === false);
    const input = g.input;
    C.check(shape(input, ['batch_refs', 'start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy'], ['material_strategy', 'hold_window', 'time_budget_seconds'])
      && Array.isArray(input.batch_refs) && input.batch_refs.every(C.ref) && new Set(input.batch_refs).size === input.batch_refs.length
      && ['start_date', 'end_date'].every(key => A.time(input[key] + 'T00:00:00')) && input.start_date <= input.end_date
      && typeof input.ready_check === 'boolean' && ['auto_assign', 'exclude'].includes(input.missing_resource_policy) && input.completed_policy === 'preserve_actuals'
      && (input.material_strategy === undefined || ['strict', 'stage'].includes(input.material_strategy))
      && (input.time_budget_seconds === undefined || window.RunGenerationContract.budget(input.time_budget_seconds)));
    const hold = input.hold_window;
    C.check(hold === undefined || hold === null || shape(hold, ['start', 'end'])
      && A.time(hold.start + ':00') && A.time(hold.end + ':00') && hold.start < hold.end);
    const expected = scope.batch_ref ? [scope.batch_ref] : input.batch_refs.slice().sort();
    C.check(baselineIdentity(d.baseline, g)
      && C.equal(d.time_scope, { range_start: scope.range_start, range_end: scope.range_end, interval: 'half_open_overlap',
        membership: 'either_side_overlap', counterpart_policy: 'retain_complete_counterpart', time_basis: 'factory_local',
        unplanned_policy: 'included_without_time_interval', unknown_or_zero_interval_policy: 'included_without_time_interval' })
      && d.batch_ref === (scope.batch_ref || null) && C.equal(d.batch_refs, expected)
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
  async function read(value, signal) {
    const scope = context(value);
    C.check(scope.candidate_ref && scope.range_start && scope.range_end, '请先选择候选并填写两个方案共同的开始和结束时间。');
    const query = { range_start: scope.range_start, range_end: scope.range_end, ...(scope.batch_ref ? { batch_ref: scope.batch_ref } : {}) };
    const payload = await C.read('/api/workbench/v1/dashboard/candidates/' + scope.candidate_ref + '/comparison', query, signal);
    validate(payload, scope); return payload;
  }
  window.DashboardCandidateComparisonAPI = { read, validate, context };
})();
