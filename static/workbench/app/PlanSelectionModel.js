(function () {
  'use strict';

  function defaultPlan(plans, planRef, context = {}) {
    if (planRef || Object.keys(context).length) return null;
    const current = plans.filter(plan => plan.is_current_official && plan.capabilities.view && plan.plan_ref);
    return current.length === 1 ? current[0] : null;
  }
  window.PlanSelectionModel = {
    defaultPlan
  };
})();
