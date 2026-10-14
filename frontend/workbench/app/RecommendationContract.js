(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string', reference = value => text(value) && /^[a-f0-9]{48}$/.test(value);
  const numeric = value => value === null || typeof value === 'number' && Number.isFinite(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const issue = value => object(value) && text(value.code) && text(value.message);
  const tabs = ['batches', 'operations', 'resources', 'preparation', 'changeovers'];
  function entry(value) {
    return object(value) && ['metric_key', 'label', 'unit', 'scope', 'source', 'metric_version', 'text'].every(key => text(value[key]))
      && count(value.precision) && ['value', 'reference_value', 'selected_value'].every(key => numeric(value[key]))
      && ['comparable', 'different_coverage', 'unavailable', 'not_applicable'].includes(value.state)
      && ['better', 'worse', 'equal', 'neutral'].includes(value.direction) && (value.reason === null || issue(value.reason))
      && (value.compared_batch_count === null || count(value.compared_batch_count))
      && Array.isArray(value.sample_compared_batch_refs) && value.sample_compared_batch_refs.length <= 3 && value.sample_compared_batch_refs.every(reference)
      && Array.isArray(value.supporting_refs) && value.supporting_refs.length <= 3 && value.supporting_refs.every(target => object(target)
        && text(target.kind) && (target.ref === null || reference(target.ref)) && reference(target.candidate_ref) && object(target.drill)
        && (target.side === undefined || ['selected', 'reference'].includes(target.side))
        && reference(target.drill.run_ref) && reference(target.drill.candidate_ref)
        && ['candidates', 'admission_official'].includes(target.drill.comparison_mode)
        && (target.drill.comparison_tab === undefined || tabs.includes(target.drill.comparison_tab) && object(target.drill.detail_query)));
  }
  window.RecommendationContract = Object.freeze({ entry });
})();
