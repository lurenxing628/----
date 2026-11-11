import APSResourceContract from './resource-contract.js';
import ActualGanttModel from './ActualGanttModel.js';

const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
const fail = text => { throw APSResourceContract.failure(text); };
function local(value) {
  if (typeof value !== 'string' || !/^(?!0000)\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?!000000$)\d{6})?(?![\s\S])/.test(value)) return false;
  const base = value.slice(0, 19), at = Date.parse(base + 'Z');
  return Number.isFinite(at) && new Date(at).toISOString().slice(0, 19) === base;
}
const scalarKeys = ['range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref'];
const cohortKeys = ['plan_ref', 'source', ...scalarKeys, 'batch_ids'];
function scope(input, exporting = false) {
  const allowed = cohortKeys.concat(['snapshot_ref'], exporting ? ['format', 'local_query', 'late_filter', 'selected_task_ref'] : []);
  if (!object(input) || Reflect.ownKeys(input).some(key => !allowed.includes(key))) fail('现场实际甘特的查询范围里有不认识的项，没有忽略来源条件。');
  const value = { ...input };
  if (!ref(value.plan_ref) || own(value, 'source') && value.source !== 'production') fail('请选择有效的生产计划。');
  for (const [start, end, dateOnly] of [['range_start', 'range_end', false], ['plan_finish_date_from', 'plan_finish_date_to', true]]) {
    const hasStart = own(value, start), hasEnd = own(value, end);
    if (hasStart !== hasEnd || hasStart && (!local(value[start] + (dateOnly ? 'T00:00:00' : '')) || !local(value[end] + (dateOnly ? 'T00:00:00' : '')) || (dateOnly ? value[start] > value[end] : value[start] >= value[end]))) fail('起止范围不完整或时间无效。');
  }
  if (own(value, 'resource_type') !== own(value, 'resource_ref') || own(value, 'resource_ref') && (!['machine', 'operator'].includes(value.resource_type) || !ref(value.resource_ref))) fail('资源范围不完整。');
  if (own(value, 'batch_ids') && (!Array.isArray(value.batch_ids) || value.batch_ids.length > 10000 || value.batch_ids.some(v => typeof v !== 'string' || !v.trim()) || new Set(value.batch_ids).size !== value.batch_ids.length)) fail('批次范围无效。');
  if (own(value, 'snapshot_ref') && (typeof value.snapshot_ref !== 'string' || !value.snapshot_ref)) fail('数据版本无效。');
  if (exporting && (value.format !== 'csv' || !value.snapshot_ref || own(value, 'local_query') && (typeof value.local_query !== 'string' || value.local_query.length > 200) || own(value, 'late_filter') && !Object.keys(ActualGanttModel.lateLabels).includes(value.late_filter) || own(value, 'selected_task_ref') && !ref(value.selected_task_ref))) fail('导出格式、数据版本或本地筛选无效。');
  return value;
}
function scopeMatches(s, query) {
  if (!object(s) || s.kind !== 'actual_gantt' || s.source !== 'production'
    || own(query, 'source') && query.source !== 'production' || s.plan_ref !== query.plan_ref
    || scalarKeys.some(key => s[key] !== (own(query, key) ? query[key] : null))
    || !Array.isArray(s.batch_ids)) return false;
  const batches = own(query, 'batch_ids') ? query.batch_ids : [];
  if (!Array.isArray(batches) || s.batch_ids.length !== batches.length) return false;
  const expected = new Set(batches);
  return expected.size === batches.length && new Set(s.batch_ids).size === batches.length
    && s.batch_ids.every(id => expected.has(id));
}
function workspace(result, query) {
  // 成功信封（meta 五键、warnings、as_of）已由 transport.read 校验；导出与刷新要钉住同一份快照。
  const d = result.data, meta = result.meta;
  if (meta.snapshot_ref === null || query.snapshot_ref && query.snapshot_ref !== meta.snapshot_ref) fail('读到的现场实际甘特数据不完整，或者数据已更新。请刷新后重试。');
  if (!d.plan || d.plan.plan_ref !== query.plan_ref || !d.plan.capabilities.view
    || !scopeMatches(d.scope, query)
    || !Array.isArray(d.items) || d.items_complete !== true) fail('读到的现场实际甘特范围不完整，请刷新重试。');
  return result;
}
function transport(value) { const result = { ...value }; if (result.batch_ids) result.batch_ids = JSON.stringify(result.batch_ids); return result; }
const ActualGanttContract = { scope, workspace, transport, local, ref };
export { ActualGanttContract, scope, workspace, transport, local, ref };
export default ActualGanttContract;
