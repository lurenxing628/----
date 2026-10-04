(function () {
  'use strict';
  const C = window.APSResourceContract;
  const path = '/api/workbench/v1/calendar';
  const keys = ['type', 'hours', 'eff', 'allowNormal', 'allowUrgent', 'note', 'shiftStart', 'shiftEnd', 'periods'];
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
  function fields(value) {
    return C.object(value) && ['work', 'rest'].includes(value.type) && Number.isFinite(value.hours) && Number.isFinite(value.eff)
      && ['yes', 'no'].includes(value.allowNormal) && ['yes', 'no'].includes(value.allowUrgent)
      && (value.note === null || typeof value.note === 'string');
  }
  function policy(value) {
    return C.object(value) && typeof value.explicit === 'boolean' && fields(value.fields) && C.object(value.effective)
      && typeof value.effective.is_working === 'boolean' && typeof value.effective.window_start === 'string'
      && typeof value.effective.window_end === 'string' && (value.explicit ? C.object(value.stored) : value.stored === null);
  }
  function day(value) {
    return policy(value) && isDate(value.date) && (value.explicit
      ? typeof value.calendar_ref === 'string' && /^[0-9a-f]{48}$/.test(value.calendar_ref)
        && C.object(value.entity) && value.entity.ref === value.calendar_ref
      : value.calendar_ref === null && value.entity === null);
  }
  function envelope(raw) {
    if (raw && raw.ok === false) throw raw;
    if (!C.object(raw) || raw.ok !== true || raw.schema_version !== 1 || !C.object(raw.data) || !C.object(raw.meta)
        || !['production', 'demo'].includes(raw.meta.source) || raw.meta.time_basis !== 'factory_local'
        || !raw.meta.snapshot_ref || !raw.meta.request_ref || !raw.meta.as_of || !Array.isArray(raw.warnings))
      throw C.failure('读到的工作日历数据不完整，页面没有改动。请刷新后重试。');
    return raw;
  }
  function month(raw, year, number) {
    const result = envelope(raw), data = result.data;
    if (data.year !== year || data.month !== number || data.time_basis !== 'factory_local' || !Array.isArray(data.days)
        || data.days.length !== monthDays(year, number) || !Array.isArray(data.cells) || data.cells.length % 7 !== 0
        || !data.days.every((row, index) => day(row) && row.date === monthKey(year, number) + '-' + String(index + 1).padStart(2, '0')
          && row.day === index + 1 && Number.isInteger(row.weekday) && row.weekday >= 0 && row.weekday <= 6
          && typeof row.is_weekend === 'boolean' && typeof row.is_today === 'boolean')
        || data.cells.filter(Boolean).map(row => row.date).join() !== data.days.map(row => row.date).join()
        || data.cells.length !== Math.ceil((data.days[0].weekday + data.days.length) / 7) * 7
        || data.cells.slice(0, data.days[0].weekday).some(Boolean)
        || !C.object(data.stats) || !['work_days', 'configured', 'overrides', 'weekend_rest'].every(key => Number.isSafeInteger(data.stats[key]) && data.stats[key] >= 0))
      throw C.failure('读到的月份、日期或统计数据不完整，页面没有改动。请刷新后重试。');
    return result;
  }
  function rangeDates(request) {
    if (!isDate(request.start_date) || !isDate(request.end_date) || request.start_date > request.end_date)
      throw C.failure('日期范围不正确，没有查看变更。请重新选择开始日期和结束日期。');
    const cursor = new Date(request.start_date + 'T12:00:00'), selected = [];
    for (let count = 0; count < 36500; count++) {
      const key = monthKey(cursor.getFullYear(), cursor.getMonth() + 1) + '-' + String(cursor.getDate()).padStart(2, '0');
      const weekend = [0, 6].includes(cursor.getDay());
      if (request.scope === 'all' || (request.scope === 'weekend') === weekend) selected.push(key);
      if (key === request.end_date) return selected;
      cursor.setDate(cursor.getDate() + 1);
    }
    throw C.failure('日期范围超过 36500 天，没有查看变更。请缩小日期范围后重试。');
  }
  function preview(raw) {
    const result = envelope(raw), data = result.data;
    if (!/^[0-9a-f]{32}$/.test(data.preview_ref || '') || !Array.isArray(data.days) || !Array.isArray(data.dates)
        || !C.object(data.counts) || data.counts.selected !== data.days.length || data.dates.length !== data.days.length
        || !C.object(data.request) || !isDate(data.request.start_date) || !isDate(data.request.end_date)
        || !['all', 'weekday', 'weekend'].includes(data.request.scope) || !['upsert', 'delete'].includes(data.request.operation)
        || typeof data.expires_at !== 'string' || new Set(data.dates).size !== data.dates.length
        || !data.days.every((row, index) => isDate(row.date) && row.date === data.dates[index] && day(row.before)
          && row.before.date === row.date && policy(row.after) && typeof row.changed === 'boolean')
        || data.counts.changed !== data.days.filter(row => row.changed).length
        || data.counts.unchanged !== data.days.filter(row => !row.changed).length
        || data.dates.join() !== rangeDates(data.request).join())
      throw C.failure('读到的变更清单不完整，没有写入。请点「重新预览变更」。');
    return result;
  }
  function draft(value) {
    // legacyShift：原记录是没有逐段时段的旧单班工作日，休息改回工作日时恢复原班次，不填默认时段。
    return { ...value.fields, defaultPeriods: value.default_periods, legacyShift: value.fields.type === 'work' && value.fields.periods == null,
      periods: value.fields.periods == null ? null : value.fields.periods.map(row => ({ ...row })), shiftStart: value.stored && value.stored.shift_start || value.effective.window_start.slice(11, 16),
      shiftEnd: value.stored && value.stored.shift_end || '', hours: displayNumber(value.fields.hours), eff: displayNumber(value.fields.eff), note: value.fields.note || '' };
  }
  // 切换「这一天是否排产」。休息改回工作日时：草稿里还留着逐段时段，或原记录是旧单班工作日（periods 为 null），
  // 就原样恢复原班次起点和工时；原本是休息日、没单独设置或时段被清空时，才填默认工作时间。
  function switchType(value, type) {
    if (type !== 'work' || value.type !== 'rest' || value.periods?.length || value.periods == null && value.legacyShift) return { ...value, type };
    const periods = value.defaultPeriods || window.APSWorkPeriods.defaults();
    return { ...value, type, periods: window.APSWorkPeriods.clone(periods), hours: String(window.APSWorkPeriods.hours(periods)), allowNormal: 'yes', allowUrgent: 'yes' };
  }
  function number(value, key) {
    const result = Number(value);
    if (typeof value !== 'string' || !value.trim() || !Number.isFinite(result) || result < 0
        || result > (key === 'hours' ? 24 : 200) || key === 'eff' && result === 0)
      throw C.failure(key === 'hours' ? '可排工时须为 0 至 24 小时。' : '效率须大于 0 且不超过 200%。',
        [{ path: 'fields.' + key, message: '请输入有效数字。' }]);
    return result;
  }
  function input(value, original) {
    const converted = { type: value.type, note: value.note.trim() || null };
    if (value.type === 'work') Object.assign(converted, { hours: number(value.hours, 'hours'), eff: number(value.eff, 'eff'),
      allowNormal: value.allowNormal, allowUrgent: value.allowUrgent });
    if (value.type === 'work' && value.shiftStart) converted.shiftStart = value.shiftStart;
    if (value.type === 'work' && value.shiftEnd !== undefined) converted.shiftEnd = value.shiftEnd || null;
    if (Array.isArray(value.periods)) {
      const periods = value.type === 'rest' ? [] : value.periods, issue = window.APSWorkPeriods.validate(periods);
      if (issue) throw C.failure(issue, [{ path: 'fields.periods', message: issue }]);
      converted.periods = window.APSWorkPeriods.clone(periods);
      delete converted.shiftStart; delete converted.shiftEnd;
      if (value.type === 'work') converted.hours = window.APSWorkPeriods.hours(periods);
    }
    // A default date has no stored row; creating it must not inherit different domain defaults.
    if (!original || !original.explicit) return converted;
    const output = {};
    keys.forEach(key => {
      // 有逐段时段时工时由时段算出：时段没改就不比较、不提交工时，免得换算末位差异被当成改了工时。
      if (key === 'hours' && C.own(converted, 'periods') && JSON.stringify(converted.periods) === JSON.stringify(original.fields.periods)) return;
      const before = ['shiftStart', 'shiftEnd'].includes(key) ? draft(original)[key] || null
        : (['hours', 'eff'].includes(key) ? Number(displayNumber(original.fields[key])) : original.fields[key]);
      if (C.own(converted, key) && JSON.stringify(converted[key]) !== JSON.stringify(before)) output[key] = converted[key];
    });
    return output;
  }
  function stale(command) {
    const error = command.error;
    return command.phase === 'rejected' && ['stale_write', 'snapshot_stale'].includes(error && (error.code || error.error && error.error.code));
  }
  // 月历格子里的工时带单位显示，数字格式和单位统一走 WorkbenchFormat，不在这里手拼“小时”。
  const hoursText = value => window.APSWorkPeriods.duration(value);
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
  window.APSCalendarContract = { path, month, preview, monthDays, monthKey, isDate, draft, switchType, input, stale, tag, rangeDates, displayNumber };
})();
