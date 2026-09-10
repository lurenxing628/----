(function () {
  'use strict';
  function create() {
    const transport = window.APSResourceAPI.create(), batches = window.APSBatchAPI.create(), C = window.PreflightContract;
    return {
      async preflight(value, signal) {
        const input = C.input(value), result = await transport.preview('scheduling/preflight', input, signal);
        C.result(result, input); return result;
      },
      async list(scope, signal) {
        return window.APSBatchContract.list(await batches.list('batch', scope, signal), scope);
      },
      async selection(scope, signal) {
        const result = await batches.selection(scope, signal); C.selection(result, scope.snapshot_ref); return result;
      }
    };
  }
  window.PreflightAPI = { create };
})();
