import WorkbenchTerms from './WorkbenchTerms.js';
import WorkbenchFormat from './WorkbenchFormat.js';
import { failure, object, localSecond } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：现场任务详情属于所选任务。
// 报工状态与报工类型都取全站词表：现场记录、现场实际甘特、报表中心、工时校准与排产候选、值班台用同一套叫法，不再各自造词。
const states = WorkbenchTerms.execution_states;
const reportActions = WorkbenchTerms.report_actions;
const fields = ['completed_quantity', 'actual_start', 'actual_end', 'effective_processing_hours', 'actual_machine_ref', 'actual_operator_ref', 'remark'];
// 计划应做数量缺失的三种说法：现场记录、现场实际甘特、计划甘特提示共用，不再各写一份。
const quantityReasons = { plan_target_not_recorded: '原计划未记录应做数量', plan_target_unavailable: '原计划应做数量读不到', plan_target_invalid: '原计划应做数量无效' };
const quantity = (value, options = { digits: 0 }) => typeof value === 'string'
  ? WorkbenchFormat.integerText(value) : WorkbenchFormat.number(value, options);
// 有效工时按录入精度最多显示三位小数；单位由表头或调用处补。
const hours = value => value === null || value === undefined || value === '' ? '未知' : WorkbenchFormat.number(value, { digits: 3, trim: true });
const pieceLabel = value => value.piece_id === null ? '共同工序' : '分件 ' + value.piece_id;
// 信封（ok、schema_version、meta、data 对象）已由 transport.js 的 envelope() 校验，这里只校验 data。
function detail(result, expected) {
  const d = result.data;
  if (!object(d.task) || d.task.task_ref !== expected) throw failure('现场任务详情不匹配，请刷新后重选。');
  return result;
}
// context 是已校验过的任务、记录或预检上下文；关闭的上下文没有 write_token、capabilities 为空，原因都在 blocked_reasons 里
// （core/models/workbench_execution_input.py closed_write_context）。
function blocked(context, action) {
  if (context.write_token && context.capabilities[action] === true) return '';
  const reasons = context.blocked_reasons.map(item => item.message);
  return reasons.length ? reasons.join('；') : '本页数据已过期，请刷新后重试。';
}
function draft(record) {
  return Object.fromEntries(fields.map(key => [key, record && record[key] != null ? String(record[key]) : '']).concat([['reason', ''], ['declared_operator', '']]));
}
function input(value, record, action) {
  const result = {}, errors = [];
  const bad = (path, message) => errors.push({ path, message });
  fields.forEach(key => {
    let v = value[key];
    if (['completed_quantity', 'effective_processing_hours'].includes(key)) {
      // 提交前只确认能解析成有限数（NaN 会被 JSON 写成 null，当成“清空”）；取值范围由后端校验，422 带字段路径。
      const number = Number(v);
      if (v !== '' && !Number.isFinite(number)) bad(key, key === 'completed_quantity' ? '请填写有效的数量。' : '请填写有效的工时。');
      v = v === '' ? null : number;
    } else if (key === 'actual_start' || key === 'actual_end') {
      v = v ? v.length === 16 ? v + ':00' : v : null;
      if (v !== null && !localSecond(v)) bad(key, '请按 2026-09-13 08:30 这样填写；未知时请清除。');
    }
    else if (key.endsWith('_ref')) v = v === '' ? null : v;
    if (!record || v !== record[key]) result[key] = v;
  });
  if (record) {
    if (!value.reason.trim()) bad('reason', '请填写补齐或更正原因。');
    if (!Object.keys(result).length) throw failure('内容没有变化。');
    result.original_revision_ref = record.revision_ref; result.reason = value.reason.trim();
  } else result.source = 'manual';
  // 补齐不改已有值、完工不早于开工、工时不超过起止时长这些业务规则由后端校验，422 带字段路径。
  if (errors.length) throw failure('请核对标红的项。', { fields: errors });
  result.declared_operator = value.declared_operator.trim();
  return result;
}
const display = value => value === null || value === undefined || value === '' ? '未知' : String(value);
// Report times are second-precision (see the time pattern and step="1" inputs): seconds stay visible whenever they are
// not :00, so nothing is lost while whole-minute times read as minutes. WorkbenchFormat has no auto option yet.
const hasSeconds = value => typeof value === 'string' && /:\d\d:(?!00(?:\.0+)?$)\d\d(?:\.\d+)?$/.test(value);
const date = value => WorkbenchFormat.dateTime(value, { seconds: hasSeconds(value), fractions: true });
const FieldContract = { states, reportActions, fields, detail, blocked, draft, input, display, date, quantity, hours, pieceLabel, quantityReasons };
export { FieldContract, states, reportActions, fields, detail, blocked, draft, input, display, date, quantity, hours, pieceLabel, quantityReasons };
export default FieldContract;
