(function () {
  'use strict';
  // Load after resource-contract.js。个人日历只描述"这个人这天哪几个时段上班"，工时由后端按工作时段算。
  const C = window.APSResourceContract;
  const ACTIONS = ['operator.calendar_upsert', 'operator.calendar_delete', 'operator.calendar_range_clear'];
  const FIELDS = ['day_type', 'efficiency', 'allow_normal', 'allow_urgent', 'remark'];
  const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    && new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
  function day(value) {
    if (!C.object(value) || !isDate(value.date) || typeof value.explicit !== 'boolean') return false;
    if (!FIELDS.every(key => C.own(value, key))) return false;
    if (!value.explicit) return FIELDS.every(key => value[key] === null) && value.calendar_ref === null;
    return ['workday', 'holiday'].includes(value.day_type)
      && typeof value.efficiency === 'number' && Number.isFinite(value.efficiency) && value.efficiency > 0
      && ['yes', 'no'].includes(value.allow_normal) && ['yes', 'no'].includes(value.allow_urgent)
      && (value.remark === null || typeof value.remark === 'string') && window.APSWorkPeriods.valid(value.periods)
      && typeof value.calendar_ref === 'string' && /^[0-9a-f]{48}$/.test(value.calendar_ref);
  }
  // 信封（ok、schema_version、meta、warnings）已由 transport.js 的 envelope() 校验，这里只校验 data。
  function month(result, expected) {
    const data = result.data;
    if (data.year !== expected.year || data.month !== expected.month || data.operator_ref !== expected.ref)
      throw C.failure('读到的个人日历不是当前人员的这个月，请刷新后重试。');
    if (!Array.isArray(data.days) || !data.days.length || !data.days.every(item => day(item)
        && window.APSWorkPeriods.validDefault(item.default_periods)
        && Number.isSafeInteger(item.day) && Number.isSafeInteger(item.weekday)
        && typeof item.is_weekend === 'boolean' && typeof item.is_today === 'boolean'))
      throw C.failure('个人日历的日期内容不完整，请刷新后重试。');
    if (!Array.isArray(data.cells) || data.cells.length % 7 !== 0
        || data.cells.filter(cell => cell !== null).length !== data.days.length)
      throw C.failure('个人日历的月历格子不完整，请刷新后重试。');
    if (!C.object(data.write_context) || !C.object(data.write_context.capabilities)
        || !ACTIONS.every(action => C.own(data.write_context.capabilities, action)))
      throw C.failure('个人日历的写入能力没有声明，暂时不能修改。请刷新后重试。');
    return result;
  }
  function draftOf(value) {
    if (!value.explicit) return { type: 'work', eff: '100',
      allowNormal: 'yes', allowUrgent: 'yes', note: '', periods: window.APSWorkPeriods.clone(value.default_periods) };
    return {
      periods: window.APSWorkPeriods.clone(value.periods),
      type: value.day_type === 'holiday' ? 'rest' : 'work',
      eff: String(Number((value.efficiency * 100).toPrecision(15))),
      allowNormal: value.allow_normal, allowUrgent: value.allow_urgent, note: value.remark === null ? '' : value.remark
    };
  }
  // 只有从休息改回上班且当前时段已清空时才补默认工作时间；已经是上班或草稿里还有逐段时段时保持原样。
  function switchType(day, draft, type) {
    if (type !== 'work' || draft.type !== 'rest' || draft.periods.length) return { ...draft, type };
    return { ...draft, type, periods: window.APSWorkPeriods.clone(day.default_periods) };
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
    const issue = window.APSWorkPeriods.validate(periods);
    if (issue) throw C.failure(issue, [{ path: 'fields.periods', message: issue }]);
    fields.periods = window.APSWorkPeriods.clone(periods);
    const note = draft.note.trim();
    fields.note = note === '' ? null : note;
    return fields;
  }
  function tag(value) {
    if (!value || !value.explicit) return { tone: 'none', text: '按班次' };
    if (!value.periods.length || value.allow_normal === 'no' && value.allow_urgent === 'no')
      return { tone: 'rest', text: '休息' };
    return { tone: 'cfg', text: window.APSWorkPeriods.describe(value.periods) };
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
    if (!Number.isSafeInteger(data.count) || data.count < 0 || !Array.isArray(data.days)
        || data.days.length !== data.count || !data.days.every(item => day(item) && item.explicit))
      throw C.failure('预检内容不完整，没有清除任何设置。');
    if (!C.object(data.write_context)) throw C.failure('清除能力没有声明，没有清除任何设置。');
    return result;
  }
  window.APSOperatorCalendar = { month, draftOf, switchType, input, tag, rangeInput, rangePreview };
})();
