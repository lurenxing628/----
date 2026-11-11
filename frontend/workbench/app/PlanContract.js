import APSResourceContract from './resource-contract.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const C = APSResourceContract;
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const token = value => typeof value === 'string' && value.length > 0;
const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
const same = (a, b) => object(a) && object(b) && Object.keys(b).every(key => own(a, key) && a[key] === b[key]);
function localTime(value) {
  if (typeof value !== 'string' || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.(?!000000$)[0-9]{6})?(?![\s\S])/.test(value)) return false;
  const [year, month, day, hour, minute, second] = value.slice(0, 19).split(/[-T:]/).map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1]
    && hour < 24 && minute < 60 && second < 60;
}
function parameters(scope, allowed) {
  if (!object(scope) || Object.keys(scope).some(key => !allowed.includes(key)))
    throw C.failure('查询条件不对，这次没有读取计划。筛选条件没有变，请点「刷新」重试。');
  const query = { ...scope };
  for (const key of ['cursor', 'snapshot_ref']) {
    if (own(query, key) && !token(query[key])) throw C.failure('翻页位置已失效，请回到第 1 页重新查询。');
  }
  return query;
}
function catalogScope(scope = {}) {
  const query = parameters(scope, ['collection', 'size', 'cursor', 'snapshot_ref']);
  if (!own(query, 'collection')) query.collection = 'history';
  if (!own(query, 'size')) query.size = 20;
  if (query.collection !== 'history' || !Number.isSafeInteger(query.size) || query.size < 1 || query.size > 50)
    throw C.failure('计划列表只能按历史版本查看，每页 1 至 50 条。这次没有读取，请点「刷新」重试。');
  return query;
}
function workspaceScope(planRef, scope = {}) {
  if (!ref(planRef)) throw C.failure('这条计划记录已失效，请回到计划列表重新选择。');
  const query = parameters(scope, ['range_start', 'range_end', 'snapshot_ref']);
  const start = own(query, 'range_start'), end = own(query, 'range_end');
  if (start !== end || start && (!localTime(query.range_start) || !localTime(query.range_end) || query.range_start >= query.range_end))
    throw C.failure('读取的开始时间和结束时间要一起填，开始必须早于结束。请按 2026-09-13 08:30 这样填。');
  return query;
}
function tasksScope(planRef, scope) {
  if (!ref(planRef)) throw C.failure('这条计划记录已失效，请回到计划列表重新选择。');
  const query = parameters(scope, ['range_start', 'range_end', 'snapshot_ref', 'page', 'size']);
  if (!own(query, 'snapshot_ref') || !token(query.snapshot_ref))
    throw C.failure('翻页位置已失效，请回到第 1 页重新查询。');
  const start = own(query, 'range_start'), end = own(query, 'range_end');
  if (start !== end || start && (!localTime(query.range_start) || !localTime(query.range_end) || query.range_start >= query.range_end))
    throw C.failure('读取的开始时间和结束时间要一起填，开始必须早于结束。请按 2026-09-13 08:30 这样填。');
  if (!own(query, 'page')) query.page = 1;
  if (!own(query, 'size')) query.size = 5000;
  if (!Number.isSafeInteger(query.page) || query.page < 1 || !Number.isSafeInteger(query.size) || query.size < 1 || query.size > 5000)
    throw C.failure('工序安排分页参数无效，请刷新后重试。');
  return query;
}
function ganttGraphScope(planRef, scope) {
  const query = workspaceScope(planRef, scope);
  if (!own(query, 'snapshot_ref') || !token(query.snapshot_ref))
    throw C.failure('翻页位置已失效，请回到第 1 页重新查询。');
  return query;
}
function capacityScope(planRef, scope) {
  const query = workspaceScope(planRef, scope);
  if (!own(query, 'snapshot_ref') || !token(query.snapshot_ref))
    throw C.failure('翻页位置已失效，请回到第 1 页重新查询。');
  return query;
}
function baselineScope(planRef, scope) {
  if (!ref(planRef)) throw C.failure('这条计划记录已失效，请回到计划列表重新选择。');
  const query = parameters(scope, ['range_start', 'range_end', 'snapshot_ref', 'page', 'size']);
  if (!own(query, 'snapshot_ref') || !token(query.snapshot_ref))
    throw C.failure('翻页位置已失效，请回到第 1 页重新查询。');
  const start = own(query, 'range_start'), end = own(query, 'range_end');
  if (start !== end || start && (!localTime(query.range_start) || !localTime(query.range_end) || query.range_start >= query.range_end))
    throw C.failure('读取的开始时间和结束时间要一起填，开始必须早于结束。请按 2026-09-13 08:30 这样填。');
  if (!own(query, 'page')) query.page = 1;
  if (!own(query, 'size')) query.size = 5000;
  if (!Number.isSafeInteger(query.page) || query.page < 1 || !Number.isSafeInteger(query.size) || query.size < 1 || query.size > 5000)
    throw C.failure('原安排对照分页参数无效，请刷新后重试。');
  return query;
}
function exportScope(planRef, scope) {
  const query = parameters(scope, ['format', 'range_start', 'range_end', 'snapshot_ref']);
  if (!['csv', 'xlsx'].includes(query.format) || !own(query, 'snapshot_ref'))
    throw C.failure('导出没有拿到文件格式或当前数据版本，这次没有导出。请刷新后重新点「导出」。');
  const {format, ...read} = query;
  return {format, ...workspaceScope(planRef, read)};
}
// 成功信封（meta 五键、warnings 形状、as_of）已由 transport.read 校验；计划翻页与导出要钉住同一份快照。
function envelope(result, query) {
  if (result.meta.snapshot_ref === null) throw C.failure('计划数据不完整或数据源无效，请刷新后重试。');
  if (own(query, 'snapshot_ref') && result.meta.snapshot_ref !== query.snapshot_ref)
    throw C.failure(WorkbenchTerms.outcomes.stale);
}
function catalog(result, query) {
  envelope(result, query);
  const d = result.data, p = d && d.page;
  if (!object(d) || !object(p) || p.collection !== query.collection || p.size !== query.size
      || (p.has_more ? !token(p.next_cursor) || !d.plans.length || p.next_cursor === query.cursor : p.next_cursor !== null))
    throw C.failure('计划列表的类型或分页与查询不一致，请刷新。');
  return result;
}
function baseline(value, data) {
  if (!object(value)) return false;
  if (value.state === 'unavailable') return value.baseline_plan === null;
  return value.state === 'available' && ['candidate_adoption', 'trial_adoption'].includes(value.basis)
    && object(value.baseline_plan) && ref(value.baseline_plan.plan_ref) && !value.baseline_plan.is_current_official
    && value.baseline_plan.plan_ref !== data.plan.plan_ref
    && object(value.comparison_scope) && same(value.comparison_scope.scope, data.scope);
}
function baselinePage(result, data, query, firstData = null) {
  envelope(result, query);
  const d = result.data, p = d && d.page;
  if (!object(d) || !object(p) || own(query, 'page') && p.number !== query.page || own(query, 'size') && p.size !== query.size)
    throw C.failure('原安排对照的分页或明细与所选计划不一致，请刷新。');
  if (d.state === 'unavailable') {
    if (!baseline(d, data) || firstData && (d.state !== firstData.state || d.item_count !== firstData.item_count))
      throw C.failure('原安排对照的分页或明细与所选计划不一致，请刷新。');
    return result;
  }
  if (d.state !== 'available' || !['candidate_adoption', 'trial_adoption'].includes(d.basis)
      || !object(d.baseline_plan) || !ref(d.baseline_plan.plan_ref) || d.baseline_plan.is_current_official
      || d.baseline_plan.plan_ref === data.plan.plan_ref
      || !object(d.comparison_scope) || !same(d.comparison_scope.scope, data.scope)
      || firstData && (d.state !== firstData.state || d.basis !== firstData.basis || d.item_count !== firstData.item_count
        || d.baseline_plan.plan_ref !== firstData.baseline_plan.plan_ref
        || !same(d.comparison_scope.scope, firstData.comparison_scope.scope)))
    throw C.failure('原安排对照的分页或明细与所选计划不一致，请刷新。');
  return result;
}
function calendar(value, data) {
  return object(value)
    && value.plan_ref === data.plan.plan_ref && same(value.time_scope, data.time_scope);
}
function occupancy(value, data) {
  return object(value)
    && value.plan_ref === data.plan.plan_ref && same(value.time_scope, data.time_scope);
}
function workspaceSpans(data, query) {
  const time = data.time_scope;
  return object(data.plan_span) && object(time)
    && time.range_start === (own(query, 'range_start') ? query.range_start : data.plan_span.start)
    && time.range_end === (own(query, 'range_end') ? query.range_end : data.plan_span.end);
}
function tasksPage(result, data, query) {
  envelope(result, query);
  const d = result.data, p = d && d.page;
  const planRef = data.plan.plan_ref;
  const valid = object(d) && object(d.plan) && d.plan.plan_ref === planRef
    && object(d.scope) && d.scope.plan_ref === planRef
    && d.scope.range_start === (own(query, 'range_start') ? query.range_start : null)
    && d.scope.range_end === (own(query, 'range_end') ? query.range_end : null)
    && same(d.scope, data.scope) && same(d.time_scope, data.time_scope) && d.task_count === data.task_count
    && object(p) && (!own(query, 'page') || p.number === query.page) && (!own(query, 'size') || p.size === query.size);
  if (!valid) throw C.failure('工序安排的分页或明细与所选计划不一致，请刷新。');
  return result;
}
function ganttGraph(result, data, query) {
  envelope(result, query);
  const d = result.data;
  const planRef = data.plan.plan_ref, g = d && d.gantt_graph;
  if (!object(d) || d.plan_ref !== planRef || !object(d.scope) || d.scope.plan_ref !== planRef
      || d.scope.range_start !== (own(query, 'range_start') ? query.range_start : null)
      || d.scope.range_end !== (own(query, 'range_end') ? query.range_end : null)
      || !same(d.scope, data.scope) || !object(g) || g.scope !== 'full_plan')
    throw C.failure('工序衔接图与所选计划不一致，请刷新。');
  return result;
}
function capacity(result, data, query) {
  envelope(result, query);
  const d = result.data;
  const planRef = data.plan.plan_ref;
  if (!object(d) || d.plan_ref !== planRef || !object(d.scope) || d.scope.plan_ref !== planRef
      || d.scope.range_start !== (own(query, 'range_start') ? query.range_start : null)
      || d.scope.range_end !== (own(query, 'range_end') ? query.range_end : null)
      || !same(d.scope, data.scope) || !same(d.time_scope, data.time_scope)
      || !calendar(d.calendar, data)
      || !occupancy(d.occupancy, data))
    throw C.failure('资源班表或负荷数据与所选计划不一致，请刷新。');
  return result;
}
function workspace(result, planRef, query) {
  envelope(result, query);
  const d = result.data;
  const g = d && d.gantt_graph;
  if (!object(d) || !object(d.plan) || !d.plan.capabilities || !d.plan.capabilities.view || d.plan.plan_ref !== planRef
      || !object(d.scope) || d.scope.source !== 'production'
      || d.scope.kind !== 'plan_workspace' || d.scope.plan_ref !== planRef
      || d.scope.range_start !== (own(query, 'range_start') ? query.range_start : null)
      || d.scope.range_end !== (own(query, 'range_end') ? query.range_end : null) || !workspaceSpans(d, query)
      || !object(d.projections)
      || !baseline(d.projections.baseline, d)
      || !calendar(d.projections.calendar, d)
      || !occupancy(d.projections.occupancy, d)
      || !object(d.projections.delivery_risks) || d.projections.delivery_risks.plan_ref !== planRef || !same(d.projections.delivery_risks.scope, d.scope)
      || !object(g) || g.scope !== 'full_plan')
    throw C.failure('工序安排、时间范围或分析数据与所选计划不一致，请刷新。');
  return result;
}
const APSPlanContract = { catalogScope, workspaceScope, tasksScope, ganttGraphScope, capacityScope, baselineScope, exportScope, envelope, catalog, workspace, tasksPage, ganttGraph, capacity, baseline, baselinePage };
export { APSPlanContract, catalogScope, workspaceScope, tasksScope, ganttGraphScope, capacityScope, baselineScope, exportScope, envelope, catalog, workspace, tasksPage, ganttGraph, capacity, baseline, baselinePage };
export default APSPlanContract;
