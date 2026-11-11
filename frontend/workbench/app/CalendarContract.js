import APSResourceContract from './resource-contract.js';
import APSWorkPeriods from './WorkPeriods.js';

const C = APSResourceContract;
const path = '/api/workbench/v1/calendar';
const keys = ['type', 'periods', 'eff', 'allowNormal', 'allowUrgent', 'note'];
const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && Number(value.slice(0, 4)) >= 1 && Number(value.slice(5, 7)) >= 1 && Number(value.slice(5, 7)) <= 12
  && Number(value.slice(8)) >= 1 && Number(value.slice(8)) <= monthDays(Number(value.slice(0, 4)), Number(value.slice(5, 7)));
function monthDays(year, month) {
  return [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
}
function monthKey(year, month) { return String(year).padStart(4, '0') + '-' + String(month).padStart(2, '0'); }
function displayNumber(value) {
  if (!Number.isFinite(value)) return String(value);
  const tidy = Number(value.toPrecision(15));
  return String(Math.abs(value - tidy) <= Math.abs(value) * Number.EPSILON * 2 ? tidy : value);
}
function month(result, year, number) {
  const data = result.data;
  if (!C.object(data) || data.year !== year || data.month !== number)
    throw C.failure('读到的月份、日期或统计数据不完整，页面没有改动。请刷新后重试。');
  return result;
}
function preview(result) {
  const data = result.data;
  if (typeof data.preview_ref !== 'string' || !/^[0-9a-f]{32}$/.test(data.preview_ref))
    throw C.failure('读到的变更清单不完整，没有写入。请点「重新预览变更」。');
  return result;
}
function draft(value) {
  if (Array.isArray(value)) return { type: 'work',
    periods: APSWorkPeriods.clone(value), defaultPeriods: value,
    eff: '100', allowNormal: 'yes', allowUrgent: 'yes', note: '' };
  return { type: value.fields.type, allowNormal: value.fields.allowNormal, allowUrgent: value.fields.allowUrgent,
    defaultPeriods: value.default_periods,
    periods: APSWorkPeriods.clone(value.fields.periods),
    eff: displayNumber(value.fields.eff), note: value.fields.note ?? '' };
}
function switchType(value, type) {
  if (type !== 'work' || value.type !== 'rest' || value.periods.length) return { ...value, type };
  const periods = value.defaultPeriods;
  return { ...value, type, periods: APSWorkPeriods.clone(periods), allowNormal: 'yes', allowUrgent: 'yes' };
}
function effNumber(value) {
  const result = Number(value);
  if (typeof value !== 'string' || !value.trim() || !Number.isFinite(result) || result <= 0 || result > 200)
    throw C.failure('效率须大于 0 且不超过 200%。', [{ path: 'fields.eff', message: '请输入有效数字。' }]);
  return result;
}
function input(value, original) {
  const periods = value.type === 'rest' ? [] : value.periods;
  const issue = APSWorkPeriods.validate(periods);
  if (issue) throw C.failure(issue, [{ path: 'fields.periods', message: issue }]);
  const note = value.note.trim();
  const converted = {
    type: value.type,
    periods: APSWorkPeriods.clone(periods),
    note: note === '' ? null : note
  };
  if (value.type === 'work') {
    Object.assign(converted, { eff: effNumber(value.eff), allowNormal: value.allowNormal, allowUrgent: value.allowUrgent });
  }
  // A default date has no stored row; creating it must not inherit different domain defaults.
  if (!original || !original.explicit) return converted;
  const output = {};
  keys.forEach(key => {
    const before = key === 'eff' ? Number(displayNumber(original.fields.eff)) : original.fields[key];
    if (C.own(converted, key) && JSON.stringify(converted[key]) !== JSON.stringify(before)) output[key] = converted[key];
  });
  // 休息日改工作日必须明确带上工作时段：哪怕和原来一样（全部移除就是明确 0 工时），后端都不替它沿用。
  if (value.type === 'work' && original.fields.type === 'rest') output.periods = converted.periods;
  return output;
}
// 月历格子里的工时带单位显示，数字格式和单位统一走 WorkbenchFormat，不在这里手拼“小时”。
const hoursText = value => APSWorkPeriods.duration(value);
function tag(row) {
  const working = row.effective.is_working;
  let text = working ? hoursText(row.fields.hours) : '休';
  let tone = row.is_weekend ? 'we' : '';
  if (row.explicit) {
    tone = row.is_weekend === working ? 'rest' : working ? 'cfg' : 'we';
    text = row.is_weekend && working ? '加班 ' + hoursText(row.fields.hours) : !row.is_weekend && !working ? '调休' : text;
    if (working && row.fields.allowNormal !== row.fields.allowUrgent) text += row.fields.allowNormal === 'yes' ? ' · 仅普通件' : ' · 仅急件';
  }
  return { tone, text };
}
const APSCalendarContract = { path, month, preview, monthDays, monthKey, isDate, draft, switchType, input, tag, displayNumber };
export { APSCalendarContract, path, month, preview, monthDays, monthKey, isDate, draft, switchType, input, tag, displayNumber };
export default APSCalendarContract;
