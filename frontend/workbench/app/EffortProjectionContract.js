(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const fields = (value, keys) => object(value) && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
  const text = value => typeof value === 'string', reference = value => text(value) && /^[a-f0-9]{48}$/.test(value);
  const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  const quantity = value => number(value) || text(value) && /^(?:0|[1-9]\d*)$/.test(value);
  const nullable = test => value => value === null || test(value);
  const states = ['complete', 'partial', 'unavailable', 'not_applicable'];
  const issue = value => object(value) && text(value.code) && text(value.message);
  const gaps = value => Array.isArray(value) && value.every(issue);
  const quantityFields = ['target_quantity', 'execution_target_quantity', 'remaining_quantity'];
  const hours = ['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'];
  function standard(value) {
    return fields(value, ['basis', 'setup_standard_hours', 'unit_standard_hours', 'standard_total_hours', 'target_quantity', 'remaining_quantity', 'state', 'reason'])
      && value.basis === 'archived_operation_standard' && states.includes(value.state)
      && ['setup_standard_hours', 'unit_standard_hours', 'standard_total_hours'].every(key => nullable(number)(value[key]))
      && ['target_quantity', 'remaining_quantity'].every(key => nullable(quantity)(value[key])) && (value.reason === null || issue(value.reason));
  }
  function evidence(value) {
    return value === null || object(value) && text(value.kind)
      && ['run_ref', 'candidate_ref', 'scenario_ref', 'plan_ref'].every(key => value[key] === undefined || nullable(reference)(value[key]));
  }
  function compact(value) {
    return fields(value, [...quantityFields, ...hours, 'source', 'quantity_basis', 'execution_quantity_basis', 'setup_state', 'requirement_role', 'allocation_state',
      'external_cycle_days', 'external_group_id', 'external_merge_mode', 'effort_basis', 'evidence_source', 'state', 'data_gaps', 'standard'])
      && ['internal', 'external', 'unknown', null].includes(value.source) && states.includes(value.state)
      && quantityFields.every(key => nullable(quantity)(value[key])) && [...hours, 'external_cycle_days'].every(key => nullable(number)(value[key]))
      && ['quantity_basis', 'execution_quantity_basis'].every(key => ['piece', 'batch', 'unknown', null].includes(value[key]))
      && ['pending', 'retained_in_execution', 'already_completed', 'external', 'unknown'].includes(value.setup_state)
      && ['new_schedule', 'retained', 'execution', 'completed', 'not_scheduled', 'unknown', null].includes(value.requirement_role)
      && ['new_schedule', 'unplanned', 'deferred', 'retained', 'execution', 'completed', 'external', 'unknown'].includes(value.allocation_state)
      && ['runtime_requirement_v1', null].includes(value.effort_basis) && ['external_group_id', 'external_merge_mode'].every(key => nullable(text)(value[key]))
      && evidence(value.evidence_source) && gaps(value.data_gaps) && standard(value.standard);
  }
  const resource = value => object(value) && nullable(reference)(value.ref) && nullable(text)(value.label);
  function side(value) {
    return compact(value) && fields(value, ['machine', 'machines', 'arrangements'])
      && (value.machine === null || resource(value.machine)) && Array.isArray(value.machines) && value.machines.every(resource) && Array.isArray(value.arrangements);
  }
  function metric(value) {
    return fields(value, ['value', 'state', 'known_subtotal', 'known_count', 'unknown_count', 'total_count', 'reason'])
      && nullable(number)(value.value) && states.includes(value.state) && nullable(number)(value.known_subtotal)
      && ['known_count', 'unknown_count', 'total_count'].every(key => Number.isSafeInteger(value[key]) && value[key] >= 0)
      && (value.reason === null || issue(value.reason));
  }
  function delta(value) {
    return fields(value, ['value', 'state', 'direction', 'reference_value', 'selected_value'])
      && (value.value === null || typeof value.value === 'number' && Number.isFinite(value.value))
      && ['comparable', 'different_coverage', 'unavailable'].includes(value.state) && ['neutral', 'equal', 'better', 'worse'].includes(value.direction)
      && ['reference_value', 'selected_value'].every(key => nullable(number)(value[key]));
  }
  window.EffortProjectionContract = Object.freeze({ compact, side, standard, metric, delta });
})();
