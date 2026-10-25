(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const copy = value => JSON.parse(JSON.stringify(value));
  const states = ['all', 'queued', 'running', 'complete', 'partial', 'failed', 'interrupted', 'committed', 'success', 'unknown', 'available', 'current', 'historical', 'unavailable'];
  const queryKeys = ['timeline', 'date_from', 'date_to', 'metric_keys', 'comparison', 'reference_run_ref', 'selected_entry_ref', 'range_start', 'range_end', 'resource_window_days', 'state', 'sort', 'order', 'page', 'size', 'condition_page', 'condition_size', 'snapshot_ref'];
  // 默认指标列表直接放进每份默认查询，冻结后谁也不能原地改它；切换指标一律生成新数组。
  const defaultMetrics = Object.freeze(['overdue_count', 'total_tardiness_hours', 'makespan_hours', 'elapsed_seconds']);
  const sourceLabels = { run: '排产运行', candidate_adoption: '候选方案采用', trial_adoption: '试调方案采用', legacy_official: '旧正式计划' };
  const sourceLabel = value => sourceLabels[typeof value === 'string' ? value : value.source_kind];
  const windowMetric = definition => ['fixed_resource_window', 'fixed_changeover_window'].includes(definition.scope);
  const sameMetricDefinition = (a, b) => a.unit === b.unit && a.metric_version === b.metric_version && a.scope === b.scope;
  const entryRef = value => typeof value === 'string' && /^(?:run:[a-f0-9]{48}|adoption:[a-f0-9]{32}|legacy:[1-9][0-9]*)$/.test(value);
  const runRef = value => typeof value === 'string' && /^[a-f0-9]{48}$/.test(value);
  const timeKey = value => value.slice(0, 19) + '.' + (value.split('.')[1] || '').padEnd(6, '0');
  const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
  const text = value => typeof value === 'string', nullableText = value => value === null || text(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const numeric = value => value === null || typeof value === 'number' && Number.isFinite(value);
  const refs = value => value === null || Array.isArray(value) && value.every(text) && new Set(value).size === value.length;
  const shape = (value, fields) => object(value) && fields.every(key => own(value, key)) && Object.keys(value).every(key => fields.includes(key));
  const reason = value => value === null || shape(value, ['code', 'message']) && text(value.code) && text(value.message);
  const source = value => shape(value, ['kind', 'ref', 'path']) && text(value.kind) && nullableText(value.ref) && nullableText(value.path);
  function metric(value) {
    return shape(value, ['value', 'state', 'known_subtotal', 'known_count', 'unknown_count', 'total_count', 'scope', 'metric_version', 'reason', 'source', 'unit', 'covered_batch_refs', 'covered_operation_refs', 'covered_resource_refs', 'numerator_hours', 'denominator_hours', 'unknown_workload_count'])
      && ['value', 'known_subtotal', 'numerator_hours', 'denominator_hours'].every(key => numeric(value[key]))
      && ['known_count', 'unknown_count', 'total_count'].every(key => count(value[key])) && (value.unknown_workload_count === null || count(value.unknown_workload_count))
      && ['complete', 'partial', 'unavailable', 'not_applicable'].includes(value.state) && ['scope', 'metric_version', 'unit'].every(key => text(value[key]))
      && reason(value.reason) && source(value.source) && ['covered_batch_refs', 'covered_operation_refs', 'covered_resource_refs'].every(key => refs(value[key]));
  }
  function admission(value) {
    return shape(value, ['state', 'batch_refs', 'operation_refs', 'batch_count', 'operation_count', 'demand_hours', 'reason', 'batch_quantity'])
      && ['complete', 'partial', 'unavailable'].includes(value.state) && refs(value.batch_refs) && refs(value.operation_refs)
      && ['batch_count', 'operation_count'].every(key => value[key] === null || count(value[key])) && numeric(value.demand_hours) && reason(value.reason) && metric(value.batch_quantity);
  }
  function resourceWindow(value, policy = false) {
    if (!shape(value, ['mode', 'start', 'end', 'days', 'anchor', 'time_basis', 'boundary'].concat(policy ? [] : ['state', 'reason', 'cohort']))) return false;
    const H = window.RunHistoryAPI;
    return ['absolute', 'fixed_days'].includes(value.mode) && [value.start, value.end].every(v => v === null || H.time(v))
      && (value.start === null || value.end === null || timeKey(value.start) < timeKey(value.end)) && (value.days === null || count(value.days))
      && ['source_start', 'common_absolute_window'].includes(value.anchor) && value.time_basis === 'factory_local' && value.boundary === 'half_open'
      && (policy || ['available', 'partial', 'unavailable'].includes(value.state) && reason(value.reason)
        && shape(value.cohort, ['machine_refs', 'operator_refs']) && refs(value.cohort.machine_refs) && refs(value.cohort.operator_refs));
  }
  function entry(value, metricKeys) {
    check(shape(value, ['entry_ref', 'timeline', 'source_kind', 'label', 'occurred_at', 'time_basis', 'state', 'identity', 'times', 'baseline', 'source', 'scope', 'reading_context', 'metrics', 'navigation', 'issues'])
      && entryRef(value.entry_ref) && ['run', 'official'].includes(value.timeline) && ['run', 'candidate_adoption', 'trial_adoption', 'legacy_official'].includes(value.source_kind)
      && ['label', 'state'].every(key => text(value[key])) && (value.occurred_at === null || window.RunHistoryAPI.time(value.occurred_at)) && nullableText(value.time_basis));
    check(shape(value.identity, ['run_ref', 'candidate_ref', 'scenario_ref', 'draft_ref', 'plan_ref', 'plan_version', 'history_id', 'receipt_ref', 'request_key'])
      && ['run_ref', 'candidate_ref', 'scenario_ref', 'draft_ref', 'plan_ref'].every(key => value.identity[key] === null || runRef(value.identity[key]))
      && ['plan_version', 'history_id'].every(key => value.identity[key] === null || count(value.identity[key])) && nullableText(value.identity.receipt_ref) && nullableText(value.identity.request_key));
    check(value.source_kind === 'run' ? value.timeline === 'run' && value.entry_ref === 'run:' + value.identity.run_ref
      : value.timeline === 'official' && (value.source_kind === 'legacy_official' ? value.entry_ref === 'legacy:' + value.identity.history_id : value.entry_ref === 'adoption:' + value.identity.receipt_ref));
    check(shape(value.times, ['accepted_at', 'started_at', 'finished_at', 'adopted_at', 'committed_at_utc', 'schedule_time']) && Object.values(value.times).every(nullableText)
      && shape(value.baseline, ['plan_ref', 'version']) && (value.baseline.plan_ref === null || runRef(value.baseline.plan_ref)) && (value.baseline.version === null || count(value.baseline.version))
      && shape(value.source, ['kind', 'ref', 'state', 'reason']) && text(value.source.kind) && ['available', 'partial', 'unavailable'].includes(value.source.state) && nullableText(value.source.ref) && reason(value.source.reason));
    check(admission(value.scope) && shape(value.reading_context, ['resource_window', 'metric_basis']) && resourceWindow(value.reading_context.resource_window) && text(value.reading_context.metric_basis));
    check(object(value.metrics) && metricKeys.every(key => own(value.metrics, key)) && Object.values(value.metrics).every(metric));
    check(Array.isArray(value.navigation) && value.navigation.every(target => shape(target, ['label', 'view', 'context', 'enabled', 'reason']) && text(target.label)
      && ['analysis', 'gantt', 'run', 'trial'].includes(target.view) && object(target.context) && typeof target.enabled === 'boolean' && nullableText(target.reason))
      && Array.isArray(value.issues) && value.issues.every(v => v !== null && reason(v)));
    return value;
  }
  function page(value, q, prefix = '') {
    return shape(value, ['number', 'size', 'total', 'has_more']) && count(value.number) && value.number >= 1 && count(value.size) && count(value.total) && typeof value.has_more === 'boolean'
      && (!q || value.number === q[prefix + 'page'] && value.size === q[prefix + 'size']) && value.has_more === (value.number * value.size < value.total);
  }
  const conditionStates = ['equal', 'different', 'unknown'];
  const conditionSummary = value => shape(value, conditionStates) && conditionStates.every(key => count(value[key]));
  const savedValue = value => shape(value, ['present', 'state', 'value', 'source', 'reason']) && typeof value.present === 'boolean' && ['known', 'unknown'].includes(value.state) && source(value.source) && reason(value.reason);
  const conditionRow = value => shape(value, ['category', 'entity', 'field', 'state', 'before', 'after']) && text(value.category) && text(value.field)
    && shape(value.entity, ['key', 'label']) && text(value.entity.key) && text(value.entity.label) && conditionStates.includes(value.state) && savedValue(value.before) && savedValue(value.after);
  function conditionGroup(value, q) {
    return shape(value, ['state', 'summary', 'categories', 'rows', 'page']) && conditionStates.includes(value.state) && conditionSummary(value.summary)
      && Array.isArray(value.categories) && value.categories.every(row => shape(row, ['key', 'label', 'state', 'summary']) && text(row.key) && text(row.label) && conditionStates.includes(row.state) && conditionSummary(row.summary))
      && Array.isArray(value.rows) && value.rows.every(conditionRow) && page(value.page, q, 'condition_')
      && value.rows.length === Math.min(value.page.size, Math.max(0, value.page.total - (value.page.number - 1) * value.page.size));
  }
  function comparison(value, q) {
    check(shape(value, ['mode', 'conditions', 'configurations', 'objective', 'metric_deltas', 'conclusion']) && value.mode === q.comparison
      && conditionGroup(value.conditions, q) && conditionGroup(value.configurations) && (value.objective === null || conditionRow(value.objective)));
    check(object(value.metric_deltas) && Object.values(value.metric_deltas).every(delta => shape(delta, ['value', 'state', 'direction', 'reference_value', 'selected_value', 'reason'])
      && ['value', 'reference_value', 'selected_value'].every(key => numeric(delta[key])) && ['comparable', 'different_conditions', 'different_objective', 'different_coverage', 'different_version', 'unavailable'].includes(delta.state)
      && ['better', 'worse', 'equal', 'neutral'].includes(delta.direction) && reason(delta.reason)));
    const conclusion = value.conclusion;
    check(shape(conclusion, ['state', 'message', 'reason', 'improved_metric_keys', 'worsened_metric_keys']) && ['observed', 'comparable', 'improved', 'worse', 'equal', 'different_conditions', 'different_objective', 'unavailable'].includes(conclusion.state)
      && text(conclusion.message) && reason(conclusion.reason) && [conclusion.improved_metric_keys, conclusion.worsened_metric_keys].every(keys => Array.isArray(keys) && keys.every(text)));
  }
  function scope(value = {}) {
    check(object(value) && Object.keys(value).every(key => queryKeys.includes(key)), '历史筛选含不支持的项，请重新选择。');
    const q = { timeline: 'run', date_from: null, date_to: null, metric_keys: defaultMetrics, comparison: 'observed', reference_run_ref: null, selected_entry_ref: null,
      range_start: null, range_end: null, resource_window_days: 7, state: 'all', sort: 'occurred_at', order: 'desc', page: 1, size: 20, condition_page: 1, condition_size: 20, snapshot_ref: null, ...value };
    q.metric_keys = typeof q.metric_keys === 'string' ? q.metric_keys.split(',') : q.metric_keys;
    check(['run', 'official'].includes(q.timeline) && ['observed', 'same_conditions'].includes(q.comparison) && states.includes(q.state) && q.sort === 'occurred_at' && ['asc', 'desc'].includes(q.order), '请选择有效的时间线、阅读方式、状态和排序。');
    check(Array.isArray(q.metric_keys) && q.metric_keys.length >= 1 && q.metric_keys.length <= 100 && q.metric_keys.every(key => typeof key === 'string' && /^[a-z][a-z0-9_]{0,79}$/.test(key)) && new Set(q.metric_keys).size === q.metric_keys.length, '请选择有效的历史指标。');
    check(['page', 'condition_page'].every(key => Number.isSafeInteger(q[key]) && q[key] >= 1 && q[key] <= 1000000)
      && ['size', 'condition_size'].every(key => [20, 50].includes(q[key])) && Number.isSafeInteger(q.resource_window_days) && q.resource_window_days >= 1 && q.resource_window_days <= 366, '历史页码、每页数量或资源窗口天数无效。');
    check(q.reference_run_ref === null || runRef(q.reference_run_ref), '请选择有效的基准运行。');
    check(q.selected_entry_ref === null || entryRef(q.selected_entry_ref), '请选择有效的历史条目。');
    check(q.snapshot_ref === null || typeof q.snapshot_ref === 'string' && q.snapshot_ref.length > 0 && q.snapshot_ref.length <= 512, '历史快照无效，请刷新历史。');
    const H = window.RunHistoryAPI;
    check(q.date_from === null && q.date_to === null || H.date(q.date_from) && H.date(q.date_to) && q.date_from <= q.date_to, '时间线日期须成对填写，开始日期须早于或等于结束日期。');
    check(q.range_start === null && q.range_end === null || H.time(q.range_start) && H.time(q.range_end) && timeKey(q.range_start) < timeKey(q.range_end), '资源共同窗口须成对填写，结束须晚于开始。');
    return q;
  }
  function check(value, message = '历史资料读取不完整，请刷新后重试。') {
    if (!value) throw Object.assign(new Error(message), { code: 'invalid_response' });
  }
  function returnState(origin = {}) {
    check(object(origin), '历史返回位置无效，请重新打开排产记录。');
    const value = origin.return_decision_history_context || origin.return_decision_context && origin.return_decision_context.return_decision_history_context
      || origin.source === 'run_history' && origin.history_topic === 'decision_history' && origin.decision_history_context;
    if (!value) return null;
    check(object(value) && object(value.query), '历史返回条件无效，请重新打开排产记录。');
    return copy(value);
  }
  function historyContext(origin = {}) {
    const value = returnState(origin);
    return { source: 'run_history', ...(origin.history_query ? { history_query: copy(origin.history_query) } : {}),
      ...(value ? { history_topic: 'decision_history', decision_history_context: value } : {}) };
  }
  function context(value = {}) {
    check(object(value) && Object.keys(value).every(key => ['query', 'selected_entry_ref', 'reference_entry_ref', 'metric_key', 'detail_queries'].includes(key)), '历史页面的返回条件无效，请从排产记录重新打开。');
    const query = scope(value.query), selected = value.selected_entry_ref === undefined ? query.selected_entry_ref : value.selected_entry_ref;
    const reference = value.reference_entry_ref === undefined ? query.reference_run_ref && 'run:' + query.reference_run_ref : value.reference_entry_ref;
    check(selected === null || entryRef(selected), '选中历史条目的编号无效。');
    check(reference === null || typeof reference === 'string' && /^run:[a-f0-9]{48}$/.test(reference), '历史对照的基准运行无效。');
    check(selected === query.selected_entry_ref && reference === (query.reference_run_ref && 'run:' + query.reference_run_ref), '历史选择与查询条件不一致，请重新打开历史。');
    const metric = value.metric_key || query.metric_keys[0]; check(query.metric_keys.includes(metric), '趋势指标不在当前指标列表中。');
    check(value.detail_queries === undefined || object(value.detail_queries), '条件明细的返回位置无效。');
    return { query, selected_entry_ref: selected, reference_entry_ref: reference, metric_key: metric, detail_queries: value.detail_queries === undefined ? {} : copy(value.detail_queries) };
  }
  function serialized(query) {
    return new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => [key, key === 'metric_keys' ? value.join(',') : value])));
  }
  function history(payload, query = {}) {
    const q = scope(query);
    check(shape(payload, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && payload.ok === true && payload.schema_version === 1
      && object(payload.meta) && text(payload.meta.request_ref) && payload.meta.source === 'production' && payload.meta.time_basis === 'factory_local'
      && text(payload.meta.snapshot_ref) && payload.meta.snapshot_ref.length > 0 && window.RunHistoryAPI.time(payload.meta.as_of)
      && Array.isArray(payload.warnings) && payload.warnings.every(value => value !== null && reason(value)));
    if (q.snapshot_ref && payload.meta.snapshot_ref !== q.snapshot_ref) throw Object.assign(new Error('历史资料已更新，请刷新当前条件后继续查看。'), { code: 'snapshot_stale' });
    const d = payload.data;
    const filterKeys = queryKeys.filter(key => key !== 'snapshot_ref');
    check(shape(d, ['history_version', 'filters', 'entries', 'page', 'totals', 'metric_definitions', 'selection', 'comparison', 'trend', 'resource_window']) && d.history_version === 'decision-history-v1'
      && shape(d.filters, filterKeys) && page(d.page, q)
      && shape(d.totals, ['run', 'official', 'filtered']) && Object.values(d.totals).every(count) && d.totals.filtered === d.page.total);
    for (const key of filterKeys) {
      const left = d.filters[key], right = q[key];
      check(['range_start', 'range_end'].includes(key) && left !== null && right !== null ? window.RunHistoryAPI.time(left) && timeKey(left) === timeKey(right) : JSON.stringify(left) === JSON.stringify(right), '历史返回的筛选条件已变化，请重新查询。');
    }
    check(Array.isArray(d.metric_definitions) && d.metric_definitions.every(definition => shape(definition, ['key', 'label', 'group', 'unit', 'precision', 'improvement', 'scope', 'source', 'common', 'metric_version'])
      && ['key', 'label', 'group', 'unit', 'scope', 'source', 'metric_version'].every(key => text(definition[key])) && count(definition.precision) && definition.precision <= 20
      && ['lower', 'higher', 'neutral'].includes(definition.improvement) && typeof definition.common === 'boolean'));
    const metricKeys = new Set(d.metric_definitions.map(value => value.key));
    check(metricKeys.size === d.metric_definitions.length && q.metric_keys.every(key => metricKeys.has(key)));
    check(Array.isArray(d.entries) && d.entries.length === Math.min(q.size, Math.max(0, d.page.total - (q.page - 1) * q.size)) && new Set(d.entries.map(value => value.entry_ref)).size === d.entries.length);
    d.entries.forEach(value => { entry(value, q.metric_keys); check(value.timeline === q.timeline); });
    check(shape(d.selection, ['entry', 'reference']));
    if (d.selection.entry !== null) { entry(d.selection.entry, q.metric_keys); check(q.selected_entry_ref !== null && d.selection.entry.entry_ref === q.selected_entry_ref, '历史选中条目已变化，请重新选择。'); }
    else check(q.selected_entry_ref === null, '选中的历史条目未返回，请刷新当前条件。');
    if (d.selection.reference !== null) { entry(d.selection.reference, q.metric_keys); check(q.reference_run_ref !== null && d.selection.reference.entry_ref === 'run:' + q.reference_run_ref, '历史基准运行已变化，请重新选择。'); }
    else check(q.reference_run_ref === null, '基准运行未返回，请重新选择。');
    comparison(d.comparison, q); check(resourceWindow(d.resource_window, true));
    check(d.resource_window.mode === (q.range_start ? 'absolute' : 'fixed_days') && d.resource_window.anchor === (q.range_start ? 'common_absolute_window' : 'source_start')
      && (q.range_start ? d.resource_window.start !== null && d.resource_window.end !== null && timeKey(d.resource_window.start) === timeKey(q.range_start) && timeKey(d.resource_window.end) === timeKey(q.range_end) : d.resource_window.days === q.resource_window_days), '历史资源窗口与查询条件不一致，请重新查询。');
    for (const row of [...d.entries, d.selection.entry, d.selection.reference].filter(Boolean)) {
      const value = row.reading_context.resource_window;
      check(value.mode === d.resource_window.mode && value.anchor === d.resource_window.anchor && (q.range_start ? value.start !== null && value.end !== null && timeKey(value.start) === timeKey(q.range_start) && timeKey(value.end) === timeKey(q.range_end) : value.days === q.resource_window_days), '历史条目的资源窗口与当前选择不一致，请刷新。');
    }
    check(shape(d.trend, ['point_scope', 'order', 'points']) && d.trend.point_scope === 'current_page' && d.trend.order === 'asc' && Array.isArray(d.trend.points)
      && d.trend.points.length === d.entries.length && new Set(d.trend.points.map(value => value.entry_ref)).size === d.trend.points.length);
    const entries = new Map(d.entries.map(value => [value.entry_ref, value]));
    d.trend.points.forEach((point, index) => {
      const row = entries.get(point.entry_ref);
      check(shape(point, ['entry_ref', 'occurred_at', 'time_basis', 'label', 'state', 'metrics', 'scope', 'resource_window', 'range_changed', 'condition_state', 'connections']) && row
        && point.occurred_at === row.occurred_at && point.time_basis === row.time_basis && point.label === row.label && point.state === row.state
        && JSON.stringify(point.metrics) === JSON.stringify(row.metrics) && JSON.stringify(point.scope) === JSON.stringify(row.scope) && JSON.stringify(point.resource_window) === JSON.stringify(row.reading_context.resource_window)
        && typeof point.range_changed === 'boolean' && ['equal', 'different', 'unknown', 'not_compared'].includes(point.condition_state) && object(point.connections)
        && q.metric_keys.every(key => typeof point.connections[key] === 'boolean'));
      const previous = d.trend.points[index - 1];
      if (previous) check(previous.occurred_at !== null || point.occurred_at === null);
      if (previous && previous.occurred_at !== null && point.occurred_at !== null) check(timeKey(previous.occurred_at) < timeKey(point.occurred_at)
        || timeKey(previous.occurred_at) === timeKey(point.occurred_at) && previous.entry_ref < point.entry_ref);
      for (const key of q.metric_keys) if (point.connections[key]) {
        const a = previous && previous.metrics[key], b = point.metrics[key];
        check(previous && previous.occurred_at !== null && point.occurred_at !== null && a.value !== null && b.value !== null
          && a.state !== 'unavailable' && b.state !== 'unavailable'
          && sameMetricDefinition(a, b), '历史连线的指标单位、版本或范围不一致，请刷新资料。');
      }
    });
    return d;
  }
  function numberText(value, unit, precision = 3) {
    if (value === null) return '未知';
    return unit === '%' ? window.WorkbenchFormat.percent(value, { digits: precision, trim: true }) : window.WorkbenchFormat.number(value, { digits: precision, trim: true }) + (unit ? ' ' + unit : '');
  }
  function metricText(value, definition) {
    return value.value === null ? value.state === 'not_applicable' ? '不适用' : '未知' : numberText(value.value, value.unit, definition.precision);
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(query, signal, format, section) {
      const controller = new AbortController(), abort = () => controller.abort();
      if (signal) { if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true }); }
      const timer = setTimeout(abort, 60000);
      try {
        const q = { ...query };
        if (format) { ['page', 'size', 'condition_page', 'condition_size'].forEach(key => delete q[key]); q.format = format; q.section = section; }
        const response = await fetcher('/api/workbench/v1/scheduling/decision-history' + (format ? '/export' : '') + '?' + serialized(q),
          { method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal });
        const mime = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
        if (!response.ok) {
          const value = mime === 'application/json' ? await response.json() : null, detail = value && value.error;
          throw Object.assign(new Error(detail && typeof detail.message === 'string' ? detail.message : '历史资料读取失败，请重新查询。'), { code: detail && detail.code || 'invalid_response', status: response.status });
        }
        check(response.status === 200, '历史接口的响应状态无效，请重新查询。');
        if (!format) { check(mime === 'application/json', '历史接口返回的文件类型无效。'); return await response.json(); }
        check(mime === (format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
          && /^attachment;/i.test(response.headers.get('Content-Disposition') || ''), '历史导出文件格式无效，请重新下载。');
        check(response.headers.get('X-Workbench-Snapshot-Ref') === q.snapshot_ref, '历史快照已变化，请刷新后重新导出。');
        const count = response.headers.get('X-Workbench-Row-Count'), blob = await response.blob();
        check(count !== null && /^[0-9]+$/.test(count) && Number.isSafeInteger(Number(count)) && blob.size > 0, '历史导出文件内容不完整，请重新下载。');
        return { filename: '排产历史趋势.' + format, blob, row_count: Number(count) };
      } catch (error) {
        if (controller.signal.aborted && !(signal && signal.aborted)) throw Object.assign(new Error('历史资料读取超时，请刷新重试。'), { code: 'timeout' });
        throw error;
      } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
    }
    return window.APSReadBoundary.verified({ async history(query = {}, signal) {
      const q = scope(query), result = await request(q, signal); history(result, q); return result;
    }, async historyExport(query, snapshotRef, format, signal, section = 'entries') {
      check(['csv', 'xlsx'].includes(format) && ['entries', 'conditions', 'configurations', 'all'].includes(section) && (section !== 'all' || format === 'xlsx'), '请选择有效的历史导出格式和内容。');
      const q = scope({ ...query, snapshot_ref: snapshotRef }); check(typeof q.snapshot_ref === 'string', '请读取历史资料后再导出。');
      return request(q, signal, format, section);
    } }, ['history']);
  }
  function adapter(value) { return window.APSReadBoundary.checked(value, { history }); }
  window.DecisionHistoryAPI = { check, returnState, historyContext, scope, context, serialized, states, sourceLabel, windowMetric, sameMetricDefinition, create, adapter, history, entry, numberText, metricText };
})();
