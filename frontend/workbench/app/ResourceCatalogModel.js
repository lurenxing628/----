import APSWorkPeriods from './WorkPeriods.js';
import { failure, isDate } from './shared/contract/kit.js';

const names = { machine_group: '设备组', shift_profile: '班次档' };
function draft(entity) {
  const fields = entity ? entity.fields : {};
  return { business_code: entity ? entity.business_code : '', label: entity ? entity.label : '',
    status: entity ? entity.status : '', remark: fields.remark == null ? '' : fields.remark,
    anchor_date: fields.anchor_date || '', cycle_days: fields.cycle_days == null ? '' : String(fields.cycle_days),
    pattern: Array.isArray(fields.pattern) ? fields.pattern : [] };
}
// 生成或调整逐日规则草稿前的范围约束：防止一次在浏览器里铺出巨量空白行。提交侧的取值范围由后端校验。
// 本地错误的字段路径与后端 422 同一口径（facts/6-1b 契约表）：编号、名称在顶层，其余在 fields 下。
function cycle(value) {
  if (!/^[1-9][0-9]{0,2}$/.test(value) || Number(value) > 366)
    throw failure('请填写 1 至 366 之间的整数轮换天数。', { fields: [{ path: 'fields.cycle_days', message: '轮换天数必须为 1 至 366。' }] });
  return Number(value);
}
function resized(pattern, length) {
  return Array.from({ length }, (_, day_offset) => pattern[day_offset] ||
    { day_offset, is_rest: null, periods: [] });
}
// 逐日规则的错误就地标在那一天：工作安排是 fields.pattern.<i>，休息日有时段、工作日缺时段和时段本身的问题是 fields.pattern.<i>.periods。
function patternErrors(pattern) {
  const errors = [];
  pattern.forEach((row, index) => {
    const day = 'fields.pattern.' + index, bad = (path, message) => errors.push({ path, message });
    // 跨日时段重叠等业务规则由后端校验，422 带字段路径。
    if (typeof row.is_rest !== 'boolean') bad(day, '请明确选择工作或休息。');
    if (row.is_rest === true && row.periods.length) bad(day + '.periods', '休息日不能填写工作时段。');
    if (row.is_rest === false && !row.periods.length) bad(day + '.periods', '工作日请至少填写一个工作时段，或明确改为休息日。');
    const issue = APSWorkPeriods.validate(row.periods);
    if (issue) bad(day + '.periods', issue);
  });
  return errors;
}
function samePeriods(a, b) {
  if (a === b) return true;
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
  return a.every((p, i) => {
    const q = b[i];
    return p === q || Boolean(p && q && p.start === q.start && p.end === q.end && p.day_offset === q.day_offset);
  });
}
function samePattern(a, b) {
  if (a === b) return true;
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
  return a.every((row, i) => {
    const other = b[i];
    return row === other || Boolean(row && other
      && row.day_offset === other.day_offset
      && row.is_rest === other.is_rest
      && samePeriods(row.periods, other.periods));
  });
}
function isDirty(kind, current, baseline) {
  if (current === baseline) return false;
  if (!current || !baseline) return true;
  if (current.business_code !== baseline.business_code
      || current.label !== baseline.label
      || current.status !== baseline.status
      || current.remark !== baseline.remark) return true;
  if (kind !== 'shift_profile') return false;
  if (current.anchor_date !== baseline.anchor_date
      || current.cycle_days !== baseline.cycle_days) return true;
  return !samePattern(current.pattern, baseline.pattern);
}
function input(kind, value, original) {
  if (!names[kind]) throw failure('不支持这类基础资料。');
  const creating = !original, baseFields = original ? original.fields : {}, result = {}, fields = {}, errors = [];
  const bad = (path, message) => errors.push({ path, message });
  if (creating) {
    result.business_code = value.business_code.trim();
    if (!result.business_code) bad('business_code', '请填写编号。');
  }
  if (creating || value.label !== original.label) {
    result.label = value.label.trim();
    if (!result.label) bad('label', '请填写名称。');
  }
  if (creating || value.status !== original.status) {
    if (!['active', 'inactive'].includes(value.status)) bad('fields.status', '请明确选择启用或停用。');
    else fields.status = value.status;
  }
  const remark = value.remark.trim(), baseRemark = baseFields.remark == null ? '' : baseFields.remark;
  if (creating ? remark : value.remark !== baseRemark) fields.remark = remark || null;
  const baseAnchor = baseFields.anchor_date || '', baseCycle = baseFields.cycle_days == null ? '' : String(baseFields.cycle_days);
  if (kind === 'shift_profile' && (creating || value.anchor_date !== baseAnchor || value.cycle_days !== baseCycle || !samePattern(value.pattern, baseFields.pattern))) {
    const length = /^[0-9]+$/.test(value.cycle_days) ? Number(value.cycle_days) : null;
    if (length === null) bad('fields.cycle_days', '请填写整数轮换天数。');
    if (!isDate(value.anchor_date)) bad('fields.anchor_date', '请填写有效的周期起始日期。');
    if (length !== value.pattern.length) bad('fields.pattern', '轮换天数与逐日规则不一致，请先确认调整。');
    errors.push(...patternErrors(value.pattern));
    // 校验通过的行已是 { day_offset: 序号, is_rest: 布尔, periods: 休息日为空 }，原样提交。
    fields.anchor_date = value.anchor_date; fields.cycle_days = length; fields.pattern = value.pattern;
  }
  if (errors.length) throw failure('请核对标红的项。', { fields: errors });
  if (Object.keys(fields).length) result.fields = fields;
  return result;
}
function memberCount(kind, entity) {
  const value = entity.relationships[kind === 'machine_group' ? 'machine_count' : 'operator_count'];
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}
const APSResourceCatalogModel = { names, draft, cycle, resized, samePattern, isDirty, input, memberCount };

export { APSResourceCatalogModel, names, draft, cycle, resized, samePattern, isDirty, input, memberCount };
export default APSResourceCatalogModel;
