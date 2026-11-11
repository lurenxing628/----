function defaultPlan(plans) {
  const current = plans.filter(plan => plan.is_current_official && plan.capabilities.view && plan.plan_ref);
  return current.length === 1 ? current[0] : null;
}
const PlanSelectionModel = { defaultPlan };
export { PlanSelectionModel, defaultPlan };
export default PlanSelectionModel;
