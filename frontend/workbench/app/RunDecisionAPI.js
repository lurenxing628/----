(function () {
  'use strict';
  const A = window.RunCandidateAPI, G = window.RunGenerationContract, T = window.APSWorkbenchTransport, { check, ref, time, timeKey } = A;
  const queryKeys = ['selected_candidate_ref', 'reference_candidate_ref', 'comparison_mode', 'resource_view', 'range_start', 'range_end', 'snapshot_ref'];
  function bindSnapshot(payload, query) {
    if (query.snapshot_ref) check(payload.meta.snapshot_ref === query.snapshot_ref, '比较资料已更新，请刷新后重试。');
  }
  function bindScope(payload, data, query) {
    bindSnapshot(payload, query);
    check(data.scope.resource_view === query.resource_view, '资源统计范围已变化，请刷新。');
    for (const key of ['range_start', 'range_end']) if (query[key])
      check(time(data.scope[key]) && timeKey(data.scope[key]) === timeKey(query[key]), '比较时间范围已变化，请刷新。');
    if (query.comparison_mode === 'admission_official')
      check(data.scope.reference && data.scope.reference.kind === 'admission_official' && data.baseline && data.baseline.kind === 'admission_official'
        && data.baseline.baseline_ref === data.scope.reference.baseline_ref && data.baseline.state === data.scope.reference_state,
      '比较基准的正式计划资料已变化，请刷新。');
  }
  // 各 *Scope 只保留填了值的筛选（空串、null、undefined 都不进 q）；后端把未填的筛选回显为 null，比较时用 `?? null` 对齐。
  function scope(runRef, query) {
    check(ref(runRef), '请从排产记录打开方案对比。');
    const value = { comparison_mode: 'candidates', resource_view: 'selected_batches' };
    queryKeys.forEach(key => { if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key]; });
    check(['candidates', 'admission_official'].includes(value.comparison_mode), '请选择本次排产的方案或排产时的正式计划进行比较。');
    check(['selected_batches', 'full_candidate'].includes(value.resource_view), '请选择资源统计范围。');
    check(value.comparison_mode !== 'admission_official' || value.reference_candidate_ref === undefined, '比较方式与比较基准不匹配，请从排产记录重新打开方案对比。');
    ['selected_candidate_ref', 'reference_candidate_ref'].forEach(key => check(value[key] === undefined || ref(value[key]), '方案选择已失效，请重新选择。'));
    if (value.range_start !== undefined || value.range_end !== undefined)
      check(time(value.range_start) && time(value.range_end) && value.range_start < value.range_end, '请同时填写开始和结束时间，结束须晚于开始。');
    return value;
  }
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const numeric = value => value === null || typeof value === 'number' && Number.isFinite(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const issue = value => object(value) && typeof value.code === 'string' && typeof value.message === 'string';
  const coreMetricKeys = ['expected_operation_count', 'scheduled_operation_count', 'unplanned_operation_count', 'deferred_operation_count',
    'overdue_count', 'total_tardiness_hours', 'makespan_hours', 'weighted_tardiness_hours', 'elapsed_seconds', 'changeover_count',
    'machine_used_count', 'operator_used_count', 'machine_busy_hours_total', 'operator_busy_hours_total', 'machine_util_avg', 'operator_util_avg'];
  function tradeoff(item, data, candidateRef) {
    check(window.RecommendationContract.entry(item), '推荐方案的对比资料不完整，请点“刷新方案对比”。');
    const definition = data.metric_definitions.find(row => row.key === item.metric_key);
    check(definition && item.unit === definition.unit && item.precision === definition.precision
      && item.metric_version === definition.metric_version, '推荐方案的对比资料不完整，请点“刷新方案对比”。');
    item.supporting_refs.forEach(target => {
      check(target.candidate_ref === candidateRef, '推荐理由对应的方案已变化，请点“刷新方案对比”。');
      recommendationDrill(target.drill, data, candidateRef, target.side || 'selected', target.kind);
    });
  }
  function recommendationDrill(context, data, candidateRef, side = 'selected', kind) {
    const referenceSide = side === 'reference', formalReference = referenceSide && data.scope.comparison_mode === 'admission_official';
    const actualRef = referenceSide && !formalReference ? data.scope.reference.candidate_ref : candidateRef;
    check(object(context) && context.run_ref === (data.run ? data.run.run_ref : data.run_ref) && context.candidate_ref === actualRef
      && (context.selected_candidate_ref === undefined || context.selected_candidate_ref === candidateRef)
      && context.comparison_mode === data.scope.comparison_mode
      && (context.resource_view === undefined || context.resource_view === data.scope.resource_view), '推荐理由的甘特位置或比较范围已变化，请点“刷新方案对比”。');
    check(referenceSide ? kind === 'operation' && data.scope.reference_state === 'available' && context.comparison_tab === undefined
      && (formalReference ? context.reference_view === true && context.plan_ref === data.scope.reference.baseline_ref : context.reference_view !== true && context.plan_ref === undefined)
      : context.reference_view !== true && context.plan_ref === undefined, '推荐理由对应的方案或正式计划已变化，请点“刷新方案对比”。');
    if (context.comparison_mode === 'candidates' && data.scope.reference_state === 'available') check(context.reference_candidate_ref === data.scope.reference.candidate_ref, '推荐理由的比较基准已变化，请点“刷新方案对比”。');
    if (context.comparison_tab === undefined) check(ref(context.operation_ref) && time(context.range_start) && time(context.range_end)
      && timeKey(context.range_start) <= timeKey(data.scope.range_start) && timeKey(context.range_end) >= timeKey(data.scope.range_end)
      && (timeKey(context.range_start) === timeKey(data.scope.range_start) && timeKey(context.range_end) === timeKey(data.scope.range_end) || context.drill_range_adjusted === true), '推荐理由的工序位置资料不完整，请点“刷新方案对比”。');
    else for (const key of ['range_start', 'range_end']) if (context[key] !== undefined)
      check(time(context[key]) && timeKey(context[key]) === timeKey(data.scope[key]), '推荐理由的比较时间范围已变化，请点“刷新方案对比”。');
    if (context.comparison_tab !== undefined) check(['batches', 'operations', 'resources', 'preparation', 'changeovers'].includes(context.comparison_tab)
      && object(context.detail_query), '推荐理由的明细资料不完整，请点“刷新方案对比”。');
  }

  const completionBatchCounts = ['complete_batch_count', 'incomplete_batch_count', 'ordinary_incomplete_batch_count', 'deferred_batch_count', 'unknown_batch_count'];
  function completion(value) {
    return object(value) && value.scope === 'full_admission' && ['complete', 'partial', 'unavailable', 'not_applicable'].includes(value.state)
      && value.source_available === true && completionBatchCounts.every(key => count(value[key]))
      && ['unplanned_operation_count', 'deferred_operation_count'].every(key => count(value[key]))
      && object(value.sample_batch_refs) && ['complete', 'incomplete', 'deferred', 'unknown'].every(key => Array.isArray(value.sample_batch_refs[key]) && value.sample_batch_refs[key].length <= 3 && value.sample_batch_refs[key].every(ref))
      && object(value.remaining_work) && object(value.remaining_work.metrics)
      && preparationMetrics.every(key => window.EffortProjectionContract.metric(value.remaining_work.metrics[key]))
      && ['operation_count', 'unplanned_operation_count', 'deferred_operation_count'].every(key => count(value.remaining_work[key]));
  }
  function recommendation(data) {
    const value = data.recommendation, basis = data.selection_basis, comparison = value && value.current_comparison;
    // 推荐只按业务方向选择（business_objectives_v1）；选择依据的编号、评分与空的旧证据位都由 selectionBasis 一次核对。
    check(G.selectionBasis(basis, data.candidates), '保存的共同优化选择资料不完整，请点“刷新方案对比”。');
    check(object(value) && value.recommendation_version === 'decision-recommendation-v1' && ['available', 'unavailable'].includes(value.state)
      && value.candidate_ref === basis.selected_candidate_ref && (value.state === 'available' ? ref(value.candidate_ref) : value.candidate_ref === null)
      && value.viewed_candidate_ref === data.scope.selected_candidate_ref
      && typeof value.headline === 'string' && (value.state === 'available' ? ['complete', 'schedulable_scope', 'partial'].includes(value.recommendation_type) : value.recommendation_type === null),
    '推荐方案或推荐理由已变化，请点“刷新方案对比”。');
    check(object(basis.explanation) && typeof basis.explanation.headline === 'string' && Array.isArray(basis.explanation.entries)
      && basis.explanation.entries.every(entry => A.shape(entry, ['key', 'label', 'text', 'state', 'unit', 'selected_value', 'source', 'scope'])
        && ['key', 'label', 'text', 'state', 'source', 'scope'].every(key => typeof entry[key] === 'string')
        && (entry.unit === null || typeof entry.unit === 'string') && numeric(entry.selected_value))
      && Array.isArray(basis.explanation.issues) && basis.explanation.issues.every(issue), '推荐理由资料不完整，请点“刷新方案对比”。');
    check(object(value.axes) && object(value.axes.algorithm) && value.axes.algorithm.state === (value.state === 'available' ? 'selected' : 'unavailable')
      && value.axes.algorithm.reason_code === basis.reason_code && value.axes.algorithm.evidence_state === basis.evidence_state
      && object(value.axes.completion) && object(value.axes.preflight) && value.axes.preflight.state === 'not_checked' && value.axes.preflight.source === 'existing_adoption_preview'
      && (value.state === 'available' ? completion(value.completion_scope) && object(value.axes.completion.search) && object(value.axes.completion.schedulable)
        && completion(value.axes.completion.delivery) : value.completion_scope === null), '推荐方案的工序安排或采用检查资料不完整，请点“刷新方案对比”。');
    check(object(comparison) && comparison.candidate_ref === value.candidate_ref && comparison.viewed_candidate_ref === data.scope.selected_candidate_ref
      && ['available', 'unavailable', 'absent', 'selection_required'].includes(comparison.state) && object(comparison.reference)
      && comparison.reference.kind === data.scope.reference.kind
      && (data.scope.comparison_mode === 'candidates' ? comparison.reference.candidate_ref === data.scope.reference.candidate_ref : comparison.reference.baseline_ref === data.scope.reference.baseline_ref)
      && ['benefits', 'costs', 'all_differences'].every(key => Array.isArray(comparison[key])) && comparison.benefits.length <= 3 && comparison.costs.length <= 3,
    '推荐方案与当前查看方案或比较基准不一致，请点“刷新方案对比”。');
    if (value.state === 'available') recommendationDrill(value.completion_scope.drill, data, value.candidate_ref);
    check(comparison.all_differences.length === (value.state === 'available' ? data.metric_definitions.length : 0), '推荐方案的指标对比资料不完整，请点“刷新方案对比”。');
    const all = new Map();
    comparison.all_differences.forEach(item => { tradeoff(item, data, value.candidate_ref); check(!all.has(item.metric_key), '推荐方案的对比结果重复，请点“刷新方案对比”。'); all.set(item.metric_key, item); });
    for (const [key, direction] of [['benefits', 'better'], ['costs', 'worse']]) comparison[key].forEach(item => {
      tradeoff(item, data, value.candidate_ref); const full = all.get(item.metric_key);
      check(full && item.direction === direction && ['value', 'reference_value', 'selected_value', 'state', 'direction', 'text'].every(field => item[field] === full[field]), '推荐方案的收益和代价与对比结果不一致，请点“刷新方案对比”。');
    });
    const common = comparison.common_completed_delivery;
    check(common === null || object(common) && common.scope === 'common_completed_batches' && ['complete', 'partial', 'unavailable', 'not_applicable'].includes(common.state)
      && count(common.batch_count) && Array.isArray(common.sample_batch_refs) && common.sample_batch_refs.length <= 3 && common.sample_batch_refs.every(ref)
      && object(common.before) && object(common.after) && numeric(common.delay_delta_hours) && numeric(common.overdue_delta_count), '推荐方案的批次交付对比资料不完整，请点“刷新方案对比”。');
  }
  function completionGroups(data) {
    check(Array.isArray(data.completion_groups) && data.completion_groups.every(group => object(group) && count(group.group_index) && group.source_available === true
      && count(group.complete_batch_count) && Array.isArray(group.sample_complete_batch_refs) && group.sample_complete_batch_refs.length <= 3 && group.sample_complete_batch_refs.every(ref)
      && Array.isArray(group.candidate_refs) && group.candidate_refs.every(ref)), '方案的批次安排分类资料不完整，请点“刷新方案对比”。');
    const grouped = data.completion_groups.flatMap(group => group.candidate_refs);
    check(grouped.length === data.candidates.length && new Set(grouped).size === grouped.length && data.candidates.every(row => grouped.includes(row.candidate_ref)), '批次安排分类与本次排产方案不一致，请点“刷新方案对比”。');
  }
  function decisionCore(payload, runRef, query) {
    const data = payload.data, q = scope(runRef, query);
    check(data.run && data.run.run_ref === runRef && data.scope && data.scope.run_ref === runRef
      && data.scope.comparison_mode === q.comparison_mode && Array.isArray(data.candidates) && Array.isArray(data.metric_definitions), '比较资料与当前排产记录不一致，请点“刷新方案对比”。');
    check(data.metric_definitions.every(metric => object(metric) && typeof metric.key === 'string' && typeof metric.metric_version === 'string')
      && new Set(data.metric_definitions.map(metric => metric.key)).size === data.metric_definitions.length
      && coreMetricKeys.every(key => data.metric_definitions.some(metric => metric.key === key)), '方案核心指标目录不完整，请点“刷新方案对比”。');
    const candidates = new Set();
    data.candidates.forEach(row => {
      check(ref(row.candidate_ref) && !candidates.has(row.candidate_ref) && object(row.coverage)
        && ['schedulable', 'delivery', 'search'].every(key => object(row.coverage[key])) && row.metrics && row.deltas && Array.isArray(row.selection_role), '方案的比较资料不完整，请点“刷新方案对比”。');
      candidates.add(row.candidate_ref);
      // 候选只由共同优化按业务方向生成（unified_search_v1）。
      check(A.shape(row, ['candidate_ref', 'label', 'kind', 'status', 'persisted_status', 'task_count', 'completeness', 'coverage', 'metrics',
        'capabilities', 'selection_role', 'deltas'].concat(G.metadataKeys))
        && G.metadata(row, runRef) && row.kind === 'business_objective' && row.persisted_status === 'completed'
        && ['completed', 'partial'].includes(row.status)
        && new Set(row.selection_role).size === row.selection_role.length
        && row.selection_role.every(role => role === 'recommended' || G.objective(role)), '业务方向候选的保存资料不完整，请点“刷新方案对比”。');
      coreMetricKeys.forEach(key => {
        const metric = data.metric_definitions.find(definition => definition.key === key);
        check(metric && window.EffortProjectionContract.metric(row.metrics[key]) && row.metrics[key].metric_version === metric.metric_version
          && window.EffortProjectionContract.delta(row.deltas[key]), '方案核心指标资料不完整，请点“刷新方案对比”。');
      });
    });
    check(data.scope.selected_candidate_ref === null || candidates.has(data.scope.selected_candidate_ref), '当前查看方案已不在这次排产中，请点“刷新方案对比”。');
    if (q.selected_candidate_ref) check(data.scope.selected_candidate_ref === q.selected_candidate_ref, '当前查看方案已变化，请点“刷新方案对比”。');
    if (q.comparison_mode === 'candidates' && data.scope.reference_state === 'available') check(data.scope.reference && candidates.has(data.scope.reference.candidate_ref), '比较基准已不在这次排产中，请点“刷新方案对比”。');
    if (q.comparison_mode === 'candidates' && q.reference_candidate_ref) check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '比较基准已变化，请点“刷新方案对比”。');
    if (q.comparison_mode === 'admission_official') check(data.scope.reference && data.scope.reference.kind === 'admission_official', '比较基准的正式计划资料已变化，请点“刷新方案对比”。');
    check(G.runOptions(data.scope.run_options), '本次保存的优化选项不完整，请点“刷新方案对比”。');
    bindScope(payload, data, q);
    recommendation(data);
    if (data.difference_summary !== undefined) {
      const keys = ['overdue_count', 'total_tardiness_hours', 'makespan_hours'];
      check(data.difference_summary && data.difference_summary.scope === 'full_admission'
        && Array.isArray(data.difference_summary.items) && data.difference_summary.items.length === keys.length
        && data.difference_summary.items.every((item, index) => item.key === keys[index]
          && data.metric_definitions.some(definition => definition.key === item.key && definition.unit === item.unit && definition.scope === item.scope)
          && [item.value, item.reference_value, item.selected_value].every(numeric)
          && ['comparable', 'unavailable', 'different_coverage'].includes(item.state)
          && ['better', 'worse', 'equal', 'neutral'].includes(item.direction)
          && object(item.reference_coverage) && object(item.selected_coverage)),
      '方案差异摘要的指标或统计范围不完整，请点“刷新方案对比”。');
    }
    return data;
  }
  function validateDecision(payload, runRef, query) {
    const data = decisionCore(payload, runRef, query);
    const extraMetrics = data.metric_definitions.filter(metric => !coreMetricKeys.includes(metric.key));
    data.candidates.forEach(row => extraMetrics.forEach(metric => check(window.EffortProjectionContract.metric(row.metrics[metric.key])
      && row.metrics[metric.key].metric_version === metric.metric_version && window.EffortProjectionContract.delta(row.deltas[metric.key]), '比较指标资料不完整，请点“刷新方案对比”。')));
    completionGroups(data);
    return data;
  }
  function validateDecisionSummary(payload, runRef, query) {
    const data = decisionCore(payload, runRef, query), exactCore = value => object(value)
      && Object.keys(value).length === coreMetricKeys.length && coreMetricKeys.every(key => Object.prototype.hasOwnProperty.call(value, key));
    const baseline = data.baseline, missingCandidateBaseline = data.scope.comparison_mode === 'candidates' && data.scope.reference_state === 'selection_required';
    check(data.completion_groups === undefined && data.candidates.every(row => exactCore(row.metrics) && exactCore(row.deltas)
        && Object.keys(row.coverage).length === 3)
      && baseline && object(baseline.coverage) && baseline.state === data.scope.reference_state
      && (missingCandidateBaseline ? object(baseline.metrics) && Object.keys(baseline.metrics).length === 0 && baseline.candidate_ref === null
        && Object.keys(baseline.coverage).length === 1 && baseline.coverage.schedulable && baseline.coverage.schedulable.state === 'unavailable'
        : Object.keys(baseline.coverage).length === 2 && ['schedulable', 'delivery'].every(key => object(baseline.coverage[key]))
          && (data.scope.comparison_mode !== 'candidates' || baseline.candidate_ref === data.scope.reference.candidate_ref)
          && exactCore(baseline.metrics) && coreMetricKeys.every(key => window.EffortProjectionContract.metric(baseline.metrics[key])
          && baseline.metrics[key].metric_version === data.metric_definitions.find(metric => metric.key === key).metric_version))
      && data.difference_summary !== undefined, '方案首屏指标或基准资料不完整，请点“刷新方案对比”。');
    return data;
  }
  const completionFilters = ['all', 'complete', 'unfinished', 'ordinary', 'deferred', 'unknown'];
  function completionScope(runRef, query) {
    const value = { ...scope(runRef, query), completion_filter: 'all', sort: 'batch_id', order: 'asc', page: 1, size: 20 };
    ['completion_filter', 'sort', 'order', 'page', 'size'].forEach(key => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
    });
    check(ref(value.selected_candidate_ref), '请选择要查看批次安排的方案。');
    check(completionFilters.includes(value.completion_filter) && value.sort === 'batch_id' && ['asc', 'desc'].includes(value.order), '批次安排的筛选或排序条件无效，请重新选择。');
    check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '批次清单每页支持 20 或 50 条，请重新选择页码。');
    return value;
  }
  function validateCompletionBatches(payload, runRef, query) {
    const data = payload.data, q = completionScope(runRef, query), E = window.EffortProjectionContract;
    check(A.shape(data, ['run_ref', 'scope', 'baseline', 'candidate', 'source', 'filters', 'items', 'page', 'summary', 'metric_version'])
      && data.run_ref === runRef && object(data.scope) && data.scope.run_ref === runRef
      && data.scope.selected_candidate_ref === q.selected_candidate_ref && data.scope.comparison_mode === q.comparison_mode
      && time(data.scope.range_start) && time(data.scope.range_end) && timeKey(data.scope.range_start) < timeKey(data.scope.range_end)
      && Array.isArray(data.scope.batch_refs) && data.scope.batch_refs.every(ref) && object(data.scope.reference)
      && object(data.baseline) && data.baseline.kind === data.scope.reference.kind && data.baseline.state === data.scope.reference_state
      && A.shape(data.candidate, ['candidate_ref', 'label', 'persisted_status']) && data.candidate.candidate_ref === q.selected_candidate_ref
      && (data.candidate.label === null || typeof data.candidate.label === 'string') && data.candidate.persisted_status === 'completed'
      && data.metric_version === 'decision-preparation-v4', '批次安排资料与当前方案或比较范围不一致，请刷新批次清单。');
    if (q.comparison_mode === 'candidates') check(data.scope.reference.kind === 'candidate'
      && data.baseline.candidate_ref === data.scope.reference.candidate_ref
      && (data.scope.reference_state === 'available' ? ref(data.scope.reference.candidate_ref) : data.scope.reference_state === 'selection_required' && data.scope.reference.candidate_ref === null)
      && (!q.reference_candidate_ref || data.scope.reference.candidate_ref === q.reference_candidate_ref), '批次安排的比较基准已变化，请刷新批次清单。');
    else check(data.scope.reference.kind === 'admission_official'
      && (data.scope.reference_state === 'available' ? ref(data.scope.reference.baseline_ref) : data.scope.reference_state === 'absent' && data.scope.reference.baseline_ref === null), '批次安排使用的正式计划资料已变化，请刷新批次清单。');
    bindScope(payload, data, q);
    const source = data.source;
    check(A.shape(source, ['role', 'grain', 'candidate_ref', 'available', 'reason']) && source.role === 'completion_anchor'
      && source.grain === 'full_admission_per_candidate_batch' && source.candidate_ref === q.selected_candidate_ref && source.available === true
      && source.reason === null, '所选方案的批次安排资料不完整，请刷新批次清单。');
    check(A.shape(data.filters, ['section', 'completion_filter', 'sort', 'order'])
      && data.filters.section === 'completion-batches' && ['completion_filter', 'sort', 'order'].every(key => data.filters[key] === q[key]),
    '批次清单的方案、筛选或排序已变化，请刷新批次清单。');
    check(completion(data.summary), '批次安排和待安排工时资料不完整，请刷新批次清单。');
    const cohort = new Set(data.scope.batch_refs);
    check(Object.values(data.summary.sample_batch_refs).every(values => values.every(value => cohort.has(value))), '批次清单与本次选择的批次不一致，请刷新批次清单。');
    const totalKey = { complete: 'complete_batch_count', unfinished: 'incomplete_batch_count', ordinary: 'ordinary_incomplete_batch_count', deferred: 'deferred_batch_count', unknown: 'unknown_batch_count' }[q.completion_filter];
    const total = totalKey ? data.summary[totalKey] : cohort.size;
    check(A.shape(data.page, ['number', 'size', 'total', 'has_more']) && data.page.number === q.page && data.page.size === q.size
      && count(data.page.total) && data.page.total === total && data.page.has_more === (q.page * q.size < total)
      && Array.isArray(data.items) && data.items.length === Math.min(q.size, Math.max(0, total - (q.page - 1) * q.size)),
    '批次清单的记录条数或页码已变化，请刷新批次清单。');
    function remainingDrill(value, operationCount, batchRef) {
      if (operationCount === 0) { check(value === null, '待安排工序的定位资料已失效，请刷新批次清单。'); return; }
      check(object(value) && value.comparison_tab === 'preparation' && value.selected_candidate_ref === q.selected_candidate_ref
        && A.shape(value.detail_query, ['work_scope'], batchRef ? ['batch_ref'] : []) && value.detail_query.work_scope === 'remaining'
        && (batchRef ? value.detail_query.batch_ref === batchRef : value.detail_query.batch_ref === undefined), '待安排工序的方案、批次或范围已变化，请刷新批次清单。');
      recommendationDrill(value, data, q.selected_candidate_ref);
      check(['range_start', 'range_end'].every(key => time(value[key]) && timeKey(value[key]) === timeKey(data.scope[key])), '待安排工序的比较时间范围已变化，请刷新批次清单。');
    }
    remainingDrill(data.summary.drill, data.summary.remaining_work.operation_count);
    check(data.summary.remaining_work.operation_count === data.summary.unplanned_operation_count + data.summary.deferred_operation_count
      && ['unplanned_operation_count', 'deferred_operation_count'].every(key => data.summary.remaining_work[key] === data.summary[key]),
    '所选方案的待安排工序资料不完整，请刷新批次清单。');
    data.items.forEach(row => {
      check(A.shape(row, ['batch_ref', 'batch_label', 'part_no', 'part_label', 'quantity', 'completion_state', 'schedule_complete', 'scheduled_operation_count',
        'unplanned_operation_count', 'deferred_operation_count', 'remaining_work', 'issues', 'remaining_drill'])
        && ref(row.batch_ref) && cohort.has(row.batch_ref) && ['batch_label', 'part_no', 'part_label'].every(key => row[key] === null || typeof row[key] === 'string')
        && (row.quantity === null || typeof row.quantity === 'number' && Number.isFinite(row.quantity) && row.quantity >= 0)
        && ['complete', 'incomplete', 'deferred', 'unknown'].includes(row.completion_state)
        && A.shape(row.remaining_work, ['operation_count', 'metrics']) && object(row.remaining_work.metrics)
        && preparationMetrics.every(key => E.metric(row.remaining_work.metrics[key])) && Array.isArray(row.issues) && row.issues.every(value => typeof value === 'string'),
      '批次安排或待安排工时资料不完整，请刷新批次清单。');
      check(typeof row.schedule_complete === 'boolean' && ['scheduled_operation_count', 'unplanned_operation_count', 'deferred_operation_count'].every(key => count(row[key]))
        && count(row.remaining_work.operation_count) && row.remaining_work.operation_count === row.unplanned_operation_count + row.deferred_operation_count,
      '批次的工序安排数量与读取的资料不一致，请刷新批次清单。');
      check(q.completion_filter === 'all' || q.completion_filter === 'complete' && row.schedule_complete === true
        || q.completion_filter === 'unfinished' && row.schedule_complete !== true || q.completion_filter === 'ordinary' && row.completion_state === 'incomplete'
        || q.completion_filter === 'deferred' && row.completion_state === 'deferred' || q.completion_filter === 'unknown' && row.completion_state === 'unknown',
      '批次清单与当前筛选条件不一致，请刷新批次清单。');
      remainingDrill(row.remaining_drill, row.remaining_work.operation_count, row.batch_ref);
    });
    check(new Set(data.items.map(row => row.batch_ref)).size === data.items.length, '批次清单出现重复记录，请刷新批次清单。');
    return data;
  }
  function processScope(runRef, query) {
    const value = { ...scope(runRef, query), record_kind: 'attempts', order: 'asc', page: 1, size: 20 };
    ['process_candidate_ref', 'objective', 'record_kind', 'sort', 'order', 'page', 'size'].forEach(key => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
    });
    if (value.process_candidate_ref === undefined && value.selected_candidate_ref) value.process_candidate_ref = value.selected_candidate_ref;
    if (value.sort === undefined) value.sort = value.record_kind === 'progress' ? 'elapsed_ms' : 'rank';
    check(value.process_candidate_ref === undefined || ref(value.process_candidate_ref), '优化过程的方案选择已失效，请重新选择方案。');
    check(value.objective === undefined || G.objective(value.objective), '请选择有效的优化方向。');
    check(['attempts', 'progress'].includes(value.record_kind)
      && (value.record_kind === 'progress' ? ['event_index', 'elapsed_ms', 'primary_value'] : ['rank', 'elapsed_ms']).includes(value.sort)
      && ['asc', 'desc'].includes(value.order), '优化过程的筛选或排序条件无效，请重新选择。');
    check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '优化过程每页支持 20 或 50 条，请重新选择页码。');
    return value;
  }
  // 优化过程只有共同优化一种存档（unified-optimization-process-v1）。
  function processDetails(payload, runRef, query) {
    const data = payload.data, q = processScope(runRef, query);
    const nullableText = value => value === null || typeof value === 'string';
    const amount = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
    const optionalAmount = value => value === null || amount(value), positive = value => count(value) && value > 0;
    const numbers = value => object(value) && Object.values(value).every(amount);
    const integers = value => object(value) && Object.values(value).every(count);
    const descriptors = ['name', 'label', 'primary_metric_key', 'primary_metric_label', 'unit', 'score_fields'];
    const fields = ['run_ref', 'capture_ref', 'scope', 'baseline', 'process_version', 'summary', 'counts', 'budget', 'stop_reason', 'bridges',
      'objectives', 'selected_objective', 'progress', 'scopes', 'actions', 'stages', 'candidate', 'candidates', 'source_event', 'items', 'page', 'filters'];
    check(A.shape(data, fields) && data.process_version === 'unified-optimization-process-v1' && data.run_ref === runRef && data.capture_ref === runRef
      && object(data.scope) && data.scope.run_ref === runRef && data.scope.comparison_mode === q.comparison_mode
      && (q.selected_candidate_ref ? data.scope.selected_candidate_ref === q.selected_candidate_ref : data.scope.selected_candidate_ref === null || ref(data.scope.selected_candidate_ref))
      && time(data.scope.range_start) && time(data.scope.range_end) && timeKey(data.scope.range_start) < timeKey(data.scope.range_end)
      && object(data.scope.reference) && object(data.baseline) && data.baseline.kind === data.scope.reference.kind
      && data.baseline.state === data.scope.reference_state && G.runOptions(data.scope.run_options), '共同优化过程的运行或保存选项不一致，请点“刷新优化过程”。');
    bindScope(payload, data, q);
    if (q.comparison_mode === 'candidates') check(data.scope.reference.kind === 'candidate'
      && data.baseline.candidate_ref === data.scope.reference.candidate_ref
      && (data.scope.reference_state === 'available' ? ref(data.scope.reference.candidate_ref) : data.scope.reference_state === 'selection_required' && data.scope.reference.candidate_ref === null)
      && (!q.reference_candidate_ref || data.scope.reference.candidate_ref === q.reference_candidate_ref), '过程的查看基准已变化，请点“刷新优化过程”。');
    const names = data.scope.run_options.target_objectives;
    const descriptor = value => A.shape(value, descriptors) && G.objective(value.name)
      && ['label', 'primary_metric_key', 'primary_metric_label', 'unit'].every(key => typeof value[key] === 'string')
      && Array.isArray(value.score_fields) && G.sameArray(value.score_fields.map(field => field.key), G.fieldOrders[value.name])
      && value.score_fields.every((field, index) => A.shape(field, ['index', 'key', 'label', 'unit', 'direction'])
        && field.index === index && field.direction === 'lower' && ['key', 'label', 'unit'].every(key => typeof field[key] === 'string'));
    check(Array.isArray(data.objectives) && G.sameArray(data.objectives.map(value => value.name), names) && data.objectives.every(descriptor)
      && descriptor(data.selected_objective) && names.includes(data.selected_objective.name)
      && data.selected_objective.name === (q.objective || data.scope.run_options.primary_objective)
      && JSON.stringify(data.selected_objective) === JSON.stringify(data.objectives.find(value => value.name === data.selected_objective.name)),
    '过程的优化方向或评分字段已变化，请点“刷新优化过程”。');
    const selectedObjective = data.selected_objective.name, summary = data.summary;
    check(A.shape(summary, ['elapsed_ms', 'first_complete_elapsed_ms', 'first_improvement_elapsed_ms', 'last_improvement_elapsed_ms']) && amount(summary.elapsed_ms)
      && ['first_complete_elapsed_ms', 'first_improvement_elapsed_ms', 'last_improvement_elapsed_ms'].every(key => optionalAmount(summary[key]) && (summary[key] === null || summary[key] <= summary.elapsed_ms))
      && (summary.first_improvement_elapsed_ms === null ? summary.last_improvement_elapsed_ms === null
        : summary.last_improvement_elapsed_ms !== null && summary.first_improvement_elapsed_ms <= summary.last_improvement_elapsed_ms)
      && nullableText(data.stop_reason), '共同优化的真实用时或改善时刻不完整，请点“刷新优化过程”。');
    check(A.shape(data.counts, ['actual_decoder_calls', 'new_decisions', 'decision_reuses', 'skipped_requests', 'failed_decoder_calls', 'request_count', 'execution_counts'])
      && ['actual_decoder_calls', 'new_decisions', 'decision_reuses', 'skipped_requests', 'failed_decoder_calls', 'request_count'].every(key => count(data.counts[key]))
      && integers(data.counts.execution_counts), '共同优化的实际计算次数不完整，请点“刷新优化过程”。');
    const goalFields = ['objective_status', 'weight', 'elapsed_seconds', 'charged_seconds', 'preparation_seconds', 'action_count', 'new_decisions',
      'reused_decisions', 'probe_decisions', 'minimum_opportunity', 'improvement_action_count', 'has_gain', 'feedback_rate', 'feedback_bonus',
      'unavailable_reason', 'budget_reason', 'phase_elapsed_seconds'];
    const goals = data.budget && data.budget.objectives;
    check(object(data.budget) && amount(data.budget.configured_seconds) && data.budget.configured_seconds > 0
      && A.shape(goals, names) && names.every(name => {
        const value = goals[name];
        return A.shape(value, goalFields) && ['searched', 'paused_no_gain', 'not_searched_budget', 'not_applicable'].includes(value.objective_status)
          && ['weight', 'elapsed_seconds', 'charged_seconds', 'preparation_seconds', 'feedback_rate', 'feedback_bonus'].every(key => amount(value[key]))
          && ['action_count', 'new_decisions', 'reused_decisions', 'probe_decisions', 'improvement_action_count'].every(key => count(value[key]))
          && ['minimum_opportunity', 'has_gain'].every(key => typeof value[key] === 'boolean')
          && nullableText(value.unavailable_reason) && nullableText(value.budget_reason) && numbers(value.phase_elapsed_seconds);
      }), '各优化方向的实际预算机会不完整，请点“刷新优化过程”。');
    check(object(data.scopes) && Object.entries(data.scopes).every(([key, value]) => /^[1-9]\d*$/.test(key) && G.scoringScope(value)),
      '过程的完整评价范围不完整，请点“刷新优化过程”。');
    const memberFields = ['candidate_ref', 'label', 'status', 'representative_objectives', 'origin', 'first_found_elapsed_ms', 'search_evidence_ref'];
    const member = value => A.shape(value, memberFields) && ref(value.candidate_ref) && nullableText(value.label)
      && ['completed', 'partial'].includes(value.status) && G.objectives(value.representative_objectives)
      && value.representative_objectives.every(name => names.includes(name)) && G.origin(value.origin)
      && amount(value.first_found_elapsed_ms) && G.evidence(value.search_evidence_ref, runRef);
    check(Array.isArray(data.candidates) && data.candidates.length >= 1 && data.candidates.length <= 3 && data.candidates.every(member)
      && new Set(data.candidates.map(value => value.candidate_ref)).size === data.candidates.length && member(data.candidate),
    '过程来源候选的保存身份不完整，请点“刷新优化过程”。');
    const catalog = new Map(data.candidates.map(value => [value.candidate_ref, value]));
    const anchor = q.process_candidate_ref || data.scope.selected_candidate_ref || data.candidates[0].candidate_ref;
    check(data.candidate.candidate_ref === anchor && catalog.has(anchor)
      && JSON.stringify(data.candidate) === JSON.stringify(catalog.get(anchor))
      && (data.scope.selected_candidate_ref === null || catalog.has(data.scope.selected_candidate_ref)), '过程来源定位已变化，请点“刷新优化过程”。');
    check(data.source_event === null || object(data.source_event) && positive(data.source_event.event_id)
      && data.source_event.event_id === data.candidate.search_evidence_ref.source_event_id && amount(data.source_event.elapsed_ms)
      && typeof data.source_event.phase === 'string' && typeof data.source_event.verified === 'boolean'
      && (data.source_event.scope_ref === undefined || Object.prototype.hasOwnProperty.call(data.scopes, data.source_event.scope_ref)),
    '候选的真实来源事件不一致，请点“刷新优化过程”。');
    const pointFields = ['elapsed_ms', 'entry_id', 'source_event_id', 'search_objective', 'origin', 'score', 'field_order', 'scope_ref', 'segment', 'flags', 'phase', 'verified', 'primary_value'];
    const mandatoryFlags = ['first_valid', 'first_expected_complete', 'final'], pointFlags = [...mandatoryFlags, 'strict_improvement'];
    const point = value => A.shape(value, pointFields) && amount(value.elapsed_ms) && positive(value.entry_id) && positive(value.source_event_id)
      && names.includes(value.search_objective) && nullableText(value.origin) && typeof value.phase === 'string' && typeof value.verified === 'boolean'
      && G.score(value.score) && G.sameArray(value.field_order, G.fieldOrders[selectedObjective]) && value.score.length === value.field_order.length
      && Object.prototype.hasOwnProperty.call(data.scopes, value.scope_ref) && count(value.segment)
      && Array.isArray(value.flags) && value.flags.every(flag => pointFlags.includes(flag)) && new Set(value.flags).size === value.flags.length
      && value.primary_value === value.score[value.field_order.indexOf(data.selected_objective.primary_metric_key)];
    const sampling = data.progress && data.progress.sampling;
    check(A.shape(data.progress, ['points', 'sampling']) && Array.isArray(data.progress.points) && data.progress.points.length <= 200 && data.progress.points.every(point)
      && A.shape(sampling, ['policy', 'point_budget', 'event_total_count', 'retained_point_count', 'bucket_count', 'bucket_width_ms', 'mandatory'])
      && sampling.policy === 'elapsed_equal_width_bucket_end_best_v1' && sampling.point_budget === 200
      && ['event_total_count', 'retained_point_count', 'bucket_count'].every(key => count(sampling[key]))
      && sampling.retained_point_count === data.progress.points.length && optionalAmount(sampling.bucket_width_ms) && G.sameArray(sampling.mandatory, mandatoryFlags),
    '所选方向的进步事件或采样资料不完整，请点“刷新优化过程”。');
    const actionFields = ['action_id', 'search_objective', 'phase', 'initial_construction', 'started_elapsed_ms', 'finished_elapsed_ms', 'elapsed_ms',
      'evaluation_count', 'verified_evaluation_count', 'new_decisions', 'reused_decisions', 'skip_reason', 'improved_objectives'];
    const counters = ['evaluation_count', 'verified_evaluation_count', 'new_decisions', 'reused_decisions'];
    const action = value => A.shape(value, actionFields) && positive(value.action_id) && value.search_objective === selectedObjective
      && typeof value.phase === 'string' && typeof value.initial_construction === 'boolean'
      && ['started_elapsed_ms', 'finished_elapsed_ms', 'elapsed_ms'].every(key => amount(value[key])) && value.started_elapsed_ms <= value.finished_elapsed_ms
      && counters.every(key => count(value[key])) && value.verified_evaluation_count <= value.evaluation_count
      && nullableText(value.skip_reason) && G.objectives(value.improved_objectives) && value.improved_objectives.every(name => names.includes(name));
    check(Array.isArray(data.actions) && data.actions.every(action) && new Set(data.actions.map(value => value.action_id)).size === data.actions.length
      && Array.isArray(data.stages) && data.stages.every(value => A.shape(value, ['phase', 'start_elapsed_ms', 'end_elapsed_ms', 'elapsed_ms', 'action_count', ...counters])
        && typeof value.phase === 'string' && ['start_elapsed_ms', 'end_elapsed_ms', 'elapsed_ms'].every(key => optionalAmount(value[key]))
        && count(value.action_count) && counters.every(key => count(value[key]))), '实际搜索动作或阶段统计不完整，请点“刷新优化过程”。');
    check(Array.isArray(data.bridges) && data.bridges.every(value => A.shape(value, ['search_objective', 'phase', 'before_entry_id', 'after_entry_id', 'elapsed_ms',
      'started_elapsed_ms', 'finished_elapsed_ms', 'same_arrangement', 'decoder_executed', 'reference_kind', 'source_event_id'])
      && names.includes(value.search_objective) && ['phase', 'reference_kind'].every(key => typeof value[key] === 'string')
      && ['before_entry_id', 'after_entry_id'].every(key => value[key] === null || positive(value[key]))
      && ['elapsed_ms', 'started_elapsed_ms', 'finished_elapsed_ms'].every(key => amount(value[key]))
      && (value.same_arrangement === null || typeof value.same_arrangement === 'boolean') && typeof value.decoder_executed === 'boolean' && positive(value.source_event_id)),
    '共同优化的实际接续记录不完整，请点“刷新优化过程”。');
    check(A.shape(data.filters, ['section', 'process_candidate_ref', 'objective', 'record_kind', 'sort', 'order']) && data.filters.section === 'process'
      && data.filters.process_candidate_ref === anchor && data.filters.objective === selectedObjective
      && ['record_kind', 'sort', 'order'].every(key => data.filters[key] === q[key])
      && A.shape(data.page, ['number', 'size', 'total', 'has_more']) && data.page.number === q.page && data.page.size === q.size
      && count(data.page.total) && data.page.total === (q.record_kind === 'progress' ? data.progress.points.length : data.actions.length)
      && data.page.has_more === (q.page * q.size < data.page.total) && Array.isArray(data.items)
      && data.items.length === Math.min(q.size, Math.max(0, data.page.total - (q.page - 1) * q.size))
      && data.items.every(q.record_kind === 'progress' ? point : action), '过程方向、来源或分页位置已变化，请点“刷新优化过程”。');
    return data;
  }
  function detailScope(runRef, query, section) {
    const value = { ...scope(runRef, query), page: 1, size: 20, change_kind: 'all', sort: section === 'batches' ? 'worsened' : 'sequence', order: section === 'batches' ? 'desc' : 'asc' };
    if (section === 'batches') value.delivery_filter = 'all';
    ['page', 'size', 'change_kind', 'sort', 'order', 'batch_ref', ...(section === 'operations' ? ['resource_ref'] : ['delivery_filter', 'selected_batch_ref'])].forEach(key => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
    });
    check(ref(value.selected_candidate_ref), '请选择需要查看的方案。');
    check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '明细每页支持 20 或 50 条，请重新选择页码。');
    if (value.sort === 'current_priority' && query.order === undefined) value.order = 'asc';
    ['batch_ref', 'resource_ref', 'selected_batch_ref'].forEach(key => check(value[key] === undefined || ref(value[key]), '明细的批次或资源选择已失效，请重新选择。'));
    if (section === 'batches') check(['all', 'attention', 'overdue', 'deferred', 'unplanned', 'on_time'].includes(value.delivery_filter), '请选择需要查看的交付问题。');
    return value;
  }
  function details(payload, runRef, query, section) {
    const data = payload.data, q = detailScope(runRef, query, section);
    check(data.run_ref === runRef && data.scope && data.scope.run_ref === runRef && data.scope.selected_candidate_ref === q.selected_candidate_ref
      && data.scope.comparison_mode === q.comparison_mode && data.candidate && data.candidate.candidate_ref === q.selected_candidate_ref
      && Array.isArray(data.items) && data.page && data.page.number === q.page && data.page.size === q.size && data.filters && data.filters.section === section,
    '明细的方案、比较范围或页码已变化，请点“刷新影响明细”。');
    if (q.comparison_mode === 'candidates' && q.reference_candidate_ref)
      check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '明细的比较基准已变化，请点“刷新影响明细”。');
    ['change_kind', 'sort', 'order'].forEach(key => check(data.filters[key] === q[key], '明细的筛选或排序已变化，请点“刷新影响明细”。'));
    ['batch_ref', ...(section === 'operations' ? ['resource_ref'] : [])].forEach(key => check(data.filters[key] === (q[key] ?? null), '明细的批次或资源已变化，请点“刷新影响明细”。'));
    if (section === 'batches') {
      check(data.summary && object(data.summary.operation_changes)
        && ['changed_operation_count', 'machine_change_count'].every(key => {
          const metric = data.summary.operation_changes[key];
          return window.EffortProjectionContract.metric(metric) && metric.scope === 'full_admission' && metric.metric_version === 'decision-preparation-v4';
        }), '全范围工序安排变化资料不完整，请点“刷新影响明细”。');
      if (data.filters.delivery_filter !== undefined) check(data.filters.delivery_filter === q.delivery_filter, '交付问题筛选已变化，请点“刷新影响明细”。');
      if (q.selected_batch_ref || data.filters.selected_batch_ref !== undefined) check(data.filters.selected_batch_ref === (q.selected_batch_ref ?? null)
        && (q.selected_batch_ref ? data.selected_batch && data.selected_batch.batch_ref === q.selected_batch_ref : data.selected_batch === null),
      '所选批次与当前方案的归档资料不一致，请点“刷新影响明细”。');
    }
    check(data.items.every(row => ref(row.batch_ref) && (section === 'batches' || ref(row.operation_ref)) && row.drill), '明细的甘特定位资料不完整，请点“刷新影响明细”。');
    if (section === 'operations') check(data.items.every(row => row.runtime_effort === undefined || row.runtime_effort
      && window.EffortProjectionContract.compact(row.runtime_effort.before) && window.EffortProjectionContract.compact(row.runtime_effort.after)), '工序工时资料不完整，请点“刷新影响明细”。');
    bindScope(payload, data, q);
    return data;
  }
  const preparationSorts = ['sequence', 'batch_id', 'after_setup_hours', 'after_required_hours', 'setup_delta_hours'];
  const changeoverSorts = ['next_start', 'machine_label', 'next_batch_id'];
  const preparationMetrics = ['pending_setup_hours', 'scheduled_setup_hours', 'unplanned_setup_hours', 'deferred_setup_hours', 'pending_processing_hours', 'scheduled_processing_hours', 'unplanned_processing_hours', 'deferred_processing_hours'];
  const changeoverMetrics = ['type_changeover_count', 'changed_machine_count'];
  function preparationScope(runRef, query, section = 'preparation') {
    check(['preparation', 'changeovers'].includes(section), '请选择准备需求或工种切换明细。');
    const value = { ...scope(runRef, query), page: 1, size: 20, sort: section === 'preparation' ? 'sequence' : 'next_start', order: 'asc',
      ...(section === 'preparation' ? { allocation_state: 'all', work_scope: 'all' } : { event_side: 'all' }) };
    ['page', 'size', 'sort', 'order', 'machine_ref', ...(section === 'preparation' ? ['batch_ref', 'allocation_state', 'work_scope'] : ['event_side'])].forEach(key => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
    });
    check(ref(value.selected_candidate_ref), '请选择需要查看的方案。');
    check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '准备与切换明细每页支持 20 或 50 条。');
    ['machine_ref', 'batch_ref'].forEach(key => check(value[key] === undefined || ref(value[key]), '准备与切换明细的批次或设备选择已失效，请重新选择。'));
    check(['asc', 'desc'].includes(value.order) && (section === 'preparation' ? preparationSorts : changeoverSorts).includes(value.sort), '准备与切换排序无效，请重新选择。');
    check(section === 'preparation' ? ['all', 'remaining'].includes(value.work_scope) && ['all', ...Object.keys(window.WorkbenchTerms.preparation_allocations)].includes(value.allocation_state)
      : ['all', 'selected', 'reference'].includes(value.event_side), '准备与切换筛选无效，请重新选择。');
    return value;
  }
  function preparationDetails(payload, runRef, query, section = 'preparation') {
    const data = payload.data, q = preparationScope(runRef, query, section), E = window.EffortProjectionContract;
    check(data.run_ref === runRef && data.scope && data.scope.run_ref === runRef && data.scope.selected_candidate_ref === q.selected_candidate_ref
      && data.scope.comparison_mode === q.comparison_mode && data.candidate && data.candidate.candidate_ref === q.selected_candidate_ref
      && data.metric_version === 'decision-preparation-v4' && data.filters && data.filters.section === section && Array.isArray(data.items)
      && data.baseline && ['available', 'absent', 'selection_required'].includes(data.baseline.state)
      && data.page && data.page.number === q.page && data.page.size === q.size && Number.isSafeInteger(data.page.total) && data.page.total >= 0,
    '准备与切换明细的方案、范围或页码已变化，请点“刷新准备与切换明细”。');
    if (q.comparison_mode === 'candidates' && q.reference_candidate_ref) check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '准备与切换明细的比较基准已变化，请点“刷新准备与切换明细”。');
    ['sort', 'order', ...(section === 'preparation' ? ['allocation_state', 'work_scope'] : ['event_side'])].forEach(key => check(data.filters[key] === q[key], '准备与切换明细的筛选或排序已变化，请点“刷新准备与切换明细”。'));
    ['machine_ref', ...(section === 'preparation' ? ['batch_ref'] : [])].forEach(key => check(data.filters[key] === (q[key] ?? null), '准备与切换明细的批次或设备已变化，请点“刷新准备与切换明细”。'));
    bindScope(payload, data, q);
    check(data.filter_options && Array.isArray(data.filter_options.machines) && data.filter_options.machines.every(row => ref(row.ref) && row.kind === 'machine')
      && (section !== 'preparation' || Array.isArray(data.filter_options.batches) && data.filter_options.batches.every(row => ref(row.ref))), '准备与切换明细的批次或设备选项不完整，请点“刷新准备与切换明细”。');
    function drill(value, side, operationRef) {
      if (side === 'reference' && data.baseline.state !== 'available') return value === null;
      const official = side === 'reference' && q.comparison_mode === 'admission_official';
      return value && value.run_ref === runRef && value.comparison_mode === q.comparison_mode && value.operation_ref === operationRef
        && value.candidate_ref === (side === 'reference' && !official ? data.scope.reference.candidate_ref : q.selected_candidate_ref)
        && (value.resource_view === undefined || value.resource_view === q.resource_view)
        && (official ? value.reference_view === true && value.plan_ref === data.baseline.baseline_ref : value.reference_view !== true);
    }
    const keys = section === 'preparation' ? preparationMetrics : changeoverMetrics;
    check(data.summary && data.summary.scope === (section === 'preparation' ? 'full_admission' : 'fixed_changeover_window')
      && ['before', 'after'].every(side => data.summary[side] && keys.every(key => E.metric(data.summary[side][key])))
      && data.summary.deltas && keys.every(key => E.delta(data.summary.deltas[key])), '准备与加工工时或切换次数资料不完整，请点“刷新准备与切换明细”。');
    if (section === 'preparation') {
      check(data.summary.role_totals && ['before', 'after'].every(side => data.summary.role_totals[side] && ['retained', 'execution', 'completed'].every(role => {
        const value = data.summary.role_totals[side][role]; return value && Number.isSafeInteger(value.count) && value.count >= 0
          && ['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'].every(key => E.metric(value[key]));
      })), '已有安排及已开工、已完工工序的工时资料不完整，请点“刷新准备与切换明细”。');
      check(data.items.every(row => ref(row.operation_ref) && ref(row.batch_ref) && E.side(row.before) && E.side(row.after) && row.deltas
        && ['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'].every(key => E.delta(row.deltas[key]))
        && row.drill && drill(row.drill.selected, 'selected', row.operation_ref) && drill(row.drill.reference, 'reference', row.operation_ref)), '准备与加工工时或甘特定位资料不完整，请点“刷新准备与切换明细”。');
    } else check(data.items.every(row => typeof row.event_ref === 'string' && ['selected', 'reference'].includes(row.event_side) && ref(row.machine_ref)
      && ref(row.previous_operation_ref) && ref(row.next_operation_ref) && ref(row.previous_row_ref) && ref(row.next_row_ref)
      && row.previous && row.next && typeof row.predecessor_outside_window === 'boolean' && [true, false, null].includes(row.overlap)
      && row.drill && drill(row.drill.previous, row.event_side, row.previous_operation_ref) && drill(row.drill.next, row.event_side, row.next_operation_ref)), '工种切换事件或甘特定位资料不完整，请点“刷新准备与切换明细”。');
    return data;
  }
  function validateReferenceWorkspace(payload, runRef, query) {
    const data = payload.data;
    check(data.candidate && data.candidate.run_ref === runRef && data.candidate.candidate_ref === query.selected_candidate_ref
      && data.reference && data.reference.kind === 'admission_official' && Array.isArray(data.tasks) && Array.isArray(data.unplanned_operations),
    '正式计划资料与本次比较不一致，请从方案对比重新打开。');
    check(ref(data.plan_ref) && data.plan_ref === data.reference.plan_ref && data.plan_ref === data.reference.baseline_ref
      && (!query.plan_ref || data.plan_ref === query.plan_ref), '比较基准的正式计划已变化，请从方案对比重新打开。');
    check([data.capabilities, data.candidate.capabilities].every(caps => caps && ['edit_draft', 'adopt', 'report_actual'].every(key => caps[key] === false)),
      '这份正式计划的查看资料已失效，请从方案对比重新打开。');
    check(data.batch_ref === (query.batch_ref || null), '正式计划的批次范围已变化，请从方案对比重新打开。');
    for (const key of ['range_start', 'range_end']) if (query[key])
      check(data.time_scope && time(data.time_scope[key]) && timeKey(data.time_scope[key]) === timeKey(query[key]), '正式计划的时间范围已变化，请从方案对比重新打开。');
    if (query.resource_view) check(data.scope && data.scope.resource_view === query.resource_view, '正式计划的资源范围已变化，请从方案对比重新打开。');
    check([...data.tasks, ...data.unplanned_operations].every(row => row.operation_effort === undefined || window.EffortProjectionContract.compact(row.operation_effort)), '正式计划的工序工时资料不完整，请从方案对比重新打开。');
    bindSnapshot(payload, query);
    return data;
  }
  function resourceFilters(query, section = 'resources') {
    const value = { resource_kind: 'machine', grain: 'day', pressure_threshold: 0.9, page: 1, size: 20 };
    const keys = ['resource_kind', 'resource_ref', 'grain', 'pressure_threshold', 'page', 'size'];
    if (section === 'resources') {
      Object.assign(value, { pressure_filter: 'all', sort: 'after_peak_utilization', order: 'desc', heatmap_page: 1, heatmap_size: 7 });
      keys.push('pressure_filter', 'sort', 'order', 'heatmap_page', 'heatmap_size', 'display_start', 'display_end');
    } else keys.push('bucket_start', 'bucket_end');
    keys.forEach(key => { if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key]; });
    check(['machine', 'operator'].includes(value.resource_kind), '请选择设备或人员。');
    check(value.resource_ref === undefined || ref(value.resource_ref), '设备或人员选择已失效，请重新选择。');
    check(['hour', 'shift', 'day', 'week'].includes(value.grain) && typeof value.pressure_threshold === 'number'
      && Number.isFinite(value.pressure_threshold) && value.pressure_threshold > 0 && value.pressure_threshold <= 1,
    '请选择时间粒度与有效的高负荷关注线。');
    const rangeKeys = section === 'resources' ? ['display_start', 'display_end'] : ['bucket_start', 'bucket_end'];
    if (rangeKeys.some(key => value[key] !== undefined)) check(rangeKeys.every(key => time(value[key]))
      && timeKey(value[rangeKeys[0]]) < timeKey(value[rangeKeys[1]])
      && (section !== 'resources' || value.grain === 'hour'), '时段起止要同时填写，结束时间须晚于开始时间。');
    if (section === 'resources') check(['all', 'high_pressure', 'zero_capacity', 'conflicts', 'unknown', 'demand_overload'].includes(value.pressure_filter), '请选择资源负荷筛选。');
    if (section === 'resource-days') check(ref(value.resource_ref), '请选择要查看逐日明细的设备或人员。');
    check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '资源明细每页支持 20 或 50 条，请重新选择。');
    if (section === 'resources') check(Number.isInteger(value.heatmap_page) && value.heatmap_page > 0 && [7, 14, 31].includes(value.heatmap_size), '热力图每页支持 7、14 或 31 天，请重新选择。');
    if (query.snapshot_ref !== undefined && query.snapshot_ref !== null && query.snapshot_ref !== '') value.snapshot_ref = query.snapshot_ref;
    return value;
  }
  function resourceScope(runRef, query, section = 'resources') {
    const value = { ...scope(runRef, query), ...resourceFilters(query, section) };
    check(ref(value.selected_candidate_ref), '请选择查看方案及设备或人员。');
    return value;
  }
  function savedResourceView(query, cohort, comparison) {
    const next = { ...query }, refs = cohort[next.resource_kind || 'machine'];
    if (next.resource_ref && !refs.includes(next.resource_ref)) { delete next.resource_ref; delete next.snapshot_ref; next.page = 1; }
    if (comparison && next.display_start && (timeKey(next.display_start) < timeKey(comparison.range_start) || timeKey(next.display_end) > timeKey(comparison.range_end))) {
      delete next.display_start; delete next.display_end; delete next.snapshot_ref; next.heatmap_page = 1;
    }
    return next;
  }
  function resourceWorkspaceScope(runRef, query, savedQuery) {
    const filters = resourceFilters(savedQuery), resourceSnapshot = filters.snapshot_ref; delete filters.snapshot_ref;
    return { ...scope(runRef, query), ...filters, ...(resourceSnapshot !== undefined ? { resource_snapshot_ref: resourceSnapshot } : {}) };
  }
  // 资源首屏的 data 在方案对比首屏之外多带 resource_result（内嵌的资源读取结果）与 resource_query（实际采用的资源筛选）。
  function validateResourceWorkspace(payload, runRef, query, savedQuery) {
    const data = validateDecisionSummary(payload, runRef, query), { resource_result: resources, resource_query: effective } = data, cohort = data.scope.resource_refs;
    check(object(cohort) && ['machine', 'operator'].every(kind => Array.isArray(cohort[kind]) && cohort[kind].every(ref)
      && new Set(cohort[kind]).size === cohort[kind].length), '参与比较的设备或人员资料不完整，请刷新方案对比。');
    const filterKeys = ['resource_kind', 'grain', 'pressure_threshold', 'page', 'size', 'pressure_filter', 'sort', 'order', 'heatmap_page', 'heatmap_size'];
    check(A.shape(effective, filterKeys, ['resource_ref', 'display_start', 'display_end', 'snapshot_ref']), '恢复的资源筛选资料不完整，请刷新方案对比。');
    const expected = resourceFilters(savedResourceView(resourceFilters(savedQuery), cohort, data.scope)), actual = resourceFilters(effective);
    check(JSON.stringify(actual) === JSON.stringify(expected) && Object.keys(effective).length === Object.keys(actual).length,
      '恢复的资源筛选与当前范围不一致，请刷新方案对比。');
    const candidate = data.candidates.find(row => row.candidate_ref === data.scope.selected_candidate_ref);
    if (!candidate) {
      check(resources === null, '当前方案没有可查看的资源结果，请刷新方案对比。'); return data;
    }
    check(object(resources), '资源读取结果未记录，请刷新方案对比。');
    // 内嵌的资源结果没有经过传输层：成功时按同一份查询信封核对；失败时原样留给资源页签，由 APSWorkbenchTransport.failure 统一解析。
    if (resources.ok === true) {
      T.envelope(resources);
      const comparison = { comparison_mode: data.scope.comparison_mode, resource_view: data.scope.resource_view,
        selected_candidate_ref: data.scope.selected_candidate_ref, range_start: data.scope.range_start, range_end: data.scope.range_end,
        ...(data.scope.comparison_mode === 'candidates' ? { reference_candidate_ref: data.scope.reference.candidate_ref } : {}) };
      resourceDetails(resources, runRef, { ...comparison, ...actual, expected_resource_refs: cohort });
    }
    return data;
  }
  function resourceDetails(payload, runRef, query, section = 'resources') {
    const data = payload.data, q = resourceScope(runRef, query, section);
    check(data.run_ref === runRef && data.scope && data.scope.run_ref === runRef && data.scope.selected_candidate_ref === q.selected_candidate_ref
      && data.scope.comparison_mode === q.comparison_mode && data.candidate && data.candidate.candidate_ref === q.selected_candidate_ref
      && data.metric_version === 'decision-resource-v4' && data.filters && data.filters.section === section && data.filters.resource_kind === q.resource_kind
      && data.filters.resource_ref === (q.resource_ref ?? null) && Array.isArray(data.items) && data.page && data.page.number === q.page && data.page.size === q.size,
    '资源明细的方案、设备人员范围或页码已变化，请点“刷新资源影响”。');
    if (q.comparison_mode === 'candidates' && q.reference_candidate_ref)
      check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '资源明细的比较基准已变化，请点“刷新资源影响”。');
    bindScope(payload, data, q);
    check(data.filters.grain === q.grain && data.filters.pressure_threshold === q.pressure_threshold
      && (section === 'resources' || ['bucket_start', 'bucket_end'].every(key => data.filters[key] === (q[key] ?? null))),
    '资源时间粒度、关注线或所选时段已变化，请点“刷新资源影响”。');
    const cohort = data.scope.resource_refs;
    check(cohort && ['machine', 'operator'].every(kind => Array.isArray(cohort[kind]) && cohort[kind].every(ref) && new Set(cohort[kind]).size === cohort[kind].length), '参与比较的设备或人员资料不完整，请点“刷新资源影响”。');
    if (query.expected_resource_refs) check(['machine', 'operator'].every(kind => JSON.stringify(cohort[kind]) === JSON.stringify(query.expected_resource_refs[kind])), '参与比较的设备或人员已变化，请点“刷新资源影响”。');
    const windowSource = value => window.ResourceProjectionContract.window(value) && value.source === 'archived_resource_calendar';
    function drillIdentity(value, side, resourceRef) {
      if (side === 'reference' && data.baseline.state !== 'available') return value === null;
      const official = side === 'reference' && q.comparison_mode === 'admission_official';
      return value && value.run_ref === runRef && value.comparison_mode === q.comparison_mode && value.resource_view === q.resource_view
        && value.resource_kind === q.resource_kind && value.resource_ref === resourceRef
        && value.candidate_ref === (side === 'reference' && !official ? data.scope.reference.candidate_ref : q.selected_candidate_ref)
        && (official ? value.reference_view === true && value.plan_ref === data.baseline.baseline_ref : value.reference_view !== true);
    }
    const pairedDrill = (row, resourceRef) => row.drill && ['selected', 'reference'].every(side => drillIdentity(row.drill[side], side, resourceRef));
    check(data.summary && (section === 'resources' ? [data.summary.before, data.summary.after].every(window.ResourceProjectionContract.summary)
      : [data.summary.before, data.summary.after].every(windowSource)), '资源使用统计所需的班表资料不完整，请点“刷新资源影响”。');
    check(data.items.every(row => windowSource(row.before) && windowSource(row.after) && row.drill), '设备或人员使用统计所需的班表资料不完整，请点“刷新资源影响”。');
    if (section === 'resources') {
      ['pressure_filter', 'sort', 'order'].forEach(key => check(data.filters[key] === q[key], '资源明细的筛选或排序已变化，请点“刷新资源影响”。'));
      check(data.items.every(row => ref(row.resource_ref) && row.resource_kind === q.resource_kind && cohort[q.resource_kind].includes(row.resource_ref) && (!q.resource_ref || row.resource_ref === q.resource_ref) && pairedDrill(row, row.resource_ref))
        && data.heatmap && data.heatmap.page.number === q.heatmap_page && data.heatmap.page.size === q.heatmap_size && Array.isArray(data.heatmap.buckets) && Array.isArray(data.heatmap.items),
      '资源表或热力图的设备人员范围已变化，请点“刷新资源影响”。');
      {
        check(data.heatmap.grain === q.grain && Array.isArray(data.heatmap.buckets)
          && data.heatmap.buckets.every(bucket => typeof bucket.key === 'string' && time(bucket.start) && time(bucket.end)
            && timeKey(bucket.start) < timeKey(bucket.end))
          && new Set(data.heatmap.buckets.map(bucket => bucket.key)).size === data.heatmap.buckets.length,
        '资源时段的粒度或起止时间不完整，请点“刷新资源影响”。');
        const buckets = new Map(data.heatmap.buckets.map(bucket => [bucket.key, bucket]));
        check(data.heatmap.items.length === data.items.length && data.heatmap.items.every((row, index) => row.resource_ref === data.items[index].resource_ref
          && row.resource_kind === q.resource_kind && Array.isArray(row.cells)
          && new Set(row.cells.map(cell => cell.bucket_key)).size === row.cells.length
          && row.cells.every(cell => {
            const bucket = buckets.get(cell.group_key || cell.bucket_key);
            return bucket && cell.date === bucket.date && typeof cell.bucket_key === 'string' && time(cell.start) && time(cell.end)
              && timeKey(cell.start) < timeKey(cell.end) && timeKey(cell.start) >= timeKey(bucket.start)
              && timeKey(cell.end) <= timeKey(q.grain === 'shift' ? data.scope.range_end : bucket.end)
              && windowSource(cell.before) && windowSource(cell.after);
          })), '热力图的设备人员或实际时段已变化，请点“刷新资源影响”。');
        if (q.grain === 'hour' && data.heatmap.buckets.length) check(time(data.filters.display_start) && time(data.filters.display_end)
          && data.filters.display_start === data.heatmap.buckets[0].start && data.filters.display_end === data.heatmap.buckets[data.heatmap.buckets.length - 1].end,
        '小时筛选与实际显示时段不一致，请点“刷新资源影响”。');
      }
    } else {
      check(data.resource && data.resource.ref === q.resource_ref && data.resource.kind === q.resource_kind && cohort[q.resource_kind].includes(q.resource_ref), '逐日明细的设备或人员已变化，请点“刷新资源影响”。');
      check(data.items.every(day => typeof day.date === 'string' && time(day.start) && time(day.end) && day.start < day.end), '资源逐日明细的起止时间不完整，请点“刷新资源影响”。');
      check(data.items.every(day => pairedDrill(day, q.resource_ref) && ['before', 'after'].every(side => Array.isArray(day[side].tasks) && Array.isArray(day[side].conflicts)
        && [...day[side].tasks, ...day[side].conflicts].every(item => drillIdentity(item.drill, side === 'before' ? 'reference' : 'selected', q.resource_ref)))), '逐日工序或冲突的甘特位置与当前方案不一致，请点“刷新资源影响”。');
    }
    return data;
  }
  const BASE = '/api/workbench/v1/scheduling/runs/';
  const read = (runRef, leaf, query, signal) => T.read(BASE + runRef + '/decision' + leaf, query, { signal, timeout: 60000 });
  window.RunDecisionAPI = {
    async decision(runRef, query, signal) { const q = scope(runRef, query), value = await read(runRef, '', q, signal); validateDecision(value, runRef, q); return value; },
    async decisionSummary(runRef, query, signal) { const q = scope(runRef, query), value = await read(runRef, '/summary', q, signal); validateDecisionSummary(value, runRef, q); return value; },
    async resourceWorkspace(runRef, query, savedQuery, signal) {
      const value = await read(runRef, '/resource-workspace', resourceWorkspaceScope(runRef, query, savedQuery), signal); validateResourceWorkspace(value, runRef, query, savedQuery); return value;
    },
    async decisionDetails(runRef, query, section, signal) { const q = detailScope(runRef, query, section), value = await read(runRef, '/' + section, q, signal); details(value, runRef, q, section); return value; },
    async completionBatches(runRef, query, signal) {
      const q = completionScope(runRef, query), value = await read(runRef, '/completion-batches', q, signal); validateCompletionBatches(value, runRef, q); return value;
    },
    async process(runRef, query, signal) { const q = processScope(runRef, query), value = await read(runRef, '/process', q, signal); processDetails(value, runRef, q); return value; },
    async referenceWorkspace(runRef, query, signal) {
      const q = { ...scope(runRef, { ...query, comparison_mode: 'admission_official' }) };
      if (query.batch_ref) q.batch_ref = query.batch_ref;
      const value = await read(runRef, '/reference-workspace', q, signal); validateReferenceWorkspace(value, runRef, { ...q, plan_ref: query.plan_ref }); return value;
    },
    async resources(runRef, query, signal) {
      const q = resourceScope(runRef, query), value = await read(runRef, '/resources', q, signal);
      resourceDetails(value, runRef, { ...q, expected_resource_refs: query.expected_resource_refs }); return value;
    },
    async resourceDays(runRef, query, signal) {
      const q = resourceScope(runRef, query, 'resource-days'), value = await read(runRef, '/resource-days', q, signal);
      resourceDetails(value, runRef, { ...q, expected_resource_refs: query.expected_resource_refs }, 'resource-days'); return value;
    },
    async preparation(runRef, query, signal) { const q = preparationScope(runRef, query), value = await read(runRef, '/preparation', q, signal); preparationDetails(value, runRef, q); return value; },
    async changeovers(runRef, query, signal) { const q = preparationScope(runRef, query, 'changeovers'), value = await read(runRef, '/changeovers', q, signal); preparationDetails(value, runRef, q, 'changeovers'); return value; },
    async decisionExport(runRef, query, snapshotRef, format, signal, section) {
      check(['csv', 'xlsx'].includes(format) && typeof snapshotRef === 'string' && snapshotRef.length > 0);
      const detailSection = query.filter_section || (['batches', 'operations', 'resources', 'resource-days', 'preparation', 'changeovers', 'process'].includes(section) ? section : null);
      const q = detailSection === 'process' ? processScope(runRef, query) : ['preparation', 'changeovers'].includes(detailSection) ? preparationScope(runRef, query, detailSection)
        : ['resources', 'resource-days'].includes(detailSection) ? resourceScope(runRef, query, detailSection) : detailSection ? detailScope(runRef, query, detailSection) : scope(runRef, query);
      for (const key of ['page', 'size', 'heatmap_page', 'heatmap_size']) delete q[key];
      const file = await T.download(BASE + runRef + '/decision/export', { ...q, ...(detailSection ? { filter_section: detailSection } : {}), snapshot_ref: snapshotRef, format, section },
        { signal, timeout: 60000, types: [T.types[format]] });
      check(file.header('X-Workbench-Run-Ref') === runRef && file.header('X-Workbench-Snapshot-Ref') === snapshotRef, '比较资料已更新，请关闭导出窗口，刷新后重新导出。');
      // 传输层已校验附件、文件名与后缀、格式、魔数与非空；这里只断言本领域业务头。
      const rowCount = file.header('X-Workbench-Row-Count');
      check(rowCount !== null && /^\d+$/.test(rowCount), '导出文件没有读取到内容，请重新点击下载。');
      return { blob: file.blob, row_count: Number(rowCount), filename: file.filename };
    },
    validateDecision, validateDecisionSummary, validateResourceWorkspace, resourceWorkspaceScope, resourceFilters, savedResourceView, details, scope, detailScope,
    completionScope, validateCompletionBatches, processScope, processDetails, validateReferenceWorkspace, resourceScope, resourceDetails, preparationScope, preparationDetails
  };
})();
