import DashboardContract from './DashboardContract.js';

const count = v => Number.isSafeInteger(v) && v >= 0;

const sections = ['overview', 'delivery', 'actual', 'downtime', 'material', 'pressure', 'resource_days', 'timeline'];

function scope(value) {
  const C = DashboardContract;
  const q = { section: 'delivery', page: 1, size: 20, ...value };
  C.check(C.object(value) && Object.keys(q).every(key => ['section', 'page', 'size', 'snapshot_ref', 'resource_ref', 'locate_batch_ref'].includes(key))
    && sections.includes(q.section) && count(q.page) && q.page >= 1 && q.page <= 100000 && count(q.size) && q.size >= 1 && q.size <= 100
    && (q.snapshot_ref === undefined || typeof q.snapshot_ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(q.snapshot_ref))
    && (q.section === 'resource_days' ? C.ref(q.resource_ref) : q.resource_ref === undefined)
    && (q.locate_batch_ref === undefined || q.section === 'timeline' && C.ref(q.locate_batch_ref)), '影响分析的页码或范围无效，请重新选择。');
  return q;
}

function pagination(value, q, payload) {
  const C = DashboardContract;
  C.check(C.object(value) && value.section === q.section && value.size === q.size && (q.locate_batch_ref ? value.number >= 1 && value.number <= value.pages : value.number === q.page), '影响分析返回的页码或范围和当前选择不一致，请刷新分析。');
  C.check(!q.snapshot_ref || payload.meta.snapshot_ref === q.snapshot_ref, '分析资料已更新，请刷新分析后继续翻页。');
  return value;
}

function validate(payload, planRef, query) {
  return _validate(payload, planRef, scope(query));
}

function _validate(payload, planRef, q) {
  const C = DashboardContract, d = payload && payload.data;
  C.check(C.object(d));
  const page = pagination(d.pagination, q, payload), section = page.section;
  C.check(!planRef || (C.object(d.plan) && d.plan.plan_ref === planRef));
  if (q.locate_batch_ref) C.check(Array.isArray(d.tasks) && d.tasks.some(task => task.batch_ref === q.locate_batch_ref
    && task.source === 'internal' && task.machine_ref), '影响分析返回的工序和所选批次不一致，请刷新分析。');
  if (section === 'resource_days' && d.plan) C.check(Array.isArray(d.resources) && d.resources.length === 1 && d.resources[0].resource_ref === q.resource_ref);
  return d;
}

async function read(planRef, signal, query) {
  const C = DashboardContract;
  C.check(planRef === null || planRef === undefined || C.ref(planRef));
  const q = scope(query), args = { ...q, ...(planRef ? { plan_ref: planRef } : {}) };
  const value = await C.read('/api/workbench/v1/dashboard/analysis', args, signal);
  _validate(value, planRef, q); return value;
}

const DashboardAnalysisAPI = { read, validate, scope, count };

export { DashboardAnalysisAPI, read, validate, scope, count };
export default DashboardAnalysisAPI;
