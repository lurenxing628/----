import DecisionHistoryAPI from './DecisionHistoryAPI.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
const fields = (v, keys) => object(v) && keys.every(k => Object.prototype.hasOwnProperty.call(v, k));
function check(value, message = '试调数据不完整或不一致，请刷新后重试。') { if (!value) throw new Error(message); }
const DAYS = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
function time(v) {
  // Keep the wire value intact: calendar fields are validated directly without Date allocation or timezone serialization.
  if (typeof v !== 'string' || !/^(?!0000)\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.(?!000000$)\d{6})?(?![\s\S])/.test(v)) return false;
  const y = (v.charCodeAt(0) - 48) * 1000 + (v.charCodeAt(1) - 48) * 100 + (v.charCodeAt(2) - 48) * 10 + (v.charCodeAt(3) - 48);
  const m = (v.charCodeAt(5) - 48) * 10 + (v.charCodeAt(6) - 48), d = (v.charCodeAt(8) - 48) * 10 + (v.charCodeAt(9) - 48);
  return m >= 1 && m <= 12 && d >= 1 && d <= (m === 2 && y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0) ? 29 : DAYS[m]);
}
function base(v) { check(object(v) && Object.keys(v).length === 1 && ['plan_ref', 'candidate_ref'].some(k => ref(v[k]))); return v; }
function scope(v = {}) {
  check(object(v) && Object.keys(v).every(k => ['range_start', 'range_end', 'batch_refs', 'resource_type', 'resource_ref', 'query'].includes(k)), '试调显示范围含未知条件。');
  if (v.range_start !== undefined || v.range_end !== undefined) check(time(v.range_start) && time(v.range_end) && v.range_start < v.range_end, '显示起止时间须成对填写，开始早于结束。');
  if (v.batch_refs !== undefined) check(Array.isArray(v.batch_refs) && v.batch_refs.every(ref));
  if (v.resource_type !== undefined) check(['machine', 'operator', 'batch'].includes(v.resource_type));
  if (v.resource_ref !== undefined) check(ref(v.resource_ref) && v.resource_type !== undefined);
  if (v.query !== undefined) check(typeof v.query === 'string' && v.query.length <= 200);
  return v;
}
// A navigation target is an identity, never an instruction to pick the latest record.
function target(v = {}) {
  check(object(v) && Object.keys(v).every(k => ['kind', 'draft_ref', 'scenario_ref', 'base', 'scope', 'task_origin', 'return_decision_history_context'].includes(k)), '试调入口参数无效。');
  if (v.return_decision_history_context !== undefined) DecisionHistoryAPI.context(v.return_decision_history_context);
  const keys = ['draft_ref', 'scenario_ref', 'base'].filter(k => v[k] !== undefined);
  check(keys.length <= 1, '只能指定一份试调草稿、试调方案或原来源。');
  if (v.kind !== undefined) check(v.kind === (v.draft_ref ? 'draft' : v.scenario_ref ? 'scenario' : 'base'));
  keys.forEach(k => k === 'base' ? base(v[k]) : check(ref(v[k])));
  if (v.scope !== undefined) { check(keys[0] === 'base', '已有草稿不能重新指定基础范围。'); scope(v.scope); }
  if (Object.prototype.hasOwnProperty.call(v, 'task_origin')) {
    origin(v.task_origin);
    check(keys.length === 1 && keys[0] !== 'scenario_ref', '原任务定位只能指向原正式计划或指定草稿。');
    if (v.base) check(v.base.plan_ref === v.task_origin.plan_ref, '原任务与试调原计划不一致。');
  }
  return v;
}
function origin(value) {
  check(fields(value, ['plan_ref', 'operation_ref', 'task_ref']) && Object.keys(value).length === 3
    && ['plan_ref', 'operation_ref', 'task_ref'].every(key => ref(value[key])), '原任务定位必须包含完整的原计划、工序和任务编号。');
  return value;
}
function originTask(data, value) {
  origin(value);
  check(!data.scenario_ref && data.base && data.base.plan_ref === value.plan_ref, '当前草稿与原任务来源不一致，无法调整。');
  const tasks = data.tasks.filter(task => task.source_task_ref === value.task_ref && task.operation_ref === value.operation_ref);
  check(tasks.length === 1, tasks.length ? '原任务对应多份草稿安排，无法定位。' : '当前草稿中未找到原任务。');
  return tasks[0];
}
// 信封已由 transport 校验；试调列表翻页和采用记录都钉在这次读取的数据版本上，所以数据版本不能为空。
function envelope(v, q = {}) {
  check(v.meta.snapshot_ref !== null); if (q.snapshot_ref) check(v.meta.snapshot_ref === q.snapshot_ref, WorkbenchTerms.outcomes.stale);
  return v.data;
}
function workspace(d, expected = {}) {
  check(object(d) && ref(d.draft_ref) && (!expected.draft_ref || expected.draft_ref === d.draft_ref)
    && (!expected.scenario_ref || expected.scenario_ref === d.scenario_ref));
  return d;
}
function catalog(v, collection, q) {
  const d = envelope(v, q), p = d.page, s = d.scope;
  check(object(s) && s.collection === collection
    && s.status === (q.status ?? null) && s.base_kind === (q.base_kind ?? null) && s.base_ref === (q.base_ref ?? null) && s.size === q.size
    && object(p) && p.number === q.page && p.size === q.size);
  return d;
}
function receipt(v, intent) {
  check(v && v.ok === true && ['committed', 'unchanged'].includes(v.result) && /^[a-f0-9]{32}$/.test(v.receipt_ref));
  const d = v.data;
  if (d && d.status === 'discarded' && d.history_retained === true) check(ref(d.draft_ref));
  else workspace(d);
  if (intent) {
    if (intent.draft_ref) check(d.draft_ref === intent.draft_ref);
    if (intent.action === 'create') check(JSON.stringify(d.base) === JSON.stringify(intent.input.base) && d.status === 'editing');
    if (intent.action === 'save') check(ref(d.scenario_ref) && d.name === intent.input.name.trim());
    if (intent.action === 'discard') check(d.status === 'discarded' && d.history_retained === true);
    if (intent.action === 'change') { const t = d.tasks.find(t => t.task_ref === intent.input.task_ref); check(t && ['machine_ref', 'operator_ref', 'start'].every(k => t[k] === intent.input[k])); }
  }
  return v;
}
const TrialContract = { object, ref, check, time, base, scope, target, origin, originTask, envelope, workspace, catalog, receipt };
export { TrialContract, object, ref, check, time, base, scope, target, origin, originTask, envelope, workspace, catalog, receipt };
export default TrialContract;
