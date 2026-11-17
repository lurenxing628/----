import ActualGanttContract from './ActualGanttContract.js';
import APSWorkbenchTransport from './shared/network/transport.js';

// 范围（含批次列表）放在 POST 请求体里读：批次多时查询串会超出请求行长度。
async function load(context, signal) {
  const C = ActualGanttContract, scope = C.scope(context);
  return C.workspace(await APSWorkbenchTransport.preview('/api/workbench/v1/actual-gantt', scope, { signal, timeout: 20000 }), scope);
}
// 附件、CSV 类型与魔数、文件名及其后缀都由 transport.download 核对。
async function exportGantt(context, signal) {
  const C = ActualGanttContract, T = APSWorkbenchTransport;
  return T.download('/api/workbench/v1/actual-gantt/export', {}, { signal, timeout: 60000, types: [T.types.csv], body: C.scope(context, true) });
}
const ActualGanttAPI = { load, export: exportGantt };
export { ActualGanttAPI, load, exportGantt as export };
export default ActualGanttAPI;
