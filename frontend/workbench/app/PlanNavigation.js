import C from './resource-contract.js';
import { failure, ref48 } from './shared/contract/kit.js';

// 正式计划定位的取值检查：实际甘特、值班台、计划页自己的快照和深链打开正式计划都经这里。
// 键集、互斥与 return_to 已由 WorkbenchNavigation.admit 按受控导航声明准入；范围只由 PlanContract.workspaceScope 在读取时校验。
function accept(context) {
  if (C.own(context, 'query') && typeof context.query !== 'string'
      || C.own(context, 'selected_task_ref') && !ref48(context.selected_task_ref)
      || C.own(context, 'selected_batch_ref') && !ref48(context.selected_batch_ref)
      || C.own(context, 'selected_task_side') && !['current', 'before'].includes(context.selected_task_side))
    throw failure('打开计划的定位信息无效，没有改选其他计划或工序。请从来源页面重新打开。');
  return context;
}
const APSPlanNavigation = { accept };
export { APSPlanNavigation, accept };
export default APSPlanNavigation;
