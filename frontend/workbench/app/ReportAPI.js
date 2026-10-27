(function () {
  'use strict';
  const T = window.APSWorkbenchTransport, ROOT = '/api/workbench/v1/';
  const topics = ['delivery', 'records', 'machines', 'people', 'quality'];
  const scopeKeys = ['source', 'plan_ref', 'plan_finish_date_from', 'plan_finish_date_to', 'batch_ref', 'resource_type', 'resource_ref', 'query', 'focus'];
  const sorts = { delivery: ['batch_label', 'planned_end', 'finish_deviation_minutes', 'effective_processing_hours'],
    records: ['event_time', 'batch_label', 'quantity_done', 'effective_processing_hours'], machines: ['resource_label', 'events', 'effective_processing_hours'],
    people: ['resource_label', 'events', 'effective_processing_hours'], quality: ['batch_label', 'event_count', 'data_quality'] };
  function scope(value = {}) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !scopeKeys.includes(key) && key !== 'kind')
      || value.kind !== undefined && value.kind !== 'execution_analysis')
      throw new Error('传入范围里有本页不支持的条件，没有忽略日期或批次筛选。');
    const result = { source: 'production' };
    scopeKeys.forEach(key => { if (value[key] !== undefined && value[key] !== null && value[key] !== '') result[key] = value[key]; });
    return result;
  }
  function table(value = {}, topic = 'delivery') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('报表查看状态无效，未改到默认页。');
    const result = { topic, page: value.page === undefined ? 1 : value.page, size: value.size === undefined ? 20 : value.size,
      sort: value.sort === undefined ? sorts[topic][0] : value.sort, direction: value.direction === undefined ? 'asc' : value.direction };
    if (value.topic !== undefined && value.topic !== topic || !Number.isSafeInteger(result.page) || result.page < 1
      || ![10, 20, 50].includes(result.size) || !sorts[topic].includes(result.sort) || !['asc', 'desc'].includes(result.direction))
      throw new Error('报表专题、排序或分页无效，未改到其他查看状态。');
    return result;
  }
  async function readView(input, signal) {
    if (input.snapshot_ref) return read(input, signal);
    const result = await read(input, signal);
    if (input.plan_ref && result.data.plan.plan_ref !== input.plan_ref || result.data.topic !== input.topic)
      throw new Error('刷新后的计划或专题与原查看状态不一致，没有改用其他来源。');
    if (result.data.page.number !== input.page || result.data.page.size !== input.size)
      throw new Error('翻页位置已失效，请回到第 1 页重新查询。');
    return result;
  }
  const count = value => Number.isInteger(value) && value >= 0;
  const amount = value => value === null || Number.isFinite(value);
  const hours = row => ['effective_processing_hours', 'known_effective_processing_hours'].every(key => amount(row[key])) && count(row.unknown_hour_events);
  const totals = row => ['events', 'production_reports', 'records'].every(key => count(row[key])) && row.events + row.production_reports === row.records && hours(row);
  const operation = row => ['event_count', 'production_report_count', 'record_count', 'unknown_record_count'].every(key => count(row[key]))
      && row.event_count + row.production_report_count === row.record_count && amount(row.known_completed_quantity) && amount(row.remaining_quantity) && hours(row);
  const record = row => ['legacy_event', 'production_report'].includes(row.record_kind) && typeof row.record_kind_label === 'string' && row.record_kind_label.length > 0
      && amount(row.quantity_done) && amount(row.effective_processing_hours) && ['factory_local', 'legacy_storage'].includes(row.recorded_at_time_basis)
      && (row.record_kind === 'legacy_event' ? row.legacy_evidence && typeof row.legacy_evidence === 'object' : typeof row.report_no === 'string'
        && Array.isArray(row.correction_history) && row.correction_history.length > 0 && row.correction_history.every(revision => revision.after && (revision.before === null || typeof revision.before === 'object')));
  function validateLedger(data) {
    if (!totals(data.summary) || !data.resources || !['machines', 'people'].every(kind => Array.isArray(data.resources[kind]) && data.resources[kind].every(totals))
      || !data.rows.every(data.topic === 'records' ? record : ['machines', 'people'].includes(data.topic) ? totals : operation))
      throw new Error('报工数据缺项或计数不一致，请刷新重试。');
  }
  // 信封已由 transport.js 的 envelope() 校验；报表的翻页、详情与导出都绑定快照，这里断言快照非空。
  function validate(result) {
    const data = result.data;
    if (!result.meta.snapshot_ref || !data.plan || !data.plan.is_current_official || !data.scope || !Array.isArray(data.rows) || !data.page || !data.summary || !Array.isArray(data.data_gaps)
      || !Number.isInteger(data.page.total) || data.page.total < 0 || !Number.isInteger(data.page.number) || !Number.isInteger(data.page.pages))
      throw new Error('读到的报表数据不完整，请刷新重试。');
    if (topics.includes(data.topic)) {
      if (!['operations', 'events', 'due', 'confirmed_due', 'unreported', 'finish_sample'].every(key => Number.isInteger(data.summary[key]) && data.summary[key] >= 0)
        || !['completion_rate', 'on_time_rate', 'effective_processing_hours', 'median_finish_minutes'].every(key => data.summary[key] === null || Number.isFinite(data.summary[key])))
        throw new Error('报表汇总缺列或数值无效，没有按 0 处理。');
      validateLedger(data);
    }
    return result;
  }
  function validateDetail(result) {
    const data = result.data;
    if (!result.meta.snapshot_ref || !data.plan || !data.plan.is_current_official || !data.detail || !data.detail.operation
      || !operation(data.detail.operation) || !Array.isArray(data.detail.records) || !data.detail.records.every(record))
      throw new Error('读到的工序详情不完整，请刷新重试。');
    return result;
  }
  async function read(input, signal) { return validate(await T.read(ROOT + 'analytics', input, { signal, timeout: 20000 })); }
  async function detail(ref, input, signal) {
    if (!/^[0-9a-f]{48}$/.test(ref)) throw new Error('工序编号无效，没有定位其他工序。');
    const result = validateDetail(await T.read(ROOT + 'analytics/operations/' + ref, input, { signal, timeout: 20000 }));
    if (result.data.detail.operation.operation_ref !== ref
      || result.data.detail.records.some(row => row.operation_ref !== ref) || result.meta.snapshot_ref !== input.snapshot_ref
      || input.plan_ref && result.data.plan.plan_ref !== input.plan_ref)
      throw new Error('工序详情与原工序、计划或当前数据版本不一致，没有改指其他工序。');
    return result;
  }
  async function catalog(kind, input, signal) {
    if (!['overdue', 'utilization', 'downtime', 'official-review'].includes(kind)) throw new Error('报表不存在。');
    return validate(await T.read(ROOT + 'reports/' + kind, input, { signal, timeout: 20000 }));
  }
  async function download(path, input, signal) {
    if (!/^\/api\/workbench\/v1\/(analytics|reports\/(overdue|utilization|downtime|official-review))\/export$/.test(path) || !input.snapshot_ref)
      throw new Error('导出地址或数据版本无效，请刷新后重试。');
    const file = await T.download(path, input, { signal, timeout: 20000, types: [T.types[input.format]] });
    T.saveBlob(file.filename, file.blob);
    return { filename: file.filename, bytes: file.blob.size };
  }
  window.ReportAPI = { read, detail, catalog, download, scope, table, readView, validate, validateDetail, topics, sorts };
})();
