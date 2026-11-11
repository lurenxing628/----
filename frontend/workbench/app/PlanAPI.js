import APSWorkbenchTransport from './shared/network/transport.js';
import APSPlanContract from './PlanContract.js';

async function catalog(scope = {}, signal) {
  const C = APSPlanContract, query = C.catalogScope(scope);
  return C.catalog(await APSWorkbenchTransport.read('/api/workbench/v1/plans', query, { signal, timeout: 20000 }), query);
}
async function workspace(planRef, scope = {}, signal) {
  const C = APSPlanContract, T = APSWorkbenchTransport, query = C.workspaceScope(planRef, scope);
  const first = C.workspace(await T.read('/api/workbench/v1/plans/' + planRef + '/workspace', query, { signal, timeout: 20000 }), planRef, query);
  if (first.data.tasks_complete === false) {
    const tasks = first.data.tasks, pages = Math.ceil(first.data.task_count / 5000);
    for (let page = 2; page <= pages; page++) {
      const pageQuery = C.tasksScope(planRef, { ...query, snapshot_ref: first.meta.snapshot_ref, page, size: 5000 });
      const next = C.tasksPage(await T.read('/api/workbench/v1/plans/' + planRef + '/tasks', pageQuery, { signal, timeout: 20000 }), first.data, pageQuery);
      tasks.push(...next.data.tasks);
    }
    first.data.tasks_complete = true;
    return first;
  }
  return first;
}
async function ganttGraph(planRef, scope, workspaceData, signal) {
  const C = APSPlanContract, T = APSWorkbenchTransport, query = C.ganttGraphScope(planRef, scope);
  return C.ganttGraph(await T.read('/api/workbench/v1/plans/' + planRef + '/gantt-graph', query, { signal, timeout: 20000 }), workspaceData, query);
}
async function capacity(planRef, scope, workspaceData, signal) {
  const C = APSPlanContract, T = APSWorkbenchTransport, query = C.capacityScope(planRef, scope);
  return C.capacity(await T.read('/api/workbench/v1/plans/' + planRef + '/capacity', query, { signal, timeout: 20000 }), workspaceData, query);
}
async function baseline(planRef, scope, workspaceData, signal) {
  const C = APSPlanContract, T = APSWorkbenchTransport, query = C.baselineScope(planRef, scope);
  const first = C.baselinePage(await T.read('/api/workbench/v1/plans/' + planRef + '/baseline', query, { signal, timeout: 20000 }), workspaceData, query);
  const items = first.data.items;
  let page = first.data.page.number;
  while (first.data.page.has_more && page * query.size < first.data.page.total) {
    page++;
    const nextQuery = C.baselineScope(planRef, { ...query, page });
    const next = C.baselinePage(await T.read('/api/workbench/v1/plans/' + planRef + '/baseline', nextQuery, { signal, timeout: 20000 }), workspaceData, nextQuery, first.data);
    items.push(...next.data.items);
  }
  delete first.data.page;
  first.data.items_complete = first.data.state === 'available';
  return first;
}
async function exportPlan(planRef, scope, signal) {
  // 附件、文件类型与魔数、文件名及其后缀都由 transport.download 核对。
  const T = APSWorkbenchTransport, query = APSPlanContract.exportScope(planRef, scope);
  return T.download('/api/workbench/v1/plans/' + planRef + '/export', query, { signal, timeout: 20000, types: [T.types[query.format]] });
}
const APSPlanAPI = { catalog, workspace, ganttGraph, capacity, baseline, export: exportPlan };
export { APSPlanAPI, catalog, workspace, ganttGraph, capacity, baseline, exportPlan as export };
export default APSPlanAPI;
