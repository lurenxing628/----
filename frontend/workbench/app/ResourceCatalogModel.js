(function () {
  'use strict';
  const C = window.APSResourceContract;
  const names = { machine_group: '设备组', shift_profile: '班次档' };
  function draft(entity) {
    const fields = entity ? entity.fields : {};
    return { business_code: entity ? entity.business_code : '', label: entity ? entity.label : '',
      status: entity ? entity.status : '', remark: fields.remark == null ? '' : fields.remark,
      anchor_date: fields.anchor_date || '', cycle_days: fields.cycle_days == null ? '' : String(fields.cycle_days),
      pattern: Array.isArray(fields.pattern) ? fields.pattern : [] };
  }
  function cycle(value) {
    if (!/^[1-9][0-9]{0,2}$/.test(value) || Number(value) > 366)
      throw C.failure('请填写 1 至 366 之间的整数轮换天数。', [{ path: 'cycle_days', message: '轮换天数必须为 1 至 366。' }]);
    return Number(value);
  }
  function resized(pattern, length) {
    return Array.from({ length }, (_, day_offset) => pattern[day_offset] ||
      { day_offset, is_rest: null, periods: [] });
  }
  function dateValid(value) {
    if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value) || value.startsWith('0000')) return false;
    const date = new Date(value + 'T00:00:00Z');
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }
  function patternErrors(pattern) {
    const errors = [];
    const issues = pattern.map(row => window.APSWorkPeriods.validate(row.periods));
    pattern.forEach((row, index) => {
      const bad = message => errors.push({ path: 'pattern.' + index, message: '第 ' + (index + 1) + ' 天：' + message });
      if (row.day_offset !== index || typeof row.is_rest !== 'boolean') bad('请明确选择工作或休息。');
      if (row.is_rest === true && row.periods.length) bad('休息日不能填写工作时段。');
      if (row.is_rest === false && !row.periods.length) bad('工作日请至少填写一个工作时段，或明确改为休息日。');
      const issue = issues[index];
      if (issue) {
        bad(issue);
        return;
      }
      const nextIndex = (index + 1) % pattern.length;
      const next = pattern[nextIndex];
      if (row.is_rest === false && next.is_rest === false && row.periods.length
          && next.periods.length && !issues[nextIndex]) {
        const last = window.APSWorkPeriods.bounds(row.periods[row.periods.length - 1])[1];
        const nextFirst = window.APSWorkPeriods.bounds(next.periods[0])[0];
        if (last > 1440 + nextFirst) bad('跨夜结束与下一轮换日开始重叠。');
      }
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
    if (!names[kind]) throw C.failure('不支持这类基础资料。');
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
      if (!['active', 'inactive'].includes(value.status)) bad('status', '请明确选择启用或停用。');
      else fields.status = value.status;
    }
    const remark = value.remark.trim(), baseRemark = baseFields.remark == null ? '' : baseFields.remark;
    if (creating ? remark : value.remark !== baseRemark) fields.remark = remark || null;
    const baseAnchor = baseFields.anchor_date || '', baseCycle = baseFields.cycle_days == null ? '' : String(baseFields.cycle_days);
    if (kind === 'shift_profile' && (creating || value.anchor_date !== baseAnchor || value.cycle_days !== baseCycle || !samePattern(value.pattern, baseFields.pattern))) {
      let length;
      try { length = cycle(value.cycle_days); } catch (error) { errors.push(...C.fieldErrors(error)); }
      if (!dateValid(value.anchor_date)) bad('anchor_date', '请填写有效的周期起始日期。');
      if (length !== value.pattern.length) bad('pattern', '轮换天数与逐日规则不一致，请先确认调整。');
      errors.push(...patternErrors(value.pattern));
      // 校验通过的行已是 { day_offset: 序号, is_rest: 布尔, periods: 休息日为空 }，原样提交。
      fields.anchor_date = value.anchor_date; fields.cycle_days = length; fields.pattern = value.pattern;
    }
    if (errors.length) throw C.failure('请核对标红的项。', errors);
    if (Object.keys(fields).length) result.fields = fields;
    return result;
  }
  function memberCount(kind, entity) {
    const value = entity.relationships[kind === 'machine_group' ? 'machine_count' : 'operator_count'];
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }
  window.APSResourceCatalogModel = { names, draft, cycle, resized, samePattern, isDirty, input, memberCount };
})();
