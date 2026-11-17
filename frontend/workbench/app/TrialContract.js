import WorkbenchTerms from './WorkbenchTerms.js';
import { object, ref48, localTime, checker } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：试调读取的数据版本与请求一致，命令回执与本次操作对得上。
const fields = (v, keys) => object(v) && keys.every(k => Object.prototype.hasOwnProperty.call(v, k));
const INVALID = '试调数据不完整或不一致，请刷新后重试。';
// 试调提交回执与回执查询都在命令发出之后：核对不过时结果未知，本机待确认记录不能清。
const check = checker(INVALID), checkResult = checker(INVALID, { committed: 'unknown' });
function base(v) { check(object(v) && Object.keys(v).length === 1 && ['plan_ref', 'candidate_ref'].some(k => ref48(v[k]))); return v; }
function scope(v = {}) {
  check(object(v) && Object.keys(v).every(k => ['range_start', 'range_end', 'batch_refs', 'resource_type', 'resource_ref', 'query'].includes(k)), '试调显示范围含未知条件。');
  if (v.range_start !== undefined || v.range_end !== undefined) check(localTime(v.range_start) && localTime(v.range_end) && v.range_start < v.range_end, '显示起止时间须成对填写，开始早于结束。');
  if (v.batch_refs !== undefined) check(Array.isArray(v.batch_refs) && v.batch_refs.every(ref48));
  if (v.resource_type !== undefined) check(['machine', 'operator', 'batch'].includes(v.resource_type));
  if (v.resource_ref !== undefined) check(ref48(v.resource_ref) && v.resource_type !== undefined);
  if (v.query !== undefined) check(typeof v.query === 'string' && v.query.length <= 200);
  return v;
}
// A navigation target is an identity, never an instruction to pick the latest record.
// 键集、草稿 / 方案 / 原来源三选一、范围只配原来源、return_to 已由 WorkbenchNavigation.admit 按受控导航声明准入；这里核对取值。
function target(v) {
  const keys = ['draft_ref', 'scenario_ref', 'base'].filter(k => v[k] !== undefined);
  if (v.kind !== undefined) check(v.kind === (v.draft_ref ? 'draft' : v.scenario_ref ? 'scenario' : 'base'));
  keys.forEach(k => k === 'base' ? base(v[k]) : check(ref48(v[k])));
  if (v.scope !== undefined) scope(v.scope);
  if (Object.prototype.hasOwnProperty.call(v, 'task_origin')) {
    origin(v.task_origin);
    check(keys.length === 1, '原任务定位只能指向原正式计划或指定草稿。');
    if (v.base) check(v.base.plan_ref === v.task_origin.plan_ref, '原任务与试调原计划不一致。');
  }
  return v;
}
function origin(value) {
  check(fields(value, ['plan_ref', 'operation_ref', 'task_ref']) && Object.keys(value).length === 3
    && ['plan_ref', 'operation_ref', 'task_ref'].every(key => ref48(value[key])), '原任务定位必须包含完整的原计划、工序和任务编号。');
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
function receipt(v) {
  checkResult(v && v.ok === true && ['committed', 'unchanged'].includes(v.result) && /^[a-f0-9]{32}$/.test(v.receipt_ref) && object(v.data));
  return v;
}
const TrialContract = { check, checkResult, base, scope, target, origin, originTask, envelope, receipt };
export { TrialContract, check, checkResult, base, scope, target, origin, originTask, envelope, receipt };
export default TrialContract;
