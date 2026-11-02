(function () {
  'use strict';
  // 正式计划导航上下文的唯一接收边界：实际甘特、值班台、计划页自己的快照和深链打开正式计划都经这里。
  // 不认识的键整条拒绝，不静默丢弃其他页面的协议。范围只由 PlanContract.workspaceScope 在读取时校验，
  // return_decision_* 由使用处的 DecisionHistoryAPI 校验，返回页面是否登记由 WorkbenchNavigation.navigate 校验。
  const C = window.APSResourceContract;
  const keys = ['plan_ref', 'range_start', 'range_end', 'query', 'selected_task_ref', 'selected_task_side', 'selected_batch_ref',
    'projection_tab', 'projection_page', 'resource_kind', 'return_to', 'return_decision_context', 'return_decision_history_context'];
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  function accept(context) {
    const task = C.own(context, 'selected_task_ref'), back = context.return_to;
    if (!Reflect.ownKeys(context).every(key => keys.includes(key))
        || C.own(context, 'query') && typeof context.query !== 'string'
        || task && !ref(context.selected_task_ref)
        || C.own(context, 'selected_batch_ref') && (task || !ref(context.selected_batch_ref))
        || C.own(context, 'selected_task_side') && (!task || !['current', 'before'].includes(context.selected_task_side))
        || C.own(context, 'return_to') && !(C.object(back) && Reflect.ownKeys(back).length === 2 && C.own(back, 'view') && C.own(back, 'context')))
      throw C.failure('打开计划的定位信息无效，没有改选其他计划或工序。请从来源页面重新打开。');
    return context;
  }
  window.APSPlanNavigation = { accept };
})();
