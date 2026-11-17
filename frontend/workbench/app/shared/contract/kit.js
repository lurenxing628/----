// 工作台前端唯一的契约原语：形状谓词、工厂日历日期、工厂本地时间与统一错误对象。
// 统一错误对象：{ message, code, fields, conflicts, committed, status, requestRef, requestKey, resultTarget }。
// committed 默认 false（请求没有发出或明确没有生效）；命令或回执查询之后的结果校验一律显式传 'unknown'。

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string';
const nonempty = value => typeof value === 'string' && value.length > 0;
// 后端永久编号：48 位小写十六进制。
const ref48 = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
// 后端快照、预检与写入令牌：32 位 URL 安全字符。十六进制的回执编号不用它。
const token32 = value => typeof value === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value);

// 工厂日历日只做年月日算术，不经过本机 Date，结果与浏览器时区无关。
function monthDays(year, month) {
  return [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
}
const monthKey = (year, month) => String(year).padStart(4, '0') + '-' + String(month).padStart(2, '0');
const dateKey = (year, month, day) => monthKey(year, month) + '-' + String(day).padStart(2, '0');
// 整月的起止日（含首尾）：日历导出与清除范围的默认值。
const monthRange = ({ year, month }) => ({ start_date: dateKey(year, month, 1), end_date: dateKey(year, month, monthDays(year, month)) });
function calendarDay(year, month, day) {
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= monthDays(year, month);
}
const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && calendarDay(Number(value.slice(0, 4)), Number(value.slice(5, 7)), Number(value.slice(8)));
// 按日历逐日挪动 YYYY-MM-DD；到 0001-01-01 或 9999-12-31 就停。
function moveDay(value, offset) {
  let [year, month, day] = value.split('-').map(Number);
  const direction = Math.sign(offset);
  for (let i = 0; i < Math.abs(offset); i++) {
    if (direction < 0 && year === 1 && month === 1 && day === 1) break;
    if (direction > 0 && year === 9999 && month === 12 && day === 31) break;
    day += direction;
    if (day < 1) { month--; if (month === 0) { year--; month = 12; } day = monthDays(year, month); }
    if (day > monthDays(year, month)) { day = 1; month++; if (month === 13) { year++; month = 1; } }
  }
  return dateKey(year, month, day);
}
// “今天”“本月”取本机日期，是唯一读本机时钟的日期原语。
function today() {
  const now = new Date();
  return dateKey(now.getFullYear(), now.getMonth() + 1, now.getDate());
}
function thisMonth() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

// 后端时间唯一由 isoformat() 写出：没有小数，或正好 6 位且不全为 0。只认这种规范形状，按真实日历判定。
function localTime(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?!000000$)\d{6})?(?![\s\S])/.test(value)) return false;
  const [year, month, day, hour, minute, second] = value.slice(0, 19).split(/[-T:]/).map(Number);
  return calendarDay(year, month, day) && hour < 24 && minute < 60 && second < 60;
}
// 秒级时间：信封 as_of、报工与外协登记。
const localSecond = value => localTime(value) && value.length === 19;

const failures = new WeakSet();
function failure(message, { code = null, fields = [], conflicts = [], committed = false, status = null,
  requestRef = null, requestKey = null, resultTarget = null } = {}) {
  const error = Object.assign(new Error(message), { code, fields, conflicts, committed, status, requestRef, requestKey, resultTarget });
  failures.add(error);
  return error;
}
const isFailure = error => failures.has(error);
// 领域校验函数：领域给出本领域数据不完整时的通用文案与错误选项，调用处可换成具体文案。
// 命令或回执查询之后的结果校验用 checker(文案, { committed: 'unknown' }) 单独绑定一份。
const checker = (fallback, details) => (valid, message = fallback) => { if (!valid) throw failure(message, details); };

const APSContractKit = {
  object, text, nonempty, ref48, token32,
  monthDays, monthKey, dateKey, monthRange, isDate, moveDay, today, thisMonth,
  localTime, localSecond, failure, isFailure, checker
};
export {
  object, text, nonempty, ref48, token32,
  monthDays, monthKey, dateKey, monthRange, isDate, moveDay, today, thisMonth,
  localTime, localSecond, failure, isFailure, checker, APSContractKit
};
export default APSContractKit;
