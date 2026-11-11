import RunHistoryAPI from './RunHistoryAPI.js';
import WorkbenchFormat from './WorkbenchFormat.js';
import APSWorkbenchTransport from './shared/network/transport.js';

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
// 返回位置与条件明细只读，并随 onNavigate 经 history.pushState 结构化克隆，不另做深拷贝。
const states = ['all', 'queued', 'running', 'complete', 'partial', 'failed', 'interrupted', 'committed'];
const queryKeys = ['timeline', 'date_from', 'date_to', 'metric_keys', 'comparison', 'reference_run_ref', 'selected_entry_ref', 'range_start', 'range_end', 'resource_window_days', 'state', 'sort', 'order', 'page', 'size', 'condition_page', 'condition_size', 'snapshot_ref'];
// 默认指标列表直接放进每份默认查询，冻结后谁也不能原地改它；切换指标一律生成新数组。
const defaultMetrics = Object.freeze(['overdue_count', 'total_tardiness_hours', 'makespan_hours', 'elapsed_seconds']);
const sourceLabels = { run: '排产运行', candidate_adoption: '候选方案采用', trial_adoption: '试调方案采用' };
const sourceLabel = value => sourceLabels[typeof value === 'string' ? value : value.source_kind];
const windowMetric = definition => ['fixed_resource_window', 'fixed_changeover_window'].includes(definition.scope);
const sameMetricDefinition = (a, b) => a.unit === b.unit && a.metric_version === b.metric_version && a.scope === b.scope;
const entryRef = value => typeof value === 'string' && /^(?:run:[a-f0-9]{48}|adoption:[a-f0-9]{32})$/.test(value);
const runRef = value => typeof value === 'string' && /^[a-f0-9]{48}$/.test(value);
const timeKey = value => value.slice(0, 19) + '.' + (value.split('.')[1] || '').padEnd(6, '0');

