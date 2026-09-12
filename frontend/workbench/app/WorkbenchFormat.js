(function () {
  'use strict';
  const unknown = '未知';
  const empty = value => value === null || value === undefined || value === '';
  const pad = value => String(value).padStart(2, '0');
  function invalid(kind) { throw new TypeError('无法显示：' + kind + '格式不正确。'); }
  function parts(value, dateOnly) {
    if (typeof value !== 'string') return invalid('日期时间');
    const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?$/.exec(value);
    if (!match || !dateOnly && match[4] === undefined) return invalid('日期时间');
    const year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1] ||
        Number(match[4] || 0) > 23 || Number(match[5] || 0) > 59 || Number(match[6] || 0) > 59) return invalid('日期时间');
    return match;
  }
  function dateTime(value, { seconds = false } = {}) {
    if (empty(value)) return unknown;
    if (typeof seconds !== 'boolean') return invalid('日期时间选项');
    const p = parts(value, false);
    return p[1] + '-' + p[2] + '-' + p[3] + ' ' + p[4] + ':' + p[5] + (seconds ? ':' + (p[6] || '00') : '');
  }
  function date(value) {
    if (empty(value)) return unknown;
    const p = parts(value, true);
    return p[1] + '-' + p[2] + '-' + p[3];
  }
  function instant(value, { seconds = false } = {}) {
    if (empty(value)) return unknown;
    if (typeof value !== 'string' || typeof seconds !== 'boolean') return invalid('时刻');
    const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/.exec(value);
    if (!match) return invalid('时刻');
    parts(match[1] + 'T' + match[2] + (match[3] || ''), false);
    if (match[4] !== 'Z' && (Number(match[4].slice(1, 3)) > 23 || Number(match[4].slice(4)) > 59)) return invalid('时区');
    const point = new Date(value);
    if (!Number.isFinite(point.getTime())) return invalid('时刻');
    const year = point.getFullYear();
    if (year < 1 || year > 9999) return invalid('时刻');
    return String(year).padStart(4, '0') + '-' + pad(point.getMonth() + 1) + '-' + pad(point.getDate()) + ' ' +
      pad(point.getHours()) + ':' + pad(point.getMinutes()) + (seconds ? ':' + pad(point.getSeconds()) : '');
  }
  // digits: fixed decimals (default 1). trim: drop trailing zeros so "up to `digits` decimals" is possible for
  // values whose stored precision matters (entered hours, cumulative totals, candidate comparisons).
  function numberOptions(options, kind) {
    const source = options === undefined ? {} : typeof options === 'number' ? { digits: options } : options;
    if (source === null || typeof source !== 'object') return invalid(kind);
    const { digits = 1, trim = false } = source;
    if (!Number.isInteger(digits) || digits < 0 || digits > 20 || typeof trim !== 'boolean') return invalid(kind);
    return { digits, trim };
  }
  function signedZero(value, digits) {
    // A value that rounds to zero must not read as "-0.0": nothing was reduced.
    return Number(value.toFixed(digits)) === 0 ? 0 : value;
  }
  function number(value, options) {
    if (empty(value)) return unknown;
    const { digits, trim } = numberOptions(options, '数值');
    if (typeof value !== 'number' || !Number.isFinite(value)) return invalid('数值');
    return signedZero(value, digits).toLocaleString('zh-CN', { minimumFractionDigits: trim ? 0 : digits, maximumFractionDigits: digits });
  }
  function integerText(value) {
    if (empty(value)) return unknown;
    if (typeof value !== 'string' || !/^(?:0|[1-9]\d*)$/.test(value)) return invalid('整数字符串');
    const first = value.length % 3 || 3, groups = [value.slice(0, first)];
    for (let index = first; index < value.length; index += 3) groups.push(value.slice(index, index + 3));
    return groups.join(',');
  }
  function percent(ratio, options) {
    if (empty(ratio)) return unknown;
    const { digits, trim } = numberOptions(options, '百分比');
    if (typeof ratio !== 'number' || !Number.isFinite(ratio)) return invalid('百分比');
    return signedZero(ratio, digits + 2).toLocaleString('zh-CN', { style: 'percent', minimumFractionDigits: trim ? 0 : digits, maximumFractionDigits: digits });
  }
  function hours(value, options) {
    if (empty(value)) return unknown;
    numberOptions(options, '工时');
    if (typeof value !== 'number' || !Number.isFinite(value)) return invalid('工时');
    return number(value, options) + ' h';
  }
  window.WorkbenchFormat = Object.freeze({ dateTime, date, instant, number, integerText, percent, hours });
})();
