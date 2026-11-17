import T from './shared/network/transport.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import { object, token32, isDate, failure, checker } from './shared/contract/kit.js';

const states = Object.keys(WorkbenchTerms.run_statuses);
const count = v => Number.isSafeInteger(v) && v >= 0;
const check = checker('读到的排产记录数据不完整，请刷新重试。', { code: 'invalid_response' });
const queryKeys = ['page', 'size', 'state', 'accepted_from', 'accepted_to', 'sort', 'order', 'snapshot_ref'];
function scope(query = {}) {
  check(object(query) && Object.keys(query).every(k => queryKeys.includes(k)), '查询条件里有不认识的项，没有自动忽略。请从侧栏重新打开排产记录。');
  const q = { page: 1, size: 20, state: 'all', sort: 'accepted_at', order: 'desc', ...query };
  check(count(q.page) && q.page >= 1 && q.page <= 1000000 && count(q.size) && q.size >= 1 && q.size <= 50
    && ['all', ...states].includes(q.state) && ['accepted_at', 'started_at', 'finished_at'].includes(q.sort)
    && ['asc', 'desc'].includes(q.order) && (q.snapshot_ref === undefined || token32(q.snapshot_ref)), '筛选、排序或翻页条件无效，请重新设置后查询。');
  if (q.accepted_from !== undefined || q.accepted_to !== undefined) check(isDate(q.accepted_from) && isDate(q.accepted_to)
    && q.accepted_from <= q.accepted_to, '提交日期要成对填写，起日不能晚于止日。');
  Object.keys(q).forEach(k => { if (q[k] === undefined) delete q[k]; }); return q;
}
// 入参是已校验的查询状态（scope() 的产物或由它派生）；返回链接只去掉快照钉，不改动调用方的状态对象。
function returnContext({ snapshot_ref, ...query }) { return query; }
function validateCatalog(v, q) {
  // 翻页和页面记忆都要用本次快照，不能为空。
  check(token32(v.meta.snapshot_ref));
  if (q.snapshot_ref && q.snapshot_ref !== v.meta.snapshot_ref) throw failure(WorkbenchTerms.outcomes.stale, { code: 'snapshot_stale' });
  return v.data;
}
async function catalog(query, signal) {
  const value = await T.read('/api/workbench/v1/scheduling/runs', query, { signal, timeout: 60000 });
  validateCatalog(value, query); return value;
}
const RunHistoryAPI = { catalog, check, scope, returnContext };
export { RunHistoryAPI, catalog, check, scope, returnContext };
export default RunHistoryAPI;
