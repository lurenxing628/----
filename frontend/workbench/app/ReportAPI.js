(function () {
  'use strict';
  const topics = ['delivery', 'records', 'machines', 'people', 'quality'];
  const scopeKeys = ['source', 'plan_ref', 'plan_finish_date_from', 'plan_finish_date_to', 'batch_ref', 'resource_type', 'resource_ref', 'query', 'focus'];
  const sorts = { delivery: ['batch_label', 'planned_end', 'finish_deviation_minutes', 'effective_processing_hours'],
    records: ['event_time', 'batch_label', 'quantity_done', 'effective_processing_hours'], machines: ['resource_label', 'events', 'effective_processing_hours'],
    people: ['resource_label', 'events', 'effective_processing_hours'], quality: ['batch_label', 'event_count', 'data_quality'] };
  function scope(value = {}) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !scopeKeys.includes(key) && key !== 'kind')
      || value.kind !== undefined && value.kind !== 'execution_analysis')
      throw new Error('传入范围含本页不支持的条件，未忽略日期或对象筛选。');
    const result = { source: 'production' };
    scopeKeys.forEach(key => { if (value[key] !== undefined && value[key] !== null && value[key] !== '') result[key] = value[key]; });
    return result;
  }
  function validateLedger(data) {
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
    if (!totals(data.summary) || !data.resources || !['machines', 'people'].every(kind => Array.isArray(data.resources[kind]) && data.resources[kind].every(totals))
      || !data.rows.every(data.topic === 'records' ? record : ['machines', 'people'].includes(data.topic) ? totals : operation)
      || data.detail && (!operation(data.detail.operation) || !Array.isArray(data.detail.records) || !data.detail.records.every(record)))
      throw new Error('执行台账字段缺失或计数不一致，未把旧事件当作逐次报工，也未把未知量按零处理。');
  }
  function validate(result) {
    const data = result && result.data;
    if (!result || result.ok !== true || !result.meta || result.meta.source !== 'production' || !result.meta.snapshot_ref
      || !data || !data.plan || !data.plan.is_current_official || !data.scope || !Array.isArray(data.rows) || !data.page || !data.summary || !Array.isArray(data.data_gaps)
      || !Number.isInteger(data.page.total) || data.page.total < 0 || !Number.isInteger(data.page.number) || !Number.isInteger(data.page.pages))
      throw new Error('报表数据合同不完整，未使用样例替代。');
    if (topics.includes(data.topic) && (!['operations', 'events', 'due', 'confirmed_due', 'unreported', 'finish_sample'].every(key => Number.isInteger(data.summary[key]) && data.summary[key] >= 0)
      || !['completion_rate', 'on_time_rate', 'effective_processing_hours', 'median_finish_minutes'].every(key => data.summary[key] === null || Number.isFinite(data.summary[key]))))
      throw new Error('报表汇总字段缺失或数值无效，未按零处理。');
    if (topics.includes(data.topic)) validateLedger(data);
    return result;
  }
  function create(transport) {
    const io = transport || window.APSResourceAPI.create();
    return {
      async read(input, signal) { return validate(await io.query('analytics', input, signal)); },
      async detail(ref, input, signal) {
        if (!/^[0-9a-f]{48}$/.test(ref)) throw new Error('工序引用无效，未定位其他对象。');
        return validate(await io.query('analytics/operations/' + ref, input, signal));
      },
      async catalog(kind, input, signal) {
        if (!['overdue', 'utilization', 'downtime', 'official-review'].includes(kind)) throw new Error('报表目录不存在。');
        return validate(await io.query('reports/' + kind, input, signal));
      },
      async download(path, input, signal) {
        if (!/^\/api\/workbench\/v1\/(analytics|reports\/(overdue|utilization|downtime|official-review))\/export$/.test(path) || !input.snapshot_ref)
          throw new Error('导出地址或范围快照无效，请明确刷新。');
        const result = await io.download(path, input, signal);
        const filename = /filename\*=UTF-8''([^;]+)/i.exec(result.disposition) || /filename="?([^";]+)/i.exec(result.disposition);
        let name = 'workbench-report.' + input.format;
        if (filename) { try { name = decodeURIComponent(filename[1]); } catch (_) { throw new Error('下载文件名无效。'); } }
        const url = URL.createObjectURL(result.blob), link = document.createElement('a');
        link.href = url; link.download = name;
        try { document.body.appendChild(link); link.click(); }
        finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
        return { filename: name, bytes: result.blob.size };
      }
    };
  }
  window.ReportAPI = { create, scope, validate, topics, sorts };
})();
