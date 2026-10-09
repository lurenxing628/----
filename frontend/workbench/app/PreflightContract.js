(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const token = value => typeof value === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
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
    const keys = object(value) && own(value, 'hold_window') ? fields.concat(['hold_window']) : fields;
    if (!object(value) || Object.keys(value).length !== keys.length || !keys.every(key => own(value, key))
        || !refs(value.batch_refs) || !date(value.start_date) || !date(value.end_date) || value.start_date > value.end_date
        || !['strict', 'stage', 'split'].includes(value.material_strategy) || value.material_strategy !== 'strict' && !value.ready_check
        || typeof value.ready_check !== 'boolean' || !['auto_assign', 'exclude'].includes(value.missing_resource_policy) || value.completed_policy !== 'preserve_actuals')
      throw fail('请核对已选批次、排产日期范围和本次排产规则。');
    const normalized = Object.fromEntries(fields.map(key => [key, key === 'batch_refs' ? value[key].slice().sort() : value[key]]));
    if (keys !== fields) normalized.hold_window = holdWindow(value.hold_window, value.start_date, value.end_date);
    return normalized;
  }
  function defaults() {
    const today = new Date(), end = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 6);
    return { batch_refs: [], start_date: local(today), end_date: local(end), ready_check: true, material_strategy: 'strict', missing_resource_policy: 'auto_assign', completed_policy: 'preserve_actuals' };
  }
  function initial(context) {
    if (context === undefined) return defaults();
    if (!object(context) || Object.keys(context).some(key => !fields.concat(['hold_window', 'scope', 'entity_ref', 'return_to']).includes(key)))
      throw fail('传入的排产范围无效或已过期，未自动扩大为全部批次。');
    const value = { ...defaults() };
    fields.concat(['hold_window']).forEach(key => { if (own(context, key)) value[key] = context[key]; });
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
    // 来源入口既可以是旧的视图名字符串，也可以是值班台用的 {view, context} 信封；本页不使用它，只做形状校验。
    if (context.return_to !== undefined && !['batches', 'dashboard', 'run'].includes(object(context.return_to) ? context.return_to.view : context.return_to)) throw fail('返回入口无效。');
    const normalized = input(value);
    // 旧 split 只是拆批入口，实际放行与 strict 相同；新的可编辑规则只保留真实的两种齐套方式。
    return normalized.material_strategy === 'split' ? { ...normalized, material_strategy: 'strict' } : normalized;
  }
  const issues = rows => Array.isArray(rows) && rows.every(row => object(row) && typeof row.code === 'string' && typeof row.message === 'string');
  const nullableCount = value => value === null || count(value);
  const localTime = value => value === null || typeof value === 'string'
    && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.(?!000000$)\d{6})?(?![\s\S])/.test(value) && date(value.slice(0, 10));
  function execution(value) {
    return object(value) && ['unreported', 'started', 'partial', 'paused', 'exception', 'complete'].includes(value.execution_state)
      && [null, 'complete_reports', 'legacy_finish_event'].includes(value.completion_basis)
      && ['complete', 'incomplete', 'legacy_incomplete', 'invalid'].includes(value.data_quality)
      && ['first_actual_start', 'confirmed_finish'].every(key => localTime(value[key]))
      && ['remaining_quantity', 'known_completed_quantity', 'unknown_record_count'].every(key => nullableCount(value[key]));
  }
  // 排产会原样保留的原安排：落在不重排时段里的（含同批次一起保留的前道）。正式计划里的锁定标记已不再起作用。
  const held = value => value === null || object(value) && Object.keys(value).length === 3 && value.basis === 'hold_window'
    && value.start !== null && localTime(value.start) && value.end !== null && localTime(value.end) && value.start <= value.end;
  function effectiveHold(config, normalized) {
    const value = config.hold_window;
    if (normalized.hold_window === undefined) return config.hold_window_source === 'default' && (value === null || span(value));
    const expected = normalized.hold_window;
    return config.hold_window_source === 'explicit' && (value === null ? expected === null : expected !== null && span(value) && value.start === expected.start && value.end === expected.end);
  }
  const taskStates = ['eligible', 'auto_assign_required', 'skipped', 'blocked', 'protected'];
  const countKeys = ['ready_tasks', 'auto_assign_required', 'skipped_tasks', 'blocked_tasks', 'protected_tasks', 'eligible_tasks', 'selected_batches', 'selected_tasks', 'no_route_batches', 'unready_batches', 'missing_resource_tasks', 'actual_fact_tasks', 'held_tasks', 'hold_window_tasks'];
  function result(envelope, expected) {
    const d = envelope && envelope.data, normalized = input(expected), scope = new Set(normalized.batch_refs);
    if (!object(d) || !token(d.input_ref) || !date(String(d.input_expires_at).slice(0, 10)) || !object(d.counts) || !countKeys.every(key => count(d.counts[key]))
        || JSON.stringify(input(d.normalized_input)) !== JSON.stringify(normalized)
        || !Array.isArray(d.tasks) || !d.tasks.every(row => object(row) && ref(row.operation_ref) && scope.has(row.batch_ref)
          && typeof row.batch_id === 'string' && typeof row.label === 'string' && taskStates.includes(row.status) && typeof row.has_execution_facts === 'boolean'
          && issues(row.issues) && Array.isArray(row.predecessor_refs) && row.predecessor_refs.every(ref) && execution(row.execution) && own(row, 'held') && held(row.held))
        || new Set(d.tasks.map(row => row.operation_ref)).size !== d.tasks.length
        || !issues(d.blockers) || !issues(d.warnings) || !issues(d.run_blocked_reasons) || !d.run_blocked_reasons.length
        || d.calendar_check !== 'not_evaluated' || d.config_scope !== 'single_run' || d.run_blocked !== true
        || !object(d.write_context) || !object(d.write_context.capabilities) || d.write_context.capabilities['scheduling.run'] !== false || d.write_context.write_token !== null
        || !Array.isArray(d.no_route_batches) || !Array.isArray(d.unready_batches)
        || !Array.isArray(d.included_batches) || !Array.isArray(d.excluded_batches)
        || !object(d.scope) || d.scope.source !== 'production' || !refs(d.scope.batch_refs) || JSON.stringify(d.scope.batch_refs) !== JSON.stringify(normalized.batch_refs)
        || !object(d.effective_config) || !fields.slice(3).every(key => (key === 'material_strategy' ? d.effective_config[key] || 'strict' : d.effective_config[key]) === normalized[key])
        || !effectiveHold(d.effective_config, normalized)
        || d.effective_start !== normalized.start_date + 'T00:00:00') throw fail('排产检查结果与本次范围或能力不一致，不能继续。');
    const c = d.counts, heldRows = d.tasks.filter(row => row.held !== null);
    ['ready_tasks', 'auto_assign_required', 'skipped_tasks', 'blocked_tasks', 'protected_tasks'].forEach((key, index) => {
      if (c[key] !== d.tasks.filter(row => row.status === taskStates[index]).length) throw fail('排产检查计数不一致。');
    });
    if (c.held_tasks !== heldRows.length || c.hold_window_tasks !== heldRows.filter(row => row.held.basis === 'hold_window').length
        || d.effective_config.hold_window === null && c.held_tasks !== 0) throw fail('排产检查计数不一致。');
    const batchRows = d.included_batches.concat(d.excluded_batches);
    const taskRefs = new Set(d.tasks.map(row => row.operation_ref));
    if (c.selected_tasks !== d.tasks.length || c.selected_batches !== scope.size || c.eligible_tasks !== c.ready_tasks + c.auto_assign_required
        || d.eligible_tasks !== c.eligible_tasks || d.auto_assign_required !== c.auto_assign_required || d.skipped_tasks !== c.skipped_tasks
        || c.actual_fact_tasks !== d.tasks.filter(row => row.has_execution_facts).length
        || c.no_route_batches !== d.no_route_batches.length || c.unready_batches !== d.unready_batches.length
        || new Set(d.no_route_batches.map(row => row.batch_ref)).size !== c.no_route_batches || new Set(d.unready_batches.map(row => row.batch_ref)).size !== c.unready_batches
        || !d.tasks.every(row => row.predecessor_refs.every(ref => taskRefs.has(ref)))
        || d.tasks.some(row => ['eligible', 'auto_assign_required'].includes(row.status) && row.execution.execution_state !== 'unreported')
        || batchRows.length !== scope.size || new Set(batchRows.map(row => row.batch_ref)).size !== scope.size
        || !batchRows.concat(d.no_route_batches, d.unready_batches).every(row => object(row) && scope.has(row.batch_ref) && typeof row.batch_id === 'string'))
      throw fail('排产检查遗漏了选中批次，不能继续。');
    return d;
  }
  function selection(envelope, snapshot) {
    const data = envelope && envelope.data;
    if (!object(data) || !refs(data.refs) || data.count !== data.refs.length || envelope.meta.snapshot_ref !== snapshot)
      throw fail(window.WorkbenchTerms.outcomes.stale);
    return data.refs;
  }
  window.PreflightContract = { input, initial, defaults, result, selection, refs, ref, fail, holdBounds, holdWindow };
})();
