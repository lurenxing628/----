import RunGenerationContract from './RunGenerationContract.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import { equal } from './shared/session/pending-store.js';

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
const token = value => typeof value === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value);
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const fields = ['batch_refs', 'start_date', 'end_date', 'ready_check', 'material_strategy', 'missing_resource_policy', 'completed_policy'];
// 不重排时段：不带这个键 = 按交付设置；null = 本次不设；{start, end} = 本次单独填的时段（精确到分）。
const HOLD_MESSAGE = '不重排时段要填完整的开始和结束时刻（精确到分），开始要早于结束，并且在排产日期范围内。';
function fail(message) { const error = new Error(message); error.committed = false; return error; }
function date(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '1900-01-01' || value >= '9999-12-31') return false;
  const [year, month, day] = value.split('-').map(Number), d = new Date(year, month - 1, day);
  return d.getFullYear() === year && d.getMonth() === month - 1 && d.getDate() === day;
}
const local = d => [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-');
const minute = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d$/.test(value) && date(value.slice(0, 10));
const span = value => object(value) && Object.keys(value).length === 2 && minute(value.start) && minute(value.end) && value.start < value.end;
function holdBounds(start, end) {
  if (!date(start) || !date(end) || start > end) return null;
  const [year, month, day] = end.split('-').map(Number);
  return { min: start + 'T00:00', max: local(new Date(year, month - 1, day + 1)) + 'T00:00' };
}
function holdWindow(value, start, end) {
  if (value === null) return null;
  const bounds = holdBounds(start, end);
  if (!span(value) || !bounds || value.start < bounds.min || value.end > bounds.max) throw fail(HOLD_MESSAGE);
  return { start: value.start, end: value.end };
}
function refs(value) { return Array.isArray(value) && value.length <= 5000 && value.every(ref) && new Set(value).size === value.length; }
function input(value) {
  if (object(value) && value.material_strategy === undefined) value = { ...value, material_strategy: 'strict' };
  if (object(value) && value.hold_window === undefined && own(value, 'hold_window')) { value = { ...value }; delete value.hold_window; }
  const optional = ['hold_window', 'time_budget_seconds'].filter(key => object(value) && own(value, key)), keys = fields.concat(optional);
  if (!object(value) || Object.keys(value).length !== keys.length || !keys.every(key => own(value, key))
      || !refs(value.batch_refs) || !date(value.start_date) || !date(value.end_date) || value.start_date > value.end_date
      || !['strict', 'stage'].includes(value.material_strategy) || value.material_strategy === 'stage' && !value.ready_check
      || typeof value.ready_check !== 'boolean' || !['auto_assign', 'exclude'].includes(value.missing_resource_policy) || value.completed_policy !== 'preserve_actuals'
      || own(value, 'time_budget_seconds') && !RunGenerationContract.budget(value.time_budget_seconds))
    throw fail('请核对已选批次、排产日期范围和本次排产规则。');
  const normalized = Object.fromEntries(fields.map(key => [key, key === 'batch_refs' ? value[key].slice().sort() : value[key]]));
  if (own(value, 'hold_window')) normalized.hold_window = holdWindow(value.hold_window, value.start_date, value.end_date);
  if (own(value, 'time_budget_seconds')) normalized.time_budget_seconds = value.time_budget_seconds;
  return normalized;
}
function defaults() {
  const today = new Date(), end = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 6);
  return { batch_refs: [], start_date: local(today), end_date: local(end), ready_check: true, material_strategy: 'strict', missing_resource_policy: 'auto_assign', completed_policy: 'preserve_actuals' };
}
function preferences(response) {
  const data = response && response.data;
  if (!object(data) || !own(data, 'input'))
    throw fail('保存的排产范围读取不完整，请刷新后重试。');
  return response;
}
function initial(context) {
  if (context === undefined) return defaults();
  if (!object(context) || Object.keys(context).some(key => !fields.concat(['hold_window', 'time_budget_seconds', 'scope', 'entity_ref', 'return_to']).includes(key)))
    throw fail('传入的排产范围无效或已过期，未自动扩大为全部批次。');
  const value = { ...defaults() };
  fields.concat(['hold_window', 'time_budget_seconds']).forEach(key => { if (own(context, key)) value[key] = context[key]; });
  if (context.scope !== undefined) {
    const scope = context.scope;
    if (!object(scope) || scope.source !== 'production' || !refs(scope.batch_refs) || Object.keys(scope).some(key => !['source', 'batch_refs'].includes(key)) || context.batch_refs !== undefined || context.entity_ref !== undefined)
      throw fail('排产范围无法确认，未切换到新数据。');
    value.batch_refs = scope.batch_refs;
  }
  if (context.entity_ref !== undefined) {
    if (!ref(context.entity_ref) || context.batch_refs !== undefined) throw fail('这个批次已失效，请点「选择批次」重新选。');
    value.batch_refs = [context.entity_ref];
  }
  // 只有值班台带 {view: 'dashboard', context} 返回入口进入本页；本页不使用它，只做形状校验。
  if (context.return_to !== undefined && !(object(context.return_to) && Object.keys(context.return_to).every(key => ['view', 'context'].includes(key))
      && context.return_to.view === 'dashboard' && object(context.return_to.context))) throw fail('返回入口无效。');
  return input(value);
}
function effectiveHold(config, normalized) {
  const value = config.hold_window;
  if (normalized.hold_window === undefined) return config.hold_window_source === 'default' && (value === null || span(value));
  const expected = normalized.hold_window;
  return config.hold_window_source === 'explicit' && (value === null ? expected === null : expected !== null && span(value) && value.start === expected.start && value.end === expected.end);
}
function result(envelope, expected) {
  const d = envelope && envelope.data, normalized = { ...expected }, actual = d && d.normalized_input;
  if (object(actual) && normalized.time_budget_seconds === undefined && actual.time_budget_seconds !== undefined) normalized.time_budget_seconds = actual.time_budget_seconds;
  if (!object(d) || !token(d.input_ref) || !object(actual)
      || !equal(actual, normalized)
      || !own(d, 'run_options') || (d.run_options !== null && actual.time_budget_seconds !== d.run_options.time_budget_seconds)
      || !object(d.scope) || d.scope.source !== 'production' || !Array.isArray(d.scope.batch_refs) || !equal(d.scope.batch_refs, normalized.batch_refs)
      || !object(d.effective_config)
      || !effectiveHold(d.effective_config, normalized)
      || d.effective_start !== normalized.start_date + 'T00:00:00') throw fail('排产检查结果与本次范围或能力不一致，不能继续。');
  return d;
}
function selection(envelope, snapshot) {
  const data = envelope && envelope.data;
  if (!object(data) || !Array.isArray(data.refs) || envelope.meta.snapshot_ref !== snapshot)
    throw fail(WorkbenchTerms.outcomes.stale);
  return data.refs;
}
const PreflightContract = { input, initial, defaults, preferences, result, selection, refs, ref, fail, holdBounds, holdWindow };
export { PreflightContract, input, initial, defaults, preferences, result, selection, refs, ref, fail, holdBounds, holdWindow };
export default PreflightContract;
