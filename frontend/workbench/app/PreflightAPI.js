import APSResourceAPI from './resource-api.js';
import APSBatchAPI from './BatchAPI.js';
import C from './PreflightContract.js';
import APSWorkbenchTransport from './shared/network/transport.js';
import { equal } from './shared/session/pending-store.js';
import APSBatchContract from './BatchContract.js';
import { failure } from './shared/contract/kit.js';

// 排产检查只读写排产偏好、发预检，不留待确认记录：借用基础资料命名空间的读写通道，不另立待确认键。
const transport = APSResourceAPI.forNamespace('resources');
const PreflightAPI = {
  preferences(signal) { return transport.query('scheduling/preferences', {}, signal); },
  async savePreferences(value, signal) {
    const input = C.input(value), current = (await transport.query('scheduling/preferences', {}, signal)).data;
    if (current.input !== null && equal(current.input, input)) return input;
    const request_key = APSWorkbenchTransport.requestKey('preferences');
    const receipt = await transport.execute('scheduling/preferences', { request_key, write_token: current.write_context.write_token, input });
    // 保存已经执行：回执对不上时偏好可能已经写入，结果未知。
    if (!equal(receipt.data.input, input)) throw failure('保存的排产范围与本次选择不一致，请重新检查。', { committed: 'unknown' });
    return input;
  },
  async preflight(value, signal) {
    const input = C.input(value), result = await transport.preview('scheduling/preflight', input, signal);
    C.result(result, input); return result;
  },
  async list(scope, signal) {
    return APSBatchContract.list(await APSBatchAPI.list('batch', scope, signal), scope);
  },
  selection(scope, signal) { return APSBatchAPI.selection(scope, signal); }
};
export { PreflightAPI };
export default PreflightAPI;
