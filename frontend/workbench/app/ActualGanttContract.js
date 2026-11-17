import ActualGanttModel from './ActualGanttModel.js';
import Hours from './shared/hours.js';
import { object, nonempty, ref48, isDate, localTime, failure } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：计划与范围和查询一致、数据版本没变，报工精确工时已解析成 shared/hours.js 的精确量。
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const scalarKeys = ['range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref'];
const cohortKeys = ['plan_ref', 'source', ...scalarKeys, 'batch_ids'];
function scope(input, exporting = false) {
  const allowed = cohortKeys.concat(['snapshot_ref'], exporting ? ['format', 'local_query', 'late_filter', 'selected_task_ref'] : []);
  if (!object(input) || Reflect.ownKeys(input).some(key => !allowed.includes(key))) throw failure('现场实际甘特的查询范围里有不认识的项，没有忽略来源条件。');
  const value = { ...input };
  if (!ref48(value.plan_ref) || own(value, 'source') && value.source !== 'production') throw failure('请选择有效的生产计划。');
  for (const [start, end, dateOnly] of [['range_start', 'range_end', false], ['plan_finish_date_from', 'plan_finish_date_to', true]]) {
    const hasStart = own(value, start), hasEnd = own(value, end);
    if (hasStart !== hasEnd || hasStart && (!(dateOnly ? isDate : localTime)(value[start]) || !(dateOnly ? isDate : localTime)(value[end]) || (dateOnly ? value[start] > value[end] : value[start] >= value[end]))) throw failure('起止范围不完整或时间无效。');
  }
  if (own(value, 'resource_type') !== own(value, 'resource_ref') || own(value, 'resource_ref') && (!['machine', 'operator'].includes(value.resource_type) || !ref48(value.resource_ref))) throw failure('资源范围不完整。');
  if (own(value, 'batch_ids') && (!Array.isArray(value.batch_ids) || value.batch_ids.some(v => typeof v !== 'string' || !v.trim()) || new Set(value.batch_ids).size !== value.batch_ids.length)) throw failure('批次范围无效。');
  if (own(value, 'snapshot_ref') && !nonempty(value.snapshot_ref)) throw failure('数据版本无效。');
  if (exporting && (value.format !== 'csv' || !value.snapshot_ref || own(value, 'local_query') && (typeof value.local_query !== 'string' || value.local_query.length > 200) || own(value, 'late_filter') && !Object.keys(ActualGanttModel.lateLabels).includes(value.late_filter) || own(value, 'selected_task_ref') && !ref48(value.selected_task_ref))) throw failure('导出格式、数据版本或本地筛选无效。');
  return value;
}
function scopeMatches(s, query) {
  if (!object(s) || s.kind !== 'actual_gantt' || s.source !== 'production'
    || own(query, 'source') && query.source !== 'production' || s.plan_ref !== query.plan_ref
    || scalarKeys.some(key => s[key] !== (own(query, key) ? query[key] : null))
    || !Array.isArray(s.batch_ids)) return false;
  const batches = own(query, 'batch_ids') ? query.batch_ids : [];
  if (s.batch_ids.length !== batches.length) return false;
  const expected = new Set(batches);
  return expected.size === batches.length && new Set(s.batch_ids).size === batches.length
    && s.batch_ids.every(id => expected.has(id));
}
// 报工精确工时只在这里准入一次：规范十进制串解析成 shared/hours.js 的精确量，未知仍为 null；之后的分组合计只用这个精确量。
function admittedReport(report) {
  const text = report.effective_processing_hours_exact;
  if (text === null) return report;
  const exact = Hours.parseHours(text);
  if (!exact) throw failure('读到的报工工时格式不对，请刷新重试。');
  return { ...report, effective_processing_hours_exact: exact };
}
function workspace(result, query) {
  // 成功信封（meta 五键、warnings、as_of）已由 transport.preview 校验；导出与刷新要钉住同一份快照。
  const d = result.data, meta = result.meta;
  if (meta.snapshot_ref === null || query.snapshot_ref && query.snapshot_ref !== meta.snapshot_ref) throw failure('读到的现场实际甘特数据不完整，或者数据已更新。请刷新后重试。');
  if (!d.plan || d.plan.plan_ref !== query.plan_ref || !d.plan.capabilities.view
    || !scopeMatches(d.scope, query)
    || !Array.isArray(d.items) || d.items_complete !== true) throw failure('读到的现场实际甘特范围不完整，请刷新重试。');
  const items = d.items.map(item => item.execution === null ? item
    : { ...item, execution: { ...item.execution, reports: item.execution.reports.map(admittedReport) } });
  return { ...result, data: { ...d, items } };
}
const ActualGanttContract = { scope, workspace };
export { ActualGanttContract, scope, workspace };
export default ActualGanttContract;
