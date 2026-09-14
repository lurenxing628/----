(function () {
  'use strict';

  const C = window.APSResourceContract;
  const names = {
    machine_group: '设备组',
    shift_profile: '班次档'
  };
  const clone = value => JSON.parse(JSON.stringify(value));
  function draft(entity) {
    const fields = entity ? entity.fields : {};
    return {
      business_code: entity ? entity.business_code : '',
      label: entity ? entity.label : '',
      status: entity ? entity.status : '',
      remark: fields.remark == null ? '' : fields.remark,
      anchor_date: fields.anchor_date || '',
      cycle_days: fields.cycle_days == null ? '' : String(fields.cycle_days),
      pattern: Array.isArray(fields.pattern) ? clone(fields.pattern) : []
    };
  }
  function cycle(value) {
    if (!/^[1-9][0-9]{0,2}$/.test(value) || Number(value) > 366) throw C.failure('请填写 1 至 366 之间的整数轮换天数。', [{
      path: 'cycle_days',
      message: '轮换天数必须为 1 至 366。'
    }]);
    return Number(value);
  }
  function resized(pattern, length) {
    return Array.from({
      length
    }, (_, day_offset) => pattern[day_offset] ? {
      ...pattern[day_offset]
    } : {
      day_offset,
      is_rest: null,
      shift_start: '',
      shift_end: ''
    });
  }
  function dateValid(value) {
    if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value) || value.startsWith('0000')) return false;
    const date = new Date(value + 'T00:00:00Z');
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }
  const clockValid = value => typeof value === 'string' && /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(value);
  const minutes = value => Number(value.slice(0, 2)) * 60 + Number(value.slice(3));
  function patternErrors(pattern) {
    const errors = [];
    pattern.forEach((row, index) => {
      const bad = message => errors.push({
        path: 'pattern.' + index,
        message: '第 ' + (index + 1) + ' 天：' + message
      });
      if (row.day_offset !== index || typeof row.is_rest !== 'boolean') bad('请明确选择工作或休息。');
      if (!clockValid(row.shift_start) || !clockValid(row.shift_end)) bad('开始和结束请按 08:30 这样填。');
      const next = pattern[(index + 1) % pattern.length];
      if (row.is_rest === false && next.is_rest === false && clockValid(row.shift_start) && clockValid(row.shift_end) && clockValid(next.shift_start)) {
        const start = minutes(row.shift_start),
          end = minutes(row.shift_end);
        if (end + (end <= start ? 1440 : 0) > 1440 + minutes(next.shift_start)) bad('跨夜结束与下一轮换日开始重叠。');
      }
    });
    return errors;
  }
  function input(kind, value, original) {
    if (!names[kind]) throw C.failure('不支持这类基础资料。');
    const base = draft(original),
      creating = !original,
      result = {},
      fields = {},
      errors = [];
    const bad = (path, message) => errors.push({
      path,
      message
    });
    if (creating) {
      result.business_code = value.business_code.trim();
      if (!result.business_code) bad('business_code', '请填写编号。');
    }
    if (creating || value.label !== base.label) {
      result.label = value.label.trim();
      if (!result.label) bad('label', '请填写名称。');
    }
    if (creating || value.status !== base.status) {
      if (!['active', 'inactive'].includes(value.status)) bad('status', '请明确选择启用或停用。');else fields.status = value.status;
    }
    if (creating ? value.remark.trim() : value.remark !== base.remark) fields.remark = value.remark.trim() || null;
    if (kind === 'shift_profile' && (creating || ['anchor_date', 'cycle_days', 'pattern'].some(key => JSON.stringify(base[key]) !== JSON.stringify(value[key])))) {
      let length;
      try {
        length = cycle(value.cycle_days);
      } catch (error) {
        errors.push(...C.fieldErrors(error));
      }
      if (!dateValid(value.anchor_date)) bad('anchor_date', '请填写有效的周期起始日期。');
      if (length !== value.pattern.length) bad('pattern', '轮换天数与逐日规则不一致，请先确认调整。');
      errors.push(...patternErrors(value.pattern));
      fields.anchor_date = value.anchor_date;
      fields.cycle_days = length;
      fields.pattern = clone(value.pattern);
    }
    if (errors.length) throw C.failure('请核对标红的项。', errors);
    if (Object.keys(fields).length) result.fields = fields;
    return result;
  }
  function memberCount(kind, entity) {
    const value = entity.relationships[kind === 'machine_group' ? 'machine_count' : 'operator_count'];
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }
  window.APSResourceCatalogModel = {
    names,
    draft,
    cycle,
    resized,
    input,
    memberCount
  };
})();
