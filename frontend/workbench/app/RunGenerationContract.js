(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string', nonempty = value => text(value) && value.length > 0;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  const ref = value => text(value) && /^[a-f0-9]{48}$/.test(value);
  const refs = values => Array.isArray(values) && values.every(ref) && new Set(values).size === values.length;
  const shape = (value, required, optional = []) => object(value) && required.every(key => Object.prototype.hasOwnProperty.call(value, key))
    && Object.keys(value).every(key => required.concat(optional).includes(key));
  const labels = { min_overdue: '交期优先', min_tardiness: '拖期更轻', min_changeover: '切换更少', min_weighted_tardiness: '加权拖期更轻' };
  const fieldOrders = {
    min_overdue: ['failed_ops', 'overdue_count', 'weighted_tardiness_hours', 'total_tardiness_hours', 'makespan_hours', 'changeover_count'],
    min_tardiness: ['failed_ops', 'total_tardiness_hours', 'overdue_count', 'weighted_tardiness_hours', 'makespan_hours', 'changeover_count'],
    min_weighted_tardiness: ['failed_ops', 'weighted_tardiness_hours', 'total_tardiness_hours', 'makespan_hours', 'changeover_count'],
    min_changeover: ['failed_ops', 'changeover_count', 'overdue_count', 'total_tardiness_hours', 'weighted_tardiness_hours', 'makespan_hours']
  };
  const metadataKeys = ['generation_policy_version', 'representative_objectives', 'evaluations', 'origin', 'first_found_elapsed_ms', 'search_evidence_ref'];
  const unified = value => object(value) && value.generation_policy_version === 'unified_search_v1';
  const budget = value => Number.isInteger(value) && value >= 1;
  const objective = value => text(value) && Object.prototype.hasOwnProperty.call(labels, value);
  const objectiveLabel = value => labels[value] || value;
  const sameArray = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((value, index) => value === b[index]);
  const targets = primary => [primary, ...['min_overdue', primary === 'min_weighted_tardiness' ? primary : 'min_tardiness', 'min_changeover'].filter(value => value !== primary)];
  const objectives = values => Array.isArray(values) && values.every(objective) && new Set(values).size === values.length;
  const score = values => Array.isArray(values) && values.every(value => value === null || typeof value === 'number' && Number.isFinite(value));
  function runOptions(value) {
    return shape(value, ['generation_policy_version', 'primary_objective', 'target_objectives', 'time_budget_seconds', 'algo_mode', 'graph_analysis_mode'])
      && unified(value) && objective(value.primary_objective) && sameArray(value.target_objectives, targets(value.primary_objective))
      && budget(value.time_budget_seconds) && ['greedy', 'improve'].includes(value.algo_mode) && ['off', 'report', 'on'].includes(value.graph_analysis_mode);
  }
  function scoringScope(value) {
    return shape(value, ['scheduled_operation_refs', 'complete_batch_refs', 'objective_scope', 'components_known', 'is_complete'])
      && refs(value.scheduled_operation_refs) && refs(value.complete_batch_refs) && ['all_batches', 'completed_batches_only', 'unknown'].includes(value.objective_scope)
      && typeof value.components_known === 'boolean' && typeof value.is_complete === 'boolean';
  }
  function evaluations(value) {
    return object(value) && Object.keys(value).length > 0 && Object.entries(value).every(([name, item]) => objective(name)
      && shape(item, ['field_order', 'score', 'scoring_scope']) && sameArray(item.field_order, fieldOrders[name])
      && score(item.score) && item.score.length === item.field_order.length && scoringScope(item.scoring_scope));
  }
  function origin(value) {
    return shape(value, ['search_objective', 'phase', 'origin', 'dispatch_mode', 'dispatch_rule', 'strategy', 'repair_decision'],
      ['request_id', 'source_event_ref', 'execution_kind', 'graph_ready_profile'])
      && objective(value.search_objective) && ['phase', 'origin', 'strategy'].every(key => nonempty(value[key]))
      && ['dispatch_mode', 'dispatch_rule'].every(key => value[key] === null || text(value[key]))
      && (value.repair_decision === null || object(value.repair_decision) || text(value.repair_decision))
      && ['request_id', 'source_event_ref'].every(key => value[key] === undefined || value[key] === null || count(value[key]))
      && (value.execution_kind === undefined || nonempty(value.execution_kind))
      && (value.graph_ready_profile === undefined || object(value.graph_ready_profile));
  }
  function evidence(value, runRef) {
    return shape(value, ['run_ref', 'source_event_id']) && ref(value.run_ref) && (!runRef || value.run_ref === runRef)
      && (value.source_event_id === null || count(value.source_event_id) && value.source_event_id > 0);
  }
  function metadata(value, runRef) {
    return unified(value) && metadataKeys.every(key => Object.prototype.hasOwnProperty.call(value, key))
      && objectives(value.representative_objectives) && evaluations(value.evaluations)
      && value.representative_objectives.every(name => Object.prototype.hasOwnProperty.call(value.evaluations, name))
      && origin(value.origin) && number(value.first_found_elapsed_ms) && evidence(value.search_evidence_ref, runRef);
  }
  function catalogElapsed(value) {
    return shape(value, ['value', 'state', 'reason']) && value.value === null && value.state === 'not_applicable'
      && shape(value.reason, ['field', 'code', 'message']) && value.reason.field === 'elapsed_seconds'
      && value.reason.code === 'shared_run_time' && text(value.reason.message);
  }
  function algorithm(value, runRef) {
    const fields = ['mode', 'mode_label', 'strategy', 'strategy_label'], current = unified(value);
    return shape(value, fields.concat(current ? metadataKeys.concat(['primary_objective', 'target_objectives']) : []))
      && fields.every(key => value[key] === null || text(value[key]))
      && (!current || metadata(value, runRef) && objective(value.primary_objective) && sameArray(value.target_objectives, targets(value.primary_objective)));
  }
  function selectionBasis(value, candidates) {
    const fields = ['generation_policy_version', 'selection_policy_version', 'primary_objective', 'target_objectives', 'selected_candidate_ref',
      'objective_winners', 'objective_winner_reasons', 'objective_field_order', 'selected_score', 'reason_code', 'scoring_scope', 'evidence_state',
      'objective_name', 'raw_score_best_candidate_ref', 'health_reference_candidate_ref', 'selection_policy', 'overdue_tolerance_count',
      'tardiness_tolerance_ratio', 'raw_score_comparison', 'health_comparison', 'selection_evidence_version', 'decision_evidence', 'health_decision_evidence', 'explanation'];
    if (!shape(value, fields) || !unified(value) || value.selection_policy_version !== 'business_objectives_v1'
      || !objective(value.primary_objective) || !sameArray(value.target_objectives, targets(value.primary_objective))
      || !ref(value.selected_candidate_ref) || value.objective_name !== value.primary_objective
      || value.raw_score_best_candidate_ref !== value.selected_candidate_ref || value.selection_policy !== 'business_objectives_v1'
      || value.selection_evidence_version !== 'business_objectives_v1' || !['complete', 'partial'].includes(value.evidence_state)
      || !['primary_objective_best_found', 'primary_objective_best_in_completed_scope', 'partial_scope_score_unavailable'].includes(value.reason_code)
      || !scoringScope(value.scoring_scope) || !score(value.selected_score) || !object(value.explanation)
      || !['health_reference_candidate_ref', 'overdue_tolerance_count', 'tardiness_tolerance_ratio', 'raw_score_comparison', 'health_comparison', 'decision_evidence', 'health_decision_evidence'].every(key => value[key] === null)
      || !shape(value.objective_winners, value.target_objectives) || !shape(value.objective_winner_reasons, value.target_objectives)
      || !shape(value.objective_field_order, value.target_objectives)) return false;
    const known = new Set(candidates.map(candidate => candidate.candidate_ref));
    return known.has(value.selected_candidate_ref) && value.target_objectives.every(name => {
      const winner = value.objective_winners[name], reason = value.objective_winner_reasons[name];
      return (winner === null || ref(winner) && known.has(winner)) && (reason === null || nonempty(reason))
        && sameArray(value.objective_field_order[name], fieldOrders[name]);
    }) && value.selected_score.length === value.objective_field_order[value.primary_objective].length;
  }
  window.RunGenerationContract = { metadataKeys, unified, budget, objective, objectives, objectiveLabel, targets, fieldOrders, sameArray,
    score, runOptions, scoringScope, evaluations, origin, evidence, metadata, catalogElapsed, algorithm, selectionBasis };
})();
