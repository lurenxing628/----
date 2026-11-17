// 报工有效工时的唯一精确算术，与后端 core/models/hours.py 的 sum_hours / HourTotals / exact_hours_text 同口径。
// 后端给每条报工的规范十进制串（无指数、无多余的零，零写 "0"）；解析成 BigInt 系数加小数位数，对齐小数位后整数相加。
// 展示用的数字只在最后由 hoursNumber 转换一次，不回流参与求和。
const CANONICAL = /^(0|[1-9]\d*)(?:\.(\d*[1-9]))?$/;
const TEN = BigInt(10);

// 规范十进制串 → { coefficient, scale }，值为 coefficient / 10^scale；不是规范串时为 null。
function parseHours(text) {
  const match = typeof text === 'string' && CANONICAL.exec(text);
  if (!match) return null;
  const fraction = match[2] || '';
  return { coefficient: BigInt(match[1] + fraction), scale: fraction.length };
}

function add(left, right) {
  const scale = Math.max(left.scale, right.scale);
  return { coefficient: left.coefficient * TEN ** BigInt(scale - left.scale) + right.coefficient * TEN ** BigInt(scale - right.scale), scale };
}

// 一组报工的合计 { known, unknown }：null 是一条工时未知的报工；known 是已知工时之和，没有已知时为 null；unknown 是未知条数。
function sumHours(amounts) {
  let known = null, unknown = 0;
  for (const amount of amounts) {
    if (amount === null) unknown++;
    else known = known === null ? amount : add(known, amount);
  }
  return { known, unknown };
}

// 把互不重叠的几组合计并成一组，结果与直接对全部报工 sumHours 相同。
function combineHours(parts) {
  let known = null, unknown = 0;
  for (const part of parts) {
    if (part.known !== null) known = known === null ? part.known : add(known, part.known);
    unknown += part.unknown;
  }
  return { known, unknown };
}

// 精确量的规范十进制串：无指数、去掉小数尾零，零为 "0"。
function exactHoursText(amount) {
  const digits = amount.coefficient.toString().padStart(amount.scale + 1, '0');
  const integer = digits.slice(0, digits.length - amount.scale), fraction = digits.slice(digits.length - amount.scale).replace(/0+$/, '');
  return fraction ? integer + '.' + fraction : integer;
}

function hoursNumber(amount) {
  return Number(exactHoursText(amount));
}

const Hours = { parseHours, sumHours, combineHours, exactHoursText, hoursNumber };
export { Hours, parseHours, sumHours, combineHours, exactHoursText, hoursNumber };
export default Hours;
