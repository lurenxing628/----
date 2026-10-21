(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string' && value.length > 0;
  const ref = value => typeof value === 'string' && /^[a-f0-9]{48}$/.test(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  const nullable = test => value => value === null || test(value);
  const fields = (value, keys) => object(value) && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
  function time(value) {
    if (typeof value !== 'string' || !/^(?!0000)\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?!000000$)\d{6})?(?![\s\S])/.test(value)) return false;
    const base = value.slice(0, 19), instant = Date.parse(base + 'Z');
    return Number.isFinite(instant) && new Date(instant).toISOString().slice(0, 19) === base;
  }
  const operationCounts = ['operation_count', 'scheduled_operation_count', 'unscheduled_operation_count', 'task_count',
    'invalid_task_count', 'deferred_operation_count', 'ordinary_unscheduled_operation_count'];
  const rowFields = ['batch_ref', 'batch_id', 'planned_finish', 'partial_planned_finish', 'due_date', 'due_state', 'due_issue',
    'completion_state', 'risk', 'schedule_complete', 'is_overdue', 'delay_hours', 'issues', ...operationCounts];
  // The source owns completion, due boundaries and delay calculations. This boundary validates the saved projection.
  function row(value, countsNullable = false) {
    return fields(value, rowFields) && ref(value.batch_ref) && text(value.batch_id)
      && ['overdue', 'on_time', 'unknown', 'not_applicable'].includes(value.risk)
      && ['specified', 'unspecified', 'invalid'].includes(value.due_state)
      && (value.due_issue === null || ['due_date_missing', 'due_date_invalid'].includes(value.due_issue))
      && ['complete', 'deferred', 'incomplete', 'unknown'].includes(value.completion_state)
      && typeof value.schedule_complete === 'boolean' && nullable(time)(value.planned_finish) && nullable(time)(value.partial_planned_finish)
      && (value.due_date === null || typeof value.due_date === 'string') && nullable(number)(value.delay_hours)
      && nullable(value => typeof value === 'boolean')(value.is_overdue)
      && operationCounts.every(key => (countsNullable && key !== 'operation_count' ? nullable(count) : count)(value[key]))
      && Array.isArray(value.issues) && value.issues.every(text);
  }
  const summaryCounts = ['batch_count', 'due_eligible_count', 'excluded_due_count', 'invalid_due_count', 'due_evaluation_count',
    'known_due_count', 'unknown_due_count', 'unknown_count', 'known_overdue_count'];
  const summaryFields = ['state', 'overdue_count', 'total_tardiness_hours', 'known_tardiness_hours', 'known_batch_refs', ...summaryCounts];
  function summary(value) {
    return fields(value, summaryFields) && ['complete', 'partial', 'unavailable', 'not_applicable'].includes(value.state)
      && summaryCounts.every(key => count(value[key])) && nullable(count)(value.overdue_count)
      && ['total_tardiness_hours', 'known_tardiness_hours'].every(key => nullable(number)(value[key]))
      && Array.isArray(value.known_batch_refs) && value.known_batch_refs.every(ref);
  }
  window.DeliveryProjectionContract = Object.freeze({ row, summary, operationCounts });
})();
