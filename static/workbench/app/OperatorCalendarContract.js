(function () {
  'use strict';

  // Load after resource-contract.js。个人日历只描述"这个人这天几点到几点上班"，工时由后端按班次起止算。
  const C = window.APSResourceContract;
  const ACTIONS = ['operator.calendar_upsert', 'operator.calendar_delete', 'operator.calendar_range_clear'];
  const CLOCK = /^([01][0-9]|2[0-3]):[0-5][0-9]$/;
  const FIELDS = ['day_type', 'shift_start', 'shift_end', 'shift_hours', 'efficiency', 'allow_normal', 'allow_urgent', 'remark'];
  const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
  const isClock = value => typeof value === 'string' && CLOCK.test(value);
  function day(value) {
    if (!C.object(value) || !isDate(value.date) || typeof value.explicit !== 'boolean') return false;
    if (!FIELDS.every(key => C.own(value, key))) return false;
    if (!value.explicit) return FIELDS.every(key => value[key] === null) && value.calendar_ref === null;
    return ['workday', 'holiday'].includes(value.day_type) && isClock(value.shift_start) && (value.shift_end === null || isClock(value.shift_end)) && typeof value.shift_hours === 'number' && Number.isFinite(value.shift_hours) && value.shift_hours >= 0 && typeof value.efficiency === 'number' && Number.isFinite(value.efficiency) && value.efficiency > 0 && ['yes', 'no'].includes(value.allow_normal) && ['yes', 'no'].includes(value.allow_urgent) && (value.remark === null || typeof value.remark === 'string') && typeof value.calendar_ref === 'string' && /^[0-9a-f]{48}$/.test(value.calendar_ref);
  }
  function envelope(raw) {
    if (raw && raw.ok === false) throw raw;
    if (!C.object(raw) || raw.ok !== true || raw.schema_version !== 1 || !C.object(raw.data) || !C.object(raw.meta) || !['production', 'demo'].includes(raw.meta.source) || raw.meta.time_basis !== 'factory_local' || !raw.meta.snapshot_ref || !raw.meta.request_ref || !raw.meta.as_of || !Array.isArray(raw.warnings)) throw C.failure('读到的个人日历数据不完整，页面没有改动。请刷新后重试。');
    return raw;
  }
  function month(raw, expected) {
    const result = envelope(raw),
      data = result.data;
    if (data.year !== expected.year || data.month !== expected.month || data.operator_ref !== expected.ref) throw C.failure('读到的个人日历不是当前人员的这个月，请刷新后重试。');
    if (!Array.isArray(data.days) || !data.days.length || !data.days.every(item => day(item) && Number.isSafeInteger(item.day) && Number.isSafeInteger(item.weekday) && typeof item.is_weekend === 'boolean' && typeof item.is_today === 'boolean')) throw C.failure('个人日历的日期内容不完整，请刷新后重试。');
    if (!Array.isArray(data.cells) || data.cells.length % 7 !== 0 || data.cells.filter(cell => cell !== null).length !== data.days.length) throw C.failure('个人日历的月历格子不完整，请刷新后重试。');
    if (!C.object(data.write_context) || !C.object(data.write_context.capabilities) || !ACTIONS.every(action => C.own(data.write_context.capabilities, action))) throw C.failure('个人日历的写入能力没有声明，暂时不能修改。请刷新后重试。');
    return result;
  }
  function draftOf(value) {
    if (!value || !value.explicit) return {
      type: 'work',
      shiftStart: '08:00',
      shiftEnd: '16:00',
      eff: '100',
      allowNormal: 'yes',
      allowUrgent: 'yes',
      note: ''
    };
    return {
      type: value.day_type === 'holiday' ? 'rest' : 'work',
      shiftStart: value.shift_start || '08:00',
      shiftEnd: value.shift_end || '',
      eff: String(Math.round(value.efficiency * 1000) / 10),
      allowNormal: value.allow_normal,
      allowUrgent: value.allow_urgent,
      note: value.remark || ''
    };
  }
  function input(draft) {
    const fields = {
      type: draft.type,
      allowNormal: draft.allowNormal,
      allowUrgent: draft.allowUrgent
    };
    const efficiency = Number(String(draft.eff).trim());
    if (!Number.isFinite(efficiency) || efficiency <= 0 || efficiency > 200) throw C.failure('效率须大于 0 且不超过 200%。', [{
      path: 'fields.eff',
      message: '请填 0 到 200 之间的数字。'
    }]);
    fields.eff = efficiency;
    if (draft.type === 'rest') {
      fields.allowNormal = 'no';
      fields.allowUrgent = 'no';
    } else {
      if (!isClock(draft.shiftStart)) throw C.failure('请填写班次开始时刻。', [{
        path: 'fields.shiftStart',
        message: '格式为 08:00。'
      }]);
      fields.shiftStart = draft.shiftStart;
      if (String(draft.shiftEnd).trim()) {
        if (!isClock(draft.shiftEnd)) throw C.failure('班次结束时刻不正确。', [{
          path: 'fields.shiftEnd',
          message: '格式为 16:00，跨零点填第二天的时刻。'
        }]);
        fields.shiftEnd = draft.shiftEnd;
      }
    }
    const note = String(draft.note == null ? '' : draft.note).trim();
    fields.note = note || null;
    return fields;
  }
  function hours(value) {
    if (!value || !value.explicit) return '';
    return window.WorkbenchFormat.hours(value.shift_hours, {
      digits: 2,
      trim: true
    });
  }
  function tag(value) {
    if (!value || !value.explicit) return {
      tone: 'none',
      text: '按班次'
    };
    if (value.shift_hours <= 0 || value.allow_normal === 'no' && value.allow_urgent === 'no') return {
      tone: 'rest',
      text: '休息'
    };
    // 没填班次结束时只写“几点起”，不用问号占位。
    return {
      tone: 'cfg',
      text: value.shift_end ? value.shift_start + '–' + value.shift_end : value.shift_start + ' 起'
    };
  }
  function rangeInput(range) {
    if (!isDate(range.start_date) || !isDate(range.end_date)) throw C.failure('请选择正确的开始和结束日期。', [{
      path: !isDate(range.start_date) ? 'start_date' : 'end_date',
      message: '日期须有效。'
    }]);
    if (range.start_date > range.end_date) throw C.failure('结束日期不能早于开始日期。', [{
      path: 'end_date',
      message: '结束日期不能早于开始日期。'
    }]);
    return {
      start_date: range.start_date,
      end_date: range.end_date
    };
  }
  function rangePreview(raw, expected) {
    const result = envelope(raw),
      data = result.data;
    if (!C.object(data.range) || data.range.start_date !== expected.start_date || data.range.end_date !== expected.end_date) throw C.failure('预检的日期范围和选的不一致，没有清除任何设置。请重新点「预检要清除的日期」。');
    if (!Number.isSafeInteger(data.count) || data.count < 0 || !Array.isArray(data.days) || data.days.length !== data.count || !data.days.every(item => day(item) && item.explicit)) throw C.failure('预检内容不完整，没有清除任何设置。');
    if (!C.object(data.write_context)) throw C.failure('清除能力没有声明，没有清除任何设置。');
    return result;
  }
  window.APSOperatorCalendar = {
    envelope,
    month,
    draftOf,
    input,
    hours,
    tag,
    rangeInput,
    rangePreview,
    isDate,
    isClock,
    ACTIONS
  };
})();
