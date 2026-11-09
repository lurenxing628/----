(function () {
  'use strict';
  const C = window.APSResourceContract;
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
  function fields(value) {
    return C.object(value) && ['work', 'rest'].includes(value.type) && Number.isFinite(value.hours) && Number.isFinite(value.eff)
      && ['yes', 'no'].includes(value.allowNormal) && ['yes', 'no'].includes(value.allowUrgent)
      && (value.note === null || typeof value.note === 'string') && window.APSWorkPeriods.valid(value.periods);
  }
  function policy(value) {
    return C.object(value) && typeof value.explicit === 'boolean' && fields(value.fields) && C.object(value.effective)
      && typeof value.effective.is_working === 'boolean' && typeof value.effective.window_start === 'string'
      && typeof value.effective.window_end === 'string' && window.APSWorkPeriods.valid(value.effective.periods)
      && (value.explicit ? C.object(value.stored) : value.stored === null);
  }
  function day(value) {
    return policy(value) && isDate(value.date) && window.APSWorkPeriods.validDefault(value.default_periods) && (value.explicit
      ? typeof value.calendar_ref === 'string' && /^[0-9a-f]{48}$/.test(value.calendar_ref)
        && C.object(value.entity) && value.entity.ref === value.calendar_ref
      : value.calendar_ref === null && value.entity === null);
  }
  // 信封（ok、schema_version、meta、warnings）已由 transport.js 的 envelope() 校验，这里只校验 data。
  function month(result, year, number) {
    const data = result.data;
    const prefix = monthKey(year, number) + '-';
    if (data.year !== year || data.month !== number || data.time_basis !== 'factory_local' || !window.APSWorkPeriods.validDefault(data.default_periods)
        || !Array.isArray(data.days)
        || data.days.length !== monthDays(year, number) || !Array.isArray(data.cells) || data.cells.length % 7 !== 0
        || !data.days.every((row, index) => day(row) && row.date === prefix + String(index + 1).padStart(2, '0')
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
  function preview(result) {
    const data = result.data;
    if (typeof data.preview_ref !== 'string' || !/^[0-9a-f]{32}$/.test(data.preview_ref) || !Array.isArray(data.days) || !Array.isArray(data.dates)
        || !C.object(data.counts) || data.counts.selected !== data.days.length || data.dates.length !== data.days.length
        || !C.object(data.request) || !isDate(data.request.start_date) || !isDate(data.request.end_date) || data.request.start_date > data.request.end_date
        || !['all', 'weekday', 'weekend'].includes(data.request.scope) || !['upsert', 'delete'].includes(data.request.operation)
        || typeof data.expires_at !== 'string' || new Set(data.dates).size !== data.dates.length
        || !data.days.every((row, index) => isDate(row.date) && row.date === data.dates[index] && day(row.before)
          && row.before.date === row.date && policy(row.after) && typeof row.changed === 'boolean')
        || data.counts.changed !== data.days.filter(row => row.changed).length
        || data.counts.unchanged !== data.days.length - data.counts.changed
        || data.dates.join() !== rangeDates(data.request).join())
      throw C.failure('读到的变更清单不完整，没有写入。请点「重新预览变更」。');
    return result;
  }
  function draft(value) {
    if (Array.isArray(value)) return { type: 'work',
      periods: window.APSWorkPeriods.clone(value), defaultPeriods: value,
      eff: '100', allowNormal: 'yes', allowUrgent: 'yes', note: '' };
    return { type: value.fields.type, allowNormal: value.fields.allowNormal, allowUrgent: value.fields.allowUrgent,
      defaultPeriods: value.default_periods,
      periods: window.APSWorkPeriods.clone(value.fields.periods),
      eff: displayNumber(value.fields.eff), note: value.fields.note ?? '' };
  }
  function switchType(value, type) {
    if (type !== 'work' || value.type !== 'rest' || value.periods.length) return { ...value, type };
    const periods = value.defaultPeriods;
    return { ...value, type, periods: window.APSWorkPeriods.clone(periods), allowNormal: 'yes', allowUrgent: 'yes' };
  }
  function effNumber(value) {
    const result = Number(value);
    if (typeof value !== 'string' || !value.trim() || !Number.isFinite(result) || result <= 0 || result > 200)
      throw C.failure('效率须大于 0 且不超过 200%。', [{ path: 'fields.eff', message: '请输入有效数字。' }]);
    return result;
  }
  function input(value, original) {
    const periods = value.type === 'rest' ? [] : value.periods;
    const issue = window.APSWorkPeriods.validate(periods);
    if (issue) throw C.failure(issue, [{ path: 'fields.periods', message: issue }]);
    const note = value.note.trim();
    const converted = {
      type: value.type,
      periods: window.APSWorkPeriods.clone(periods),
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
  window.APSCalendarContract = { path, month, preview, monthDays, monthKey, isDate, draft, switchType, input, tag, displayNumber };
})();
