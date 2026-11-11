import APSResourceContract from './resource-contract.js';
import APSWorkPeriods from './WorkPeriods.js';

// 个人日历只描述"这个人这天哪几个时段上班"，工时由后端按工作时段算。
const C = APSResourceContract;
const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
function month(result, expected) {
  const data = result.data;
  if (!C.object(data) || data.year !== expected.year || data.month !== expected.month || data.operator_ref !== expected.ref)
    throw C.failure('读到的个人日历不是当前人员的这个月，请刷新后重试。');
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
    if (!Number.isFinite(efficiency) || efficiency <= 0 || efficiency > 200)
      throw C.failure('效率须大于 0 且不超过 200%。', [{ path: 'fields.eff', message: '请填 0 到 200 之间的数字。' }]);
    if (!original.explicit || draft.eff !== draftOf(original).eff) fields.eff = efficiency;
  }
  const periods = draft.type === 'rest' ? [] : draft.periods;
  const issue = APSWorkPeriods.validate(periods);
  if (issue) throw C.failure(issue, [{ path: 'fields.periods', message: issue }]);
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
    throw C.failure('请选择正确的开始和结束日期。', [{ path: !isDate(range.start_date) ? 'start_date' : 'end_date', message: '日期须有效。' }]);
  if (range.start_date > range.end_date)
    throw C.failure('结束日期不能早于开始日期。', [{ path: 'end_date', message: '结束日期不能早于开始日期。' }]);
  return { start_date: range.start_date, end_date: range.end_date };
}
function rangePreview(result, expected) {
  const data = result.data;
  if (!C.object(data.range) || data.range.start_date !== expected.start_date || data.range.end_date !== expected.end_date)
    throw C.failure('预检的日期范围和选的不一致，没有清除任何设置。请重新点「预检要清除的日期」。');
  return result;
}
const APSOperatorCalendar = { month, draftOf, switchType, input, tag, rangeInput, rangePreview };
export { APSOperatorCalendar, month, draftOf, switchType, input, tag, rangeInput, rangePreview };
export default APSOperatorCalendar;
