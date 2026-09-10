(function () {
  'use strict';
  // Load resource-contract.js, resource-api.js and PlanContract.js first.
  function create() {
    const base = window.APSResourceAPI.create(), C = window.APSPlanContract;
    return {
      async catalog(scope = {}, signal) {
        const query = C.catalogScope(scope);
        return C.catalog(await base.query('plans', query, signal), query);
      },
      async workspace(planRef, scope = {}, signal) {
        const query = C.workspaceScope(planRef, scope);
        return C.workspace(await base.query('plans/' + planRef + '/workspace', query, signal), planRef, query);
      },
      async export(planRef, scope, signal) {
        const query = C.exportScope(planRef, scope);
        return C.download(await base.download('plans/' + planRef + '/export', query, signal), query.format);
      }
    };
  }
  window.APSPlanAPI = { create };
})();
