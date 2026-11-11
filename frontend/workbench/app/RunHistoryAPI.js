import APSWorkbenchTransport from './shared/network/transport.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const T = APSWorkbenchTransport;
const states = ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'];
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
function check(value, message = '读到的排产记录数据不完整，请刷新重试。') {
  if (!value) { const error = new Error(message); error.code = 'invalid_response'; throw error; }
}
function date(v) {
  if (!text(v) || !/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(v)) return false;
  const n = Date.parse(v + 'T00:00:00Z'); return Number.isFinite(n) && new Date(n).toISOString().slice(0, 10) === v;
}
function time(v) { return text(v) && date(v.slice(0, 10)) && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?$/.test(v); }
const queryKeys = ['page', 'size', 'state', 'accepted_from', 'accepted_to', 'sort', 'order', 'snapshot_ref'];
function scope(query = {}) {
  check(object(query) && Object.keys(query).every(k => queryKeys.includes(k)), '查询条件里有不认识的项，没有自动忽略。请从侧栏重新打开排产记录。');
  const q = { page: 1, size: 20, state: 'all', sort: 'accepted_at', order: 'desc', ...query };
  check(count(q.page) && q.page >= 1 && q.page <= 1000000 && count(q.size) && q.size >= 1 && q.size <= 50
    && ['all', ...states].includes(q.state) && ['accepted_at', 'started_at', 'finished_at'].includes(q.sort)
    && ['asc', 'desc'].includes(q.order) && (q.snapshot_ref === undefined || token(q.snapshot_ref)), '筛选、排序或翻页条件无效，请重新设置后查询。');
  if (q.accepted_from !== undefined || q.accepted_to !== undefined) check(date(q.accepted_from) && date(q.accepted_to)
    && q.accepted_from <= q.accepted_to, '提交日期要成对填写，起日不能晚于止日。');
  Object.keys(q).forEach(k => { if (q[k] === undefined) delete q[k]; }); return q;
}
// 入参是已校验的查询状态（scope() 的产物或由它派生）；返回链接只去掉快照钉，不改动调用方的状态对象。
function returnContext({ snapshot_ref, ...query }) { return query; }
// q 是已校验的查询状态（同上），这里只核对返回与它一致。
function validateCatalog(v, q) {
  // 翻页和页面记忆都要用本次快照，不能为空。
  check(token(v.meta.snapshot_ref));
  if (q.snapshot_ref && q.snapshot_ref !== v.meta.snapshot_ref) {
    const error = new Error(WorkbenchTerms.outcomes.stale); error.code = 'snapshot_stale'; throw error;
  }
  const d = v.data;
  check(d.state === q.state && d.sort === q.sort && d.order === q.order
    && object(d.page) && d.page.number === q.page && d.page.size === q.size
    && object(d.time_scope) && d.time_scope.accepted_from === (q.accepted_from || null) && d.time_scope.accepted_to === (q.accepted_to || null));
  return d;
}
async function catalog(query, signal) {
  const value = await T.read('/api/workbench/v1/scheduling/runs', query, { signal, timeout: 60000 });
  validateCatalog(value, query); return value;
}
const RunHistoryAPI = { catalog, check, scope, returnContext, ref, date, time, states };
export { RunHistoryAPI, catalog, check, scope, returnContext, ref, date, time, states };
export default RunHistoryAPI;
