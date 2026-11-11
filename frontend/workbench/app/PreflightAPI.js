import APSResourceAPI from './resource-api.js';
import APSBatchAPI from './BatchAPI.js';
import PreflightContract from './PreflightContract.js';
import APSWorkbenchTransport from './shared/network/transport.js';
import { equal } from './shared/session/pending-store.js';
import APSBatchContract from './BatchContract.js';

function create() {
  const transport = APSResourceAPI.create(), batches = APSBatchAPI.create(), C = PreflightContract;
  return {
    async preferences(signal) {
      return C.preferences(await transport.query('scheduling/preferences', {}, signal));
    },
    async savePreferences(value, signal) {
      const input = C.input(value), current = C.preferences(await transport.query('scheduling/preferences', {}, signal)).data;
      if (current.input !== null && equal(current.input, input)) return input;
      const request_key = APSWorkbenchTransport.requestKey('preferences');
      const receipt = await transport.execute('scheduling/preferences', { request_key, write_token: current.write_context.write_token, input });
      if (!equal(receipt.data.input, input)) throw C.fail('保存的排产范围与本次选择不一致，请重新检查。');
      return input;
    },
    async preflight(value, signal) {
      const input = C.input(value), result = await transport.preview('scheduling/preflight', input, signal);
      C.result(result, input); return result;
    },
    async list(scope, signal) {
      return APSBatchContract.list(await batches.list('batch', scope, signal), scope);
    },
    selection(scope, signal) { return batches.selection(scope, signal); }
  };
}
const PreflightAPI = { create };
export { PreflightAPI, create };
export default PreflightAPI;