function page(value, query, prefix = '') {
  return object(value) && value.number === query[prefix + 'page'] && value.size === query[prefix + 'size'];
}
function scope(value = {}) {
  check(object(value) && Object.keys(value).every(key => queryKeys.includes(key)), '历史筛选含不支持的项，请重新选择。');
  const q = { timeline: 'run', date_from: null, date_to: null, metric_keys: defaultMetrics, comparison: 'observed', reference_run_ref: null, selected_entry_ref: null,
    range_start: null, range_end: null, resource_window_days: 7, state: 'all', sort: 'occurred_at', order: 'desc', page: 1, size: 20, condition_page: 1, condition_size: 20, snapshot_ref: null, ...value };
  q.metric_keys = typeof q.metric_keys === 'string' ? q.metric_keys.split(',') : q.metric_keys;
  check(['run', 'official'].includes(q.timeline) && ['observed', 'same_conditions'].includes(q.comparison) && states.includes(q.state) && q.sort === 'occurred_at' && ['asc', 'desc'].includes(q.order), '请选择有效的时间线、阅读方式、状态和排序。');
  check(Array.isArray(q.metric_keys) && q.metric_keys.length >= 1 && q.metric_keys.length <= 100 && q.metric_keys.every(key => typeof key === 'string' && /^[a-z][a-z0-9_]{0,79}$/.test(key)) && new Set(q.metric_keys).size === q.metric_keys.length, '请选择有效的历史指标。');
  check(['page', 'condition_page'].every(key => Number.isSafeInteger(q[key]) && q[key] >= 1 && q[key] <= 1000000)
    && ['size', 'condition_size'].every(key => [20, 50].includes(q[key])) && Number.isSafeInteger(q.resource_window_days) && q.resource_window_days >= 1 && q.resource_window_days <= 366, '历史页码、每页数量或资源窗口天数无效。');
  check(q.reference_run_ref === null || runRef(q.reference_run_ref), '请选择有效的基准运行。');
  check(q.selected_entry_ref === null || entryRef(q.selected_entry_ref), '请选择有效的历史条目。');
  check(q.snapshot_ref === null || typeof q.snapshot_ref === 'string' && q.snapshot_ref.length > 0 && q.snapshot_ref.length <= 512, '历史快照无效，请刷新历史。');
  const H = RunHistoryAPI;
  check(q.date_from === null && q.date_to === null || H.date(q.date_from) && H.date(q.date_to) && q.date_from <= q.date_to, '时间线日期须成对填写，开始日期须早于或等于结束日期。');
  check(q.range_start === null && q.range_end === null || H.time(q.range_start) && H.time(q.range_end) && timeKey(q.range_start) < timeKey(q.range_end), '资源共同窗口须成对填写，结束须晚于开始。');
  return q;
}
function check(value, message = '历史资料读取不完整，请刷新后重试。') {
  if (!value) throw Object.assign(new Error(message), { code: 'invalid_response' });
}
function returnState(origin = {}) {
  check(object(origin), '历史返回位置无效，请重新打开排产记录。');
  const value = origin.return_decision_history_context || origin.return_decision_context && origin.return_decision_context.return_decision_history_context
    || origin.source === 'run_history' && origin.history_topic === 'decision_history' && origin.decision_history_context;
  if (!value) return null;
  check(object(value) && object(value.query), '历史返回条件无效，请重新打开排产记录。');
  return value;
}
function historyContext(origin = {}) {
  const value = returnState(origin);
  return { source: 'run_history', ...(origin.history_query ? { history_query: origin.history_query } : {}),
    ...(value ? { history_topic: 'decision_history', decision_history_context: value } : {}) };
}
function context(value = {}) {
  check(object(value) && Object.keys(value).every(key => ['query', 'selected_entry_ref', 'reference_entry_ref', 'metric_key', 'detail_queries'].includes(key)), '历史页面的返回条件无效，请从排产记录重新打开。');
  const query = scope(value.query), selected = value.selected_entry_ref === undefined ? query.selected_entry_ref : value.selected_entry_ref;
  const reference = value.reference_entry_ref === undefined ? query.reference_run_ref && 'run:' + query.reference_run_ref : value.reference_entry_ref;
  check(selected === null || entryRef(selected), '选中历史条目的编号无效。');
  check(reference === null || typeof reference === 'string' && /^run:[a-f0-9]{48}$/.test(reference), '历史对照的基准运行无效。');
  check(selected === query.selected_entry_ref && reference === (query.reference_run_ref && 'run:' + query.reference_run_ref), '历史选择与查询条件不一致，请重新打开历史。');
  const metric = value.metric_key || query.metric_keys[0]; check(query.metric_keys.includes(metric), '趋势指标不在当前指标列表中。');
  check(value.detail_queries === undefined || object(value.detail_queries), '条件明细的返回位置无效。');
  return { query, selected_entry_ref: selected, reference_entry_ref: reference, metric_key: metric, detail_queries: value.detail_queries === undefined ? {} : value.detail_queries };
}
function serialized(query) {
  return new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => [key, key === 'metric_keys' ? value.join(',') : value])));
}
function _history(payload, q) {
  // 成功信封（meta 五键、warnings 形状、as_of）已由 transport.read 校验；历史分页与导出要钉住同一份快照。
  check(payload.meta.snapshot_ref !== null);
  if (q.snapshot_ref && payload.meta.snapshot_ref !== q.snapshot_ref) throw Object.assign(new Error('历史资料已更新，请刷新当前条件后继续查看。'), { code: 'snapshot_stale' });
  const d = payload.data;
  const filterKeys = queryKeys.filter(key => key !== 'snapshot_ref');
  check(d.history_version === 'decision-history-v1' && object(d.filters) && page(d.page, q)
    && object(d.selection)
    && object(d.comparison) && d.comparison.mode === q.comparison && object(d.comparison.conditions) && page(d.comparison.conditions.page, q, 'condition_')
    && object(d.resource_window));
  for (const key of filterKeys) {
    const left = d.filters[key], right = q[key];
    check(['range_start', 'range_end'].includes(key) && left !== null && right !== null ? RunHistoryAPI.time(left) && timeKey(left) === timeKey(right) : JSON.stringify(left) === JSON.stringify(right), '历史返回的筛选条件已变化，请重新查询。');
  }
  if (d.selection.entry !== null) check(object(d.selection.entry) && q.selected_entry_ref !== null && d.selection.entry.entry_ref === q.selected_entry_ref, '历史选中条目已变化，请重新选择。');
  else check(q.selected_entry_ref === null, '选中的历史条目未返回，请刷新当前条件。');
  if (d.selection.reference !== null) check(object(d.selection.reference) && q.reference_run_ref !== null && d.selection.reference.entry_ref === 'run:' + q.reference_run_ref, '历史基准运行已变化，请重新选择。');
  else check(q.reference_run_ref === null, '基准运行未返回，请重新选择。');
  check(d.resource_window.mode === (q.range_start ? 'absolute' : 'fixed_days') && d.resource_window.anchor === (q.range_start ? 'common_absolute_window' : 'source_start')
    && (q.range_start ? d.resource_window.start !== null && d.resource_window.end !== null && timeKey(d.resource_window.start) === timeKey(q.range_start) && timeKey(d.resource_window.end) === timeKey(q.range_end) : d.resource_window.days === q.resource_window_days), '历史资源窗口与查询条件不一致，请重新查询。');
  return d;
}
function numberText(value, unit, precision = 3) {
  if (value === null) return '未知';
  return unit === '%' ? WorkbenchFormat.percent(value, { digits: precision, trim: true }) : WorkbenchFormat.number(value, { digits: precision, trim: true }) + (unit ? ' ' + unit : '');
}
function metricText(value, definition) {
  return value.value === null ? value.state === 'not_applicable' ? '不适用' : '未知' : numberText(value.value, value.unit, definition.precision);
}
async function read(query = {}, signal) {
  const q = scope(query), result = await APSWorkbenchTransport.read('/api/workbench/v1/scheduling/decision-history', Object.fromEntries(serialized(q)), { signal, timeout: 60000 });
  _history(result, q); return result;
}
// 附件、文件类型与魔数、文件名及其后缀由 transport.download 核对；这里只核对快照与行数两个业务头。
async function historyExport(query, snapshotRef, format, signal, section = 'entries') {
  check(['csv', 'xlsx'].includes(format) && ['entries', 'conditions', 'configurations', 'all'].includes(section) && (section !== 'all' || format === 'xlsx'), '请选择有效的历史导出格式和内容。');
  const q = scope({ ...query, snapshot_ref: snapshotRef }); check(typeof q.snapshot_ref === 'string', '请读取历史资料后再导出。');
  const params = { ...q, format, section };
  ['page', 'size', 'condition_page', 'condition_size'].forEach(key => delete params[key]);
  const T = APSWorkbenchTransport, file = await T.download('/api/workbench/v1/scheduling/decision-history/export', Object.fromEntries(serialized(params)), { signal, timeout: 60000, types: [T.types[format]] });
  check(file.header('X-Workbench-Snapshot-Ref') === q.snapshot_ref, '历史快照已变化，请刷新后重新导出。');
  const rows = file.header('X-Workbench-Row-Count');
  check(rows !== null && /^[0-9]+$/.test(rows) && Number.isSafeInteger(Number(rows)), '历史导出文件内容不完整，请重新下载。');
  return { filename: file.filename, blob: file.blob, row_count: Number(rows) };
}
const DecisionHistoryAPI = { check, returnState, historyContext, scope, context, serialized, states, sourceLabel, windowMetric, sameMetricDefinition, read, historyExport, numberText, metricText };
export { DecisionHistoryAPI, check, returnState, historyContext, scope, context, serialized, states, sourceLabel, windowMetric, sameMetricDefinition, read, historyExport, numberText, metricText };
export default DecisionHistoryAPI;
