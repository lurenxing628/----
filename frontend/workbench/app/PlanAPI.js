(function () {
  'use strict';
  // Load transport.js and PlanContract.js first.
  window.APSPlanAPI = {
    async catalog(scope = {}, signal) {
      const C = window.APSPlanContract, query = C.catalogScope(scope);
      return C.catalog(await window.APSWorkbenchTransport.read('/api/workbench/v1/plans', query, { signal, timeout: 20000 }), query);
    },
    async workspace(planRef, scope = {}, signal) {
      const C = window.APSPlanContract, query = C.workspaceScope(planRef, scope);
      return C.workspace(await window.APSWorkbenchTransport.read('/api/workbench/v1/plans/' + planRef + '/workspace', query, { signal, timeout: 20000 }), planRef, query);
    },
    async export(planRef, scope, signal) {
      // 附件、文件类型与魔数、文件名及其后缀都由 transport.download 核对。
      const T = window.APSWorkbenchTransport, query = window.APSPlanContract.exportScope(planRef, scope);
      return T.download('/api/workbench/v1/plans/' + planRef + '/export', query, { signal, timeout: 20000, types: [T.types[query.format]] });
    }
  };
})();
