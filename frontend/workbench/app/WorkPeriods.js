(function () {
  'use strict';
  const defaults = () => [{ start: "08:30", end: "11:50", day_offset: 0 }, { start: "13:30", end: "17:30", day_offset: 0 }];
  const clock = value => typeof value === 'string' && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
  const minutes = value => Number(value.slice(0, 2)) * 60 + Number(value.slice(3));
  const clone = value => value == null ? null : value.map(row => ({ ...row }));
  function bounds(row) {
    const start = minutes(row.start), end = minutes(row.end), offset = row.day_offset * 1440;
    return [start + offset, end + offset + (end <= start ? 1440 : 0)];
  }
  function validate(value) {
    if (!Array.isArray(value) || value.length > 8) return '每天最多填写 8 个工作时段。';
    let previous = null, first = null;
    for (const row of value) {
      if (!clock(row.start) || !clock(row.end)) return '请补齐每段开始和结束时刻。';
      if (![0, 1].includes(row.day_offset) || first === null && row.day_offset !== 0) return '首段须从当天开始。';
      const [low, high] = bounds(row);
      if (first === null) first = low;
      if (previous !== null && low < previous) return '工作时段应按时间先后填写，不能重叠。';
      if (high > first + 1440) return '全部工作时段不能跨越超过 24 小时。';
      previous = high;
    }
    return null;
  }
  function hours(value) {
    return validate(value) ? null : value.reduce((sum, row) => { const [low, high] = bounds(row); return sum + high - low; }, 0) / 60;
  }
  const duration = value => { const total = Math.round(value * 60); return Math.floor(total / 60) + ' 小时' + (total % 60 ? ' ' + total % 60 + ' 分钟' : ''); };
  function describe(value) {
    return value.map(row => (row.day_offset ? '次日 ' : '') + row.start + '–'
      + (row.end <= row.start ? '次日 ' : '') + row.end).join('、') || '无工作时段';
  }
  window.APSWorkPeriods = { defaults, clone, validate, hours, describe, bounds, duration };
})();
