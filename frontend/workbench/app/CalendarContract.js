import C from './resource-contract.js';
import APSWorkPeriods from './WorkPeriods.js';
import { failure } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：月历的年月与请求一致，预览带变更清单编号。
const path = '/api/workbench/v1/calendar';
const keys = ['type', 'periods', 'eff', 'allowNormal', 'allowUrgent', 'note'];
// 工厂日历日的判定与算术（isDate、monthDays、moveDay 等）统一在 shared/contract/kit.js。
function displayNumber(value) {
  if (!Number.isFinite(value)) return String(value);
  const tidy = Number(value.toPrecision(15));
  return String(Math.abs(value - tidy) <= Math.abs(value) * Number.EPSILON * 2 ? tidy : value);
}
function month(result, year, number) {
  const data = result.data;
  if (data.year !== year || data.month !== number)
    throw failure('读到的月份、日期或统计数据不完整，页面没有改动。请刷新后重试。');
  return result;
}
function preview(result) {
  const data = result.data;
  if (typeof data.preview_ref !== 'string' || !/^[0-9a-f]{32}$/.test(data.preview_ref))
    throw failure('读到的变更清单不完整，没有写入。请点「重新预览变更」。');
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
  // 提交前只确认能解析成有限数；取值范围由后端校验，422 带字段路径。
  if (typeof value !== 'string' || !value.trim() || !Number.isFinite(result))
    throw failure('请填写有效的效率。', { fields: [{ path: 'fields.eff', message: '请输入有效数字。' }] });
  return result;
}
function input(value, original) {
  const periods = value.type === 'rest' ? [] : value.periods;
  const issue = APSWorkPeriods.validate(periods);
  if (issue) throw failure(issue, { fields: [{ path: 'fields.periods', message: issue }] });
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
const APSCalendarContract = { path, month, preview, draft, switchType, input, tag, displayNumber };
export { APSCalendarContract, path, month, preview, draft, switchType, input, tag, displayNumber };
export default APSCalendarContract;
