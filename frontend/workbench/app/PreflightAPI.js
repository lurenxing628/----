(function () {
  'use strict';
  function create() {
    const transport = window.APSResourceAPI.create(), batches = window.APSBatchAPI.create(), C = window.PreflightContract;
    return {
      async preferences(signal) {
        return C.preferences(await transport.query('scheduling/preferences', {}, signal));
      },
      async savePreferences(value, signal) {
        const input = C.input(value), current = C.preferences(await transport.query('scheduling/preferences', {}, signal)).data;
        if (current.input !== null && JSON.stringify(C.input(current.input)) === JSON.stringify(input)) return input;
        const request_key = window.APSWorkbenchTransport.requestKey('preferences');
        const receipt = await transport.execute('scheduling/preferences', { request_key, write_token: current.write_context.write_token, input });
        if (JSON.stringify(C.input(receipt.data.input)) !== JSON.stringify(input)) throw C.fail('保存的排产范围与本次选择不一致，请重新检查。');
        return input;
      },
      async preflight(value, signal) {
        const input = C.input(value), result = await transport.preview('scheduling/preflight', input, signal);
        C.result(result, input); return result;
      },
      async list(scope, signal) {
        return window.APSBatchContract.list(await batches.list('batch', scope, signal), scope);
      },
      selection(scope, signal) { return batches.selection(scope, signal); }
    };
  }
  window.PreflightAPI = { create };
})();
