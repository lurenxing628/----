(function () {
  'use strict';
  const C = window.APSResourceContract;
  const path = '/api/workbench/v1/calendar';
  const keys = ['type', 'hours', 'eff', 'allowNormal', 'allowUrgent', 'note'];
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
      throw C.failure('日历读取协议不完整，未使用样例替代。');
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
      throw C.failure('月份、日期或统计信息不完整，请重新读取日历。');
    return result;
  }
  function rangeDates(request) {
    if (!isDate(request.start_date) || !isDate(request.end_date) || request.start_date > request.end_date)
      throw C.failure('预览日期范围不正确。');
    const cursor = new Date(request.start_date + 'T12:00:00'), selected = [];
    for (let count = 0; count < 36500; count++) {
      const key = monthKey(cursor.getFullYear(), cursor.getMonth() + 1) + '-' + String(cursor.getDate()).padStart(2, '0');
      const weekend = [0, 6].includes(cursor.getDay());
      if (request.scope === 'all' || (request.scope === 'weekend') === weekend) selected.push(key);
      if (key === request.end_date) return selected;
      cursor.setDate(cursor.getDate() + 1);
    }
    throw C.failure('预览范围超出日历服务支持的 36500 天，不能确认。');
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
      throw C.failure('批量预览不完整，不能确认写入。请重新预览。');
    return result;
  }
  function draft(value) {
    return { ...value.fields, hours: displayNumber(value.fields.hours), eff: displayNumber(value.fields.eff), note: value.fields.note || '' };
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
    // A default date has no stored row; creating it must not inherit different domain defaults.
    if (!original || !original.explicit) return converted;
    const output = {};
    keys.forEach(key => {
      const before = original && (['hours', 'eff'].includes(key) ? Number(displayNumber(original.fields[key])) : original.fields[key]);
      if (C.own(converted, key) && converted[key] !== before) output[key] = converted[key];
    });
    return output;
  }
  function stale(command) {
    const error = command.error;
    return command.phase === 'rejected' && ['stale_write', 'snapshot_stale'].includes(error && (error.code || error.error && error.error.code));
  }
  function tag(row) {
    const working = row.effective.is_working;
    let text = working ? displayNumber(row.fields.hours) + 'h' : '休';
    let tone = row.is_weekend ? 'we' : '';
    if (row.explicit) {
      tone = row.is_weekend === working ? 'rest' : working ? 'cfg' : 'we';
      text = row.is_weekend && working ? '加班 ' + displayNumber(row.fields.hours) + 'h' : !row.is_weekend && !working ? '调休' : text;
      if (working && row.fields.allowNormal !== row.fields.allowUrgent) text += row.fields.allowNormal === 'yes' ? ' 普' : ' 急';
    }
    return { tone, text };
  }
  window.APSCalendarContract = { path, month, preview, monthDays, monthKey, isDate, draft, input, stale, tag, rangeDates, displayNumber };
})();
