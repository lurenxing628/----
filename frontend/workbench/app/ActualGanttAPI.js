import ActualGanttContract from './ActualGanttContract.js';
import APSWorkbenchTransport from './shared/network/transport.js';

async function load(context, signal) {
  const C = ActualGanttContract, scope = C.scope(context);
  return C.workspace(await APSWorkbenchTransport.read('/api/workbench/v1/actual-gantt', C.transport(scope), { signal, timeout: 20000 }), scope);
}
// 附件、CSV 类型与魔数、文件名及其后缀都由 transport.download 核对。
async function exportGantt(context, signal) {
  const C = ActualGanttContract, T = APSWorkbenchTransport;
  return T.download('/api/workbench/v1/actual-gantt/export', C.transport(C.scope(context, true)), { signal, timeout: 60000, types: [T.types.csv] });
}
const ActualGanttAPI = { load, export: exportGantt };
export { ActualGanttAPI, load, exportGantt as export };
export default ActualGanttAPI;
