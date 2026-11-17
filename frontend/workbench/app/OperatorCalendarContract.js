import APSWorkPeriods from './WorkPeriods.js';
import { object, isDate, failure } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：个人日历属于所选人员与月份，清除预检的日期范围与所选一致。
// 个人日历只描述"这个人这天哪几个时段上班"，工时由后端按工作时段算。
function month(result, expected) {
  const data = result.data;
  if (data.year !== expected.year || data.month !== expected.month || data.operator_ref !== expected.ref)
    throw failure('读到的个人日历不是当前人员的这个月，请刷新后重试。');
  return result;
}
function draftOf(value) {
  if (!value.explicit) return { type: 'work', eff: '100',
    allowNormal: 'yes', allowUrgent: 'yes', note: '', periods: APSWorkPeriods.clone(value.default_periods) };
  return {
    periods: APSWorkPeriods.clone(value.periods),
    type: value.day_type === 'holiday' ? 'rest' : 'work',
    eff: String(Number((value.efficiency * 100).toPrecision(15))),
    allowNormal: value.allow_normal, allowUrgent: value.allow_urgent, note: value.remark === null ? '' : value.remark
  };
}
// 只有从休息改回上班且当前时段已清空时才补默认工作时间；已经是上班或草稿里还有逐段时段时保持原样。
function switchType(day, draft, type) {
  if (type !== 'work' || draft.type !== 'rest' || draft.periods.length) return { ...draft, type };
  return { ...draft, type, periods: APSWorkPeriods.clone(day.default_periods) };
}
function input(draft, original) {
  const fields = { type: draft.type, allowNormal: draft.allowNormal, allowUrgent: draft.allowUrgent };
  if (draft.type === 'rest') {
    fields.allowNormal = 'no'; fields.allowUrgent = 'no';
  } else {
    const efficiency = Number(draft.eff.trim());
    // 提交前只确认能解析成有限数；取值范围由后端校验，422 带字段路径。
    if (!draft.eff.trim() || !Number.isFinite(efficiency))
      throw failure('请填写有效的效率。', { fields: [{ path: 'fields.eff', message: '请输入有效数字。' }] });
    if (!original.explicit || draft.eff !== draftOf(original).eff) fields.eff = efficiency;
  }
  const periods = draft.type === 'rest' ? [] : draft.periods;
  const issue = APSWorkPeriods.validate(periods);
  if (issue) throw failure(issue, { fields: [{ path: 'fields.periods', message: issue }] });
  fields.periods = APSWorkPeriods.clone(periods);
  const note = draft.note.trim();
  fields.note = note === '' ? null : note;
  return fields;
}
function tag(value) {
  if (!value || !value.explicit) return { tone: 'none', text: '按班次' };
  if (!value.periods.length || value.allow_normal === 'no' && value.allow_urgent === 'no')
    return { tone: 'rest', text: '休息' };
  return { tone: 'cfg', text: APSWorkPeriods.describe(value.periods) };
}
function rangeInput(range) {
  if (!isDate(range.start_date) || !isDate(range.end_date))
    throw failure('请选择正确的开始和结束日期。', { fields: [{ path: !isDate(range.start_date) ? 'start_date' : 'end_date', message: '日期须有效。' }] });
  if (range.start_date > range.end_date)
    throw failure('结束日期不能早于开始日期。', { fields: [{ path: 'end_date', message: '结束日期不能早于开始日期。' }] });
  return { start_date: range.start_date, end_date: range.end_date };
}
function rangePreview(result, expected) {
  const data = result.data;
  if (!object(data.range) || data.range.start_date !== expected.start_date || data.range.end_date !== expected.end_date)
    throw failure('预检的日期范围和选的不一致，没有清除任何设置。请重新点「预检要清除的日期」。');
  return result;
}
const APSOperatorCalendar = { month, draftOf, switchType, input, tag, rangeInput, rangePreview };
export { APSOperatorCalendar, month, draftOf, switchType, input, tag, rangeInput, rangePreview };
export default APSOperatorCalendar;
