(function () {
  'use strict';
  const C = window.APSCalendarContract;
  const types = ['date', 'time', 'month', 'datetime-local'];
  const pad = (value, size = 2) => String(value).padStart(size, '0');
  const monthKey = (year, month) => pad(year, 4) + '-' + pad(month);
  const dateKey = (year, month, day) => monthKey(year, month) + '-' + pad(day);
  const monthParts = value => typeof value === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)
    && Number(value.slice(0, 4)) >= 1 ? [Number(value.slice(0, 4)), Number(value.slice(5))] : null;
  const dateParts = value => C.isDate(value) ? value.split('-').map(Number) : null;
  function today() {
    const now = new Date();
    return dateKey(now.getFullYear(), now.getMonth() + 1, now.getDate());
  }
  function weekday(value) {
    const [year, month, day] = dateParts(value), previous = year - 1;
    let count = previous * 365 + Math.floor(previous / 4) - Math.floor(previous / 100) + Math.floor(previous / 400) + day - 1;
    for (let i = 1; i < month; i++) count += C.monthDays(year, i);
    return count % 7;
  }
  function moveDay(value, offset) {
    let [year, month, day] = dateParts(value);
    const direction = Math.sign(offset);
    for (let i = 0; i < Math.abs(offset); i++) {
      if (direction < 0 && year === 1 && month === 1 && day === 1) break;
      if (direction > 0 && year === 9999 && month === 12 && day === 31) break;
      day += direction;
      if (day < 1) { month--; if (month === 0) { year--; month = 12; } day = C.monthDays(year, month); }
      if (day > C.monthDays(year, month)) { day = 1; month++; if (month === 13) { year++; month = 1; } }
    }
    return dateKey(year, month, day);
  }
  function moveMonth(value, offset) {
    const [year, month, day = 1] = value.split('-').map(Number);
    const index = Math.max(0, Math.min(9999 * 12 - 1, (year - 1) * 12 + month - 1 + offset));
    const nextYear = Math.floor(index / 12) + 1, nextMonth = index % 12 + 1;
    return dateKey(nextYear, nextMonth, Math.min(day, C.monthDays(nextYear, nextMonth)));
  }
  function nativeField(props) {
    const input = document.createElement('input');
    input.type = props.type;
    ['min', 'max', 'step'].forEach(key => { if (props[key] !== undefined && props[key] !== null) input.setAttribute(key, String(props[key])); });
    // Preserve the original value attribute: it is the native step base when min is absent.
    input.setAttribute('value', (props.valueAttribute === undefined ? props.value : props.valueAttribute) || '');
    return input;
  }
  function hasShape(type, value) {
    if (type === 'date') return !!dateParts(value);
    if (type === 'month') return !!monthParts(value);
    if (type === 'time') return /^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,3})?)?$/.test(value);
    if (type === 'datetime-local') {
      const parts = value.split('T');
      return parts.length === 2 && !!dateParts(parts[0]) && hasShape('time', parts[1]);
    }
    return false;
  }
  function validate(props, value) {
    if (!types.includes(props.type)) return { valid: false, message: '不支持的日期或时间类型。' };
    if (!value || !hasShape(props.type, value)) return { valid: false, message: '请选择完整、有效的日期或时间。' };
    const input = nativeField(props); input.value = value;
    if (input.value && input.checkValidity()) return { valid: true, value: input.value, message: '' };
    const validity = input.validity;
    if (validity.rangeUnderflow && validity.rangeOverflow) return { valid: false, message: '时间须在 ' + props.min + ' 至次日 ' + props.max + ' 之间。' };
    if (validity.rangeUnderflow) return { valid: false, message: '不能早于 ' + props.min + '。' };
    if (validity.rangeOverflow) return { valid: false, message: '不能晚于 ' + props.max + '。' };
    if (validity.stepMismatch) return { valid: false, message: '所选值不符合间隔要求，请调整后确认。' };
    return { valid: false, message: '请选择完整、有效的日期或时间。' };
  }
  function daySelectable(props, day) {
    if (props.type !== 'datetime-local') return validate(props, day).valid;
    const input = nativeField(props), start = day + 'T00:00';
    input.value = start;
    if (input.checkValidity()) return true;
    // Ask the same native constraint engine for the next allowed instant, without opening its UI.
    if (String(props.step).toLowerCase() === 'any') input.value = props.min || '';
    else { input.stepUp(0); if (!input.checkValidity()) { input.value = start; input.stepUp(); } }
    return input.value.slice(0, 10) === day && input.checkValidity();
  }
  function monthSelectable(props, month) {
    const parts = monthParts(month);
    if (!parts) return false;
    if (props.type === 'month') return validate(props, month).valid;
    if (!['date', 'datetime-local'].includes(props.type)) return false;
    // Month navigation keeps the original date/time constraints, including their step base.
    for (let day = 1; day <= C.monthDays(parts[0], parts[1]); day++) {
      if (daySelectable(props, month + '-' + pad(day))) return true;
    }
    return false;
  }
  function precision(props) {
    const values = [props.value, props.valueAttribute, props.min, props.max].filter(value => typeof value === 'string');
    const numericStep = Number(props.step), step = Number.isFinite(numericStep) && numericStep > 0 ? numericStep : 60;
    const any = String(props.step).toLowerCase() === 'any';
    const fraction = any || step > 0 && step % 1 !== 0 || values.some(value => /:\d{2}\.\d+$/.test(value));
    return { seconds: fraction || step > 0 && step % 60 !== 0 || values.some(value => /\d{2}:\d{2}:\d{2}/.test(value)), fraction };
  }
  function readTime(value, units) {
    const raw = (value || '').split('T').pop();
    if (!hasShape('time', raw)) return { hour: '', minute: '', second: '', millisecond: '' };
    const parts = raw.split(':'), fraction = (parts[2] || '').split('.');
    return { hour: parts[0], minute: parts[1], second: units.seconds ? fraction[0] || '00' : '',
      millisecond: units.fraction ? (fraction[1] || '').padEnd(3, '0') : '' };
  }
  function timeValue(time, units) {
    const required = ['hour', 'minute'].concat(units.seconds ? ['second'] : [], units.fraction ? ['millisecond'] : []);
    const limits = { hour: 23, minute: 59, second: 59, millisecond: 999 };
    if (required.some(key => !/^\d+$/.test(time[key]) || Number(time[key]) > limits[key])) return '';
    let value = pad(Number(time.hour)) + ':' + pad(Number(time.minute));
    if (units.seconds) value += ':' + pad(Number(time.second));
    if (units.fraction) value += '.' + pad(Number(time.millisecond), 3);
    return value;
  }
  function seed(props) {
    const current = (props.value || '').slice(0, 10), minimum = (props.min || '').slice(0, 10);
    return dateParts(current) ? current : monthParts(current) ? current + '-01'
      : dateParts(minimum) ? minimum : monthParts(minimum) ? minimum + '-01' : today();
  }
  window.WorkbenchDatePickerModel = { types, pad, monthKey, dateKey, monthParts, dateParts, today, weekday,
    moveDay, moveMonth, nativeField, hasShape, validate, daySelectable, monthSelectable, precision, readTime, timeValue, seed };
})();
