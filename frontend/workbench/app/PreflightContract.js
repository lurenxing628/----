import RunGenerationContract from './RunGenerationContract.js';
import { equal } from './shared/session/pending-store.js';
import { object, ref48, token32, isDate, moveDay, today, failure } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：排产检查结果对应本次范围与规则。
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const fields = ['batch_refs', 'start_date', 'end_date', 'ready_check', 'material_strategy', 'missing_resource_policy', 'completed_policy'];
// 不重排时段：不带这个键 = 按交付设置；null = 本次不设；{start, end} = 本次单独填的时段（精确到分）。
const HOLD_MESSAGE = '不重排时段要填完整的开始和结束时刻（精确到分），开始要早于结束，并且在排产日期范围内。';
// 排产日期是工厂日历日：判日与加减天数都走 kit 的纯日历算术，不受浏览器时区影响；日期的取值范围由后端校验。
// 时刻只认自然日加时分；落在排产日期范围里归 holdWindow()（止日次日 00:00 也在范围里）。
const minute = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d$/.test(value) && isDate(value.slice(0, 10));
const span = value => object(value) && Object.keys(value).length === 2 && minute(value.start) && minute(value.end) && value.start < value.end;
function holdBounds(start, end) {
  if (!isDate(start) || !isDate(end) || start > end) return null;
  return { min: start + 'T00:00', max: moveDay(end, 1) + 'T00:00' };
}
function holdWindow(value, start, end) {
  if (value === null) return null;
  const bounds = holdBounds(start, end);
  if (!span(value) || !bounds || value.start < bounds.min || value.end > bounds.max) throw failure(HOLD_MESSAGE);
  return { start: value.start, end: value.end };
}
function refs(value) { return Array.isArray(value) && value.every(ref48) && new Set(value).size === value.length; }
function input(value) {
  if (object(value) && value.material_strategy === undefined) value = { ...value, material_strategy: 'strict' };
  if (object(value) && value.hold_window === undefined && own(value, 'hold_window')) { value = { ...value }; delete value.hold_window; }
  const optional = ['hold_window', 'time_budget_seconds'].filter(key => object(value) && own(value, key)), keys = fields.concat(optional);
  if (!object(value) || Object.keys(value).length !== keys.length || !keys.every(key => own(value, key))
      || !refs(value.batch_refs) || !isDate(value.start_date) || !isDate(value.end_date) || value.start_date > value.end_date
      || !['strict', 'stage'].includes(value.material_strategy) || value.material_strategy === 'stage' && !value.ready_check
      || typeof value.ready_check !== 'boolean' || !['auto_assign', 'exclude'].includes(value.missing_resource_policy) || value.completed_policy !== 'preserve_actuals'
      || own(value, 'time_budget_seconds') && !RunGenerationContract.budget(value.time_budget_seconds))
    throw failure('请核对已选批次、排产日期范围和本次排产规则。');
  const normalized = Object.fromEntries(fields.map(key => [key, key === 'batch_refs' ? value[key].slice().sort() : value[key]]));
  if (own(value, 'hold_window')) normalized.hold_window = holdWindow(value.hold_window, value.start_date, value.end_date);
  if (own(value, 'time_budget_seconds')) normalized.time_budget_seconds = value.time_budget_seconds;
  return normalized;
}
function defaults() {
  // “今天”取本机日期；结束日在它上面按日历加 6 天。
  const start = today();
  return { batch_refs: [], start_date: start, end_date: moveDay(start, 6), ready_check: true, material_strategy: 'strict', missing_resource_policy: 'auto_assign', completed_policy: 'preserve_actuals' };
}
// 键集、范围与单批定位的互斥、return_to 已由 WorkbenchNavigation.admit 按受控导航声明准入；这里核对取值并规整成排产输入。
// return_to 不进排产输入，由页面原样记住。
function initial(context) {
  if (context === undefined) return defaults();
  const value = { ...defaults() };
  fields.concat(['hold_window', 'time_budget_seconds']).forEach(key => { if (own(context, key)) value[key] = context[key]; });
  if (context.scope !== undefined) {
    const scope = context.scope;
    if (!object(scope) || scope.source !== 'production' || !refs(scope.batch_refs) || Object.keys(scope).some(key => !['source', 'batch_refs'].includes(key)))
      throw failure('排产范围无法确认，未切换到新数据。');
    value.batch_refs = scope.batch_refs;
  }
  if (context.entity_ref !== undefined) {
    if (!ref48(context.entity_ref)) throw failure('这个批次已失效，请点「选择批次」重新选。');
    value.batch_refs = [context.entity_ref];
  }
  return input(value);
}
function effectiveHold(config, normalized) {
  const value = config.hold_window;
  if (normalized.hold_window === undefined) return config.hold_window_source === 'default' && (value === null || span(value));
  const expected = normalized.hold_window;
  return config.hold_window_source === 'explicit' && (value === null ? expected === null : expected !== null && span(value) && value.start === expected.start && value.end === expected.end);
}
function result(envelope, expected) {
  // 信封与检查结果的字段形状由 transport 和后端唯一生产者保证；这里只核对检查结果确实对应本次范围。
  const d = envelope.data, normalized = { ...expected }, actual = d.normalized_input;
  if (normalized.time_budget_seconds === undefined && actual.time_budget_seconds !== undefined) normalized.time_budget_seconds = actual.time_budget_seconds;
  if (!token32(d.input_ref) || !equal(actual, normalized)
      || (d.run_options !== null && actual.time_budget_seconds !== d.run_options.time_budget_seconds)
      || d.scope.source !== 'production' || !equal(d.scope.batch_refs, normalized.batch_refs)
      || !effectiveHold(d.effective_config, normalized)
      || d.effective_start !== normalized.start_date + 'T00:00:00') throw failure('排产检查结果与本次范围或能力不一致，不能继续。');
  return d;
}
const PreflightContract = { input, initial, defaults, result, refs, holdBounds, holdWindow };
export { PreflightContract, input, initial, defaults, result, refs, holdBounds, holdWindow };
export default PreflightContract;
