(function () {
  'use strict';
  window.ActualGanttAPI = {
    async load(context, signal) {
      const C = window.ActualGanttContract, scope = C.scope(context);
      return C.workspace(await window.APSWorkbenchTransport.read('/api/workbench/v1/actual-gantt', C.transport(scope), { signal, timeout: 20000 }), scope);
    },
    // 附件、CSV 类型与魔数、文件名及其后缀都由 transport.download 核对。
    async export(context, signal) {
      const C = window.ActualGanttContract, T = window.APSWorkbenchTransport;
      return T.download('/api/workbench/v1/actual-gantt/export', C.transport(C.scope(context, true)), { signal, timeout: 60000, types: [T.types.csv] });
    }
  };
})();
