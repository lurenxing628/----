(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const fields = (value, keys) => object(value) && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
  const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const nullable = test => value => value === null || test(value);
  const states = ['complete', 'partial', 'unavailable', 'not_applicable'];
  const sources = ['archived_resource_calendar', 'current_transaction_snapshot'];
  const issue = value => object(value) && typeof value.code === 'string' && value.code.length > 0
    && typeof value.message === 'string' && value.message.length > 0;
  const measures = ['available_hours', 'occupied_hours', 'summed_load_hours', 'outside_calendar_hours', 'overlap_hours',
    'utilization_ratio', 'demand_ratio', 'peak_utilization', 'numerator_hours', 'denominator_hours'];
  const windowMeasures = [...measures, 'span_occupied_hours', 'span_summed_hours', 'span_overlap_hours',
    'known_available_hours', 'known_occupied_hours', 'known_summed_load_hours', 'known_utilization_ratio'];
  const windowCounts = ['unknown_days', 'zero_capacity_days', 'task_count', 'operation_count'];
  const windowFlags = ['high_pressure', 'zero_capacity_task', 'conflict'];
  function metricWindow(value) {
    return fields(value, ['state', 'source', 'metric_version', 'issues', ...windowMeasures, ...windowCounts, ...windowFlags])
      && states.includes(value.state) && sources.includes(value.source) && ['available_occupancy_v1', 'decision-resource-v4'].includes(value.metric_version)
      && windowMeasures.every(key => nullable(number)(value[key])) && windowCounts.every(key => nullable(count)(value[key]))
      && windowFlags.every(key => nullable(value => typeof value === 'boolean')(value[key]))
      && Array.isArray(value.issues) && value.issues.every(issue);
  }
  const summaryCounts = ['resource_count', 'used_resource_count', 'known_capacity_count', 'unknown_capacity_count',
    'high_pressure_count', 'known_high_pressure_count', 'zero_capacity_task_count', 'conflict_resource_count', 'unknown_day_resource_count'];
  function summary(value) {
    return fields(value, ['state', 'issues', 'balance_cv', 'balance_state', 'balance_reason', ...measures, ...summaryCounts])
      && states.includes(value.state) && states.includes(value.balance_state) && nullable(number)(value.balance_cv)
      && (value.balance_reason === null || issue(value.balance_reason))
      && measures.every(key => nullable(number)(value[key])) && summaryCounts.every(key => nullable(count)(value[key]))
      && Object.keys(value).filter(key => key.startsWith('known_') && !summaryCounts.includes(key))
        .every(key => nullable(number)(value[key])) && Array.isArray(value.issues) && value.issues.every(issue);
  }
  function common(value, source) {
    return fields(value, ['metric_version', 'source', 'start', 'end', 'time_basis', 'cohort_basis', 'cohort'])
      && ['decision-resource-v3', 'decision-resource-v4'].includes(value.metric_version) && sources.includes(value.source)
      && (!source || value.source === source) && value.time_basis === 'factory_local'
      && typeof value.start === 'string' && typeof value.end === 'string' && value.start <= value.end
      && typeof value.cohort_basis === 'string' && Array.isArray(value.cohort)
      && value.cohort.every(row => object(row) && ['machine', 'operator'].includes(row.kind) && typeof row.ref === 'string')
      && (value.before || value.after ? ['before', 'after'].every(side => object(value[side])
          && ['machine', 'operator'].every(kind => summary(value[side][kind])))
        : ['machine', 'operator'].every(kind => summary(value[kind])));
  }
  window.ResourceProjectionContract = Object.freeze({ window: metricWindow, day: metricWindow, summary, common });
})();
