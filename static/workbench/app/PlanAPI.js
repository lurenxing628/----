(function () {
  'use strict';

  // Load resource-contract.js, resource-api.js and PlanContract.js first.
  function create() {
    const base = window.APSResourceAPI.create(),
      C = window.APSPlanContract;
    return window.APSReadBoundary.verified({
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
    }, ['catalog', 'workspace']);
  }
  function adapter(value) {
    const C = window.APSPlanContract;
    return window.APSReadBoundary.checked(value, {
      catalog: (result, scope = {}) => C.catalog(result, C.catalogScope(scope)),
      workspace: (result, planRef, scope = {}) => C.workspace(result, planRef, C.workspaceScope(planRef, scope))
    });
  }
  window.APSPlanAPI = {
    create,
    adapter
  };
})();
