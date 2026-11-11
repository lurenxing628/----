import APSResourceContract from './resource-contract.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import WorkbenchFormat from './WorkbenchFormat.js';

const C = APSResourceContract;
// 报工状态与报工类型都取全站词表：现场记录、现场实际甘特、报表中心、工时校准与排产候选、值班台用同一套叫法，不再各自造词。
const states = WorkbenchTerms.execution_states;
const reportActions = WorkbenchTerms.report_actions;
const fields = ['completed_quantity', 'actual_start', 'actual_end', 'effective_processing_hours', 'actual_machine_ref', 'actual_operator_ref', 'remark'];
// 现场记录一次最多按 5000 个批次筛选（后端 core/services/workbench/execution/field_workspace_scope.py 的 _batches）。
const batchLimit = 5000;
const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
const time = value => value === null || typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(value);
const validTime = value => typeof value === 'string' && time(value) && Number.isFinite(Date.parse(value + 'Z')) && new Date(value + 'Z').toISOString().slice(0, 19) === value;
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
  if (!C.object(d.task) || d.task.task_ref !== expected) throw C.failure('现场任务详情不匹配，请刷新后重选。');
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
      if (v !== '' && (!Number.isFinite(Number(v)) || Number(v) < 0 || key === 'completed_quantity' && !Number.isSafeInteger(Number(v)))) bad(key, key === 'completed_quantity' ? '数量必须为非负整数。' : '工时必须是 0 或正数。');
      v = v === '' ? null : Number(v);
    } else if (key === 'actual_start' || key === 'actual_end') {
      v = v ? v.length === 16 ? v + ':00' : v : null;
      if (v !== null && !validTime(v)) bad(key, '请按 2026-09-13 08:30 这样填写；未知时请清除。');
    }
    else if (key.endsWith('_ref')) v = v === '' ? null : v;
    if (!record || v !== record[key]) result[key] = v;
  });
  if (record) {
    if (!value.reason.trim()) bad('reason', '请填写补齐或更正原因。');
    if (!Object.keys(result).length) throw C.failure('内容没有变化。');
    result.original_revision_ref = record.revision_ref; result.reason = value.reason.trim();
  } else result.source = 'manual';
  if (action === 'supplement') fields.filter(key => Object.prototype.hasOwnProperty.call(result, key) && record[key] !== null && record[key] !== '' && result[key] !== record[key]).forEach(key => bad(key, '补齐不能改动已有记录，请改用「更正」。'));
  const start = value.actual_start ? Date.parse(value.actual_start + 'Z') : NaN, end = value.actual_end ? Date.parse(value.actual_end + 'Z') : NaN;
  if (Number.isFinite(start) && Number.isFinite(end) && start > end) bad('actual_end', '本次实际完工不能早于实际开工。');
  if (Number.isFinite(start) && Number.isFinite(end) && end >= start && value.effective_processing_hours !== '' && Number(value.effective_processing_hours) > (end - start) / 3600000)
    bad('effective_processing_hours', '有效工时不能超过本次实际起止的时长。');
  if (errors.length) throw C.failure('请核对标红的项。', errors);
  result.declared_operator = value.declared_operator.trim();
  return result;
}
const display = value => value === null || value === undefined || value === '' ? '未知' : String(value);
// Report times are second-precision (see the time pattern and step="1" inputs): seconds stay visible whenever they are
// not :00, so nothing is lost while whole-minute times read as minutes. WorkbenchFormat has no auto option yet.
const hasSeconds = value => typeof value === 'string' && /:\d\d:(?!00(?:\.0+)?$)\d\d(?:\.\d+)?$/.test(value);
const date = value => WorkbenchFormat.dateTime(value, { seconds: hasSeconds(value), fractions: true });
const FieldContract = { states, reportActions, fields, batchLimit, ref, detail, blocked, draft, input, display, date, quantity, hours, pieceLabel, quantityReasons, validTime };
export { FieldContract, states, reportActions, fields, batchLimit, ref, detail, blocked, draft, input, display, date, quantity, hours, pieceLabel, quantityReasons, validTime };
export default FieldContract;
