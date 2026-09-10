(function () {
  'use strict';
  const base = '/api/workbench/v1/calibration';
  const defaults = { query: '', source: null, part_ref: null, status: 'all', deviation: 'all', page: 1, size: 20, sort: 'part_no', direction: 'asc', column_filters: {} };
  const sorts = { part_no: '图号', operation_label: '工序名称', old_unit_hours: '原单件定额', suggested_unit_hours: '建议单件定额', sample_count: '有效样本数', absolute_deviation_percent: '绝对偏差', status: '状态' };
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const count = value => Number.isInteger(value) && value >= 0;
  const number = value => value === null || typeof value === 'number' && Number.isFinite(value);
  function failure(message, code) { const error = new Error(message); error.committed = false; error.error = { code, message, fields: [] }; return error; }
  function input(value = {}) {
    if (!object(value) || Object.keys(value).some(key => !(key in defaults) && key !== 'snapshot_ref')) throw failure('筛选条件不受支持，未切换到其他范围。');
    const result = { ...defaults, ...value };
    if (typeof result.query !== 'string' || result.query.length > 200 || result.query.includes('\0') || result.part_ref !== null && !ref(result.part_ref)
      || ![null, 'internal', 'external', 'unknown'].includes(result.source) || !['all', 'suggested', 'insufficient_data'].includes(result.status)
      || !['all', 'over_20_percent'].includes(result.deviation) || !(result.sort in sorts) || !['asc', 'desc'].includes(result.direction)
      || !Number.isInteger(result.page) || result.page < 1 || result.page > 1000000 || !Number.isInteger(result.size) || result.size < 1 || result.size > 200
      || result.snapshot_ref !== undefined && (typeof result.snapshot_ref !== 'string' || !result.snapshot_ref)) throw failure('筛选或记录编号无效，请核对后重试。');
    result.query = result.query.trim();
    if (!object(result.column_filters) || Object.keys(result.column_filters).some(key => !(key in sorts) || !object(result.column_filters[key]))) throw failure('校准列筛选不完整。');
    result.column_filters = Object.fromEntries(Object.keys(result.column_filters).sort().map(key => [key, window.ResourceTableFilterModel.rule(result.column_filters[key])]));
    if (result.page > 1 && !result.snapshot_ref) throw failure('原列表快照缺失，请明确刷新。', 'snapshot_required');
    return result;
  }
  function initial(value = {}) {
    if (!object(value) || Object.keys(value).some(key => !['scope', 'table', 'snapshot_ref', 'selected', 'sample_ref', 'table_widths'].includes(key))) throw failure('传入的样本来源无法识别，未改选其他记录。');
    if (value.selected != null && !ref(value.selected) || value.sample_ref != null && !ref(value.sample_ref)) throw failure('已选记录编号无效。');
    if (value.table_widths !== undefined && (!object(value.table_widths) || Object.keys(value.table_widths).some(key => !(key in sorts)
      || !Number.isFinite(value.table_widths[key]) || value.table_widths[key] < 56 || value.table_widths[key] > 16384))) throw failure('校准表格列宽记录无效。');
    return input({ ...value.scope, ...value.table, ...(value.snapshot_ref ? { snapshot_ref: value.snapshot_ref } : {}) });
  }
  function validRow(row, meta) {
    return object(row) && ref(row.suggestion_ref) && row.suggestion_ref === row.template_operation_ref && row.operation_ref === row.suggestion_ref
      && ref(row.part_ref) && ['part_no', 'part_name', 'operation_label', 'template_snapshot', 'method_version', 'generated_at'].every(key => typeof row[key] === 'string')
      && Number.isInteger(row.sequence) && Number.isInteger(row.template_revision) && row.template_revision > 0
      && ['old_unit_hours', 'suggested_unit_hours', 'deviation_percent', 'absolute_deviation_percent'].every(key => number(row[key]))
      && ['sample_count', 'eligible_sample_count', 'candidate_count', 'excluded_count'].every(key => count(row[key]))
      && row.sample_count <= 20 && row.sample_count <= row.eligible_sample_count && row.eligible_sample_count <= row.candidate_count
      && row.excluded_count === row.candidate_count - row.sample_count && Array.isArray(row.sample_refs) && row.sample_refs.length === row.sample_count
      && row.sample_refs.every(ref) && new Set(row.sample_refs).size === row.sample_count && Array.isArray(row.sample_revisions) && row.sample_revisions.length === row.sample_count
      && Array.isArray(row.exclusion_reasons) && Array.isArray(row.blocked_reasons) && object(row.capabilities)
      && typeof row.over_20_percent === 'boolean' && ['relative', 'old_zero', 'old_unknown', 'suggestion_unavailable', 'not_representable'].includes(row.deviation_basis)
      && ['insufficient_data', 'suggested'].includes(row.status) && (row.status === 'insufficient_data') === (row.suggested_unit_hours === null)
      && (row.sample_count >= 5 || row.suggested_unit_hours === null) && row.snapshot_ref === meta.snapshot_ref && row.as_of === meta.as_of;
  }
  function validSamples(data) {
    const row = data.suggestion, samples = data.samples;
    if (data.candidate_scope_basis !== 'template_ref_and_same_part_unbound' || !Array.isArray(samples)
      || samples.length !== row.candidate_count || new Set(samples.map(sample => sample && sample.sample_ref)).size !== samples.length) return false;
    const valid = samples.every(sample => {
      if (!object(sample) || !ref(sample.sample_ref) || sample.execution_operation_ref !== sample.sample_ref
        || typeof sample.eligible !== 'boolean' || typeof sample.selected !== 'boolean' || typeof sample.sample_revision !== 'string'
        || !['completed_quantity', 'effective_processing_hours', 'unit_hours'].every(key => number(sample[key])) || !count(sample.unknown_record_count)
        || !Array.isArray(sample.exclusion_reasons) || !Array.isArray(sample.reports) || !Array.isArray(sample.legacy_facts) || !Array.isArray(sample.data_gaps)
        || !sample.reports.every(report => object(report) && ref(report.report_ref) && ref(report.revision_ref) && Array.isArray(report.correction_history))) return false;
      if (sample.template_operation_ref === null) return sample.template_revision === null && sample.lineage_evidence_ref === null
        && !sample.eligible && !sample.selected && sample.exclusion_reasons.some(reason => reason.code === 'template_lineage_missing');
      return sample.template_operation_ref === row.template_operation_ref && Number.isInteger(sample.template_revision) && sample.template_revision > 0
        && ref(sample.lineage_evidence_ref) && (!sample.eligible || sample.template_revision === row.template_revision)
        && (!sample.selected || sample.eligible && sample.exclusion_reasons.length === 0)
        && (sample.selected || sample.exclusion_reasons.length > 0);
    });
    const selected = samples.filter(sample => sample && sample.selected);
    return valid && selected.length === row.sample_count && samples.filter(sample => sample.eligible).length === row.eligible_sample_count
      && selected.every(sample => row.sample_refs.includes(sample.sample_ref) && row.sample_revisions.some(revision => object(revision)
        && revision.sample_ref === sample.sample_ref && revision.sample_revision === sample.sample_revision && revision.template_revision === sample.template_revision
        && JSON.stringify(revision.report_revision_refs) === JSON.stringify(sample.report_revision_refs)));
  }
  function validate(result, query, detailRef) {
    const data = result && result.data, meta = result && result.meta;
    if (!result || result.ok !== true || result.schema_version !== 1 || !meta || meta.source !== 'production' || meta.time_basis !== 'factory_local'
      || typeof meta.snapshot_ref !== 'string' || !meta.snapshot_ref || typeof meta.as_of !== 'string' || !Array.isArray(result.warnings)
      || !data || !object(data.scope) || !object(data.summary) || !object(data.capabilities) || !Array.isArray(data.blocked_reasons)
      || !Array.isArray(data.source_constraints) || typeof data.lineage_available !== 'boolean' || !object(data.exports) || data.exports.url !== base + '/export'
      || data.exports.scope !== 'all_filtered_suggestions' || !Array.isArray(data.exports.formats)) throw failure('校准数据不完整，未使用样例或零值替代。');
    const wanted = input(query);
    if (wanted.snapshot_ref && wanted.snapshot_ref !== meta.snapshot_ref) throw failure('前后快照不一致，请明确刷新；已选记录保留。', 'snapshot_stale');
    if (Object.keys(defaults).filter(key => !['page', 'column_filters'].includes(key)).some(key => data.scope[key] !== wanted[key])
      || window.ResourceTableFilterModel.signature(data.scope.column_filters || {}) !== window.ResourceTableFilterModel.signature(wanted.column_filters)) throw failure('返回筛选范围不一致，未改选其他来源。', 'snapshot_stale');
    if (!['total', 'suggested', 'insufficient_data', 'over_20_percent'].every(key => count(data.summary[key]))
      || data.summary.total !== data.summary.suggested + data.summary.insufficient_data) throw failure('校准汇总数量不一致。');
    if (detailRef) {
      if (!validRow(data.suggestion, meta) || data.suggestion.suggestion_ref !== detailRef || !validSamples(data)) throw failure('样本分组或来源不一致，未当作有效样本显示。');
    } else if (!Array.isArray(data.items) || !data.items.every(row => validRow(row, meta)) || !data.page || !count(data.page.total)
      || data.page.number !== wanted.page || data.page.size !== wanted.size || data.page.total !== data.summary.total
      || data.page.total_pages !== Math.ceil(data.page.total / wanted.size) || data.items.length !== Math.max(0, Math.min(wanted.size, data.page.total - (wanted.page - 1) * wanted.size))) throw failure('校准列表或分页数量不一致。');
    return result;
  }
  function exportReason(data, format) {
    if (!data || !data.capabilities || data.capabilities.export !== true) return '导出权限尚未确认，暂不能导出。';
    if (!data.summary.total) return '当前筛选没有可导出的记录。';
    if (!data.exports.formats.includes(format)) return '当前来源不支持此导出格式。';
    return '';
  }
  async function download(result, value, format, signal) {
    const query = input(value), reason = exportReason(result.data, format);
    if (reason) throw failure(reason);
    if (!query.snapshot_ref || query.snapshot_ref !== result.meta.snapshot_ref) throw failure('导出快照缺失或不一致，请明确刷新。', 'snapshot_stale');
    const target = new URL(base + '/export', location.origin);
    Object.entries(transport({ ...query, format })).forEach(([key, item]) => { if (item !== undefined && item !== null && item !== '') target.searchParams.set(key, String(item)); });
    const controller = new AbortController(), abort = () => controller.abort();
    if (signal) { signal.addEventListener('abort', abort, { once: true }); if (signal.aborted) abort(); }
    const timer = setTimeout(abort, 20000);
    try {
      const response = await fetch(target.href, { method: 'GET', cache: 'no-store', credentials: 'same-origin', redirect: 'error', signal: controller.signal });
      const mime = response.headers.get('content-type') || '';
      if (!response.ok || mime.includes('application/json')) {
        const payload = mime.includes('application/json') ? await response.json() : null;
        throw failure(payload && payload.error && payload.error.message || '导出读取失败，请重试。', payload && payload.error && payload.error.code);
      }
      if (response.headers.get('X-Workbench-Snapshot') !== query.snapshot_ref || response.headers.get('X-Workbench-As-Of') !== result.meta.as_of
        || response.headers.get('X-Workbench-Row-Count') !== String(result.data.summary.total)) throw failure('导出快照或总行数不一致，文件未保存，请明确刷新。', 'snapshot_stale');
      const expected = format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      if (!mime.toLowerCase().startsWith(expected)) throw failure('导出文件格式不正确，文件未保存。');
      const blob = await response.blob(), bytes = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
      if (!blob.size || blob.size > 16 * 1024 * 1024 || (format === 'csv' ? bytes[0] !== 239 || bytes[1] !== 187 || bytes[2] !== 191 : bytes[0] !== 80 || bytes[1] !== 75)) throw failure('导出文件内容不完整，文件未保存。');
      const disposition = response.headers.get('content-disposition') || '';
      const match = /filename\*=UTF-8''([^;]+)/i.exec(disposition) || /filename="?([^";]+)/i.exec(disposition);
      const filename = match ? decodeURIComponent(match[1]) : '';
      if (!/^workbench-calibration-[\wT-]+\.(csv|xlsx)$/.test(filename) || !filename.endsWith('.' + format)) throw failure('导出文件名不正确，文件未保存。');
      if (controller.signal.aborted) throw failure('导出已取消，文件未保存。');
      const url = URL.createObjectURL(blob), link = document.createElement('a');
      link.href = url; link.download = filename;
      try { document.body.appendChild(link); link.click(); }
      finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
      return { filename, rows: result.data.summary.total, snapshot_ref: query.snapshot_ref, bytes: blob.size };
    } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
  }
  function transport(value) {
    const result = { ...value };
    if (result.column_filters && Object.keys(result.column_filters).length) result.column_filters = JSON.stringify(result.column_filters);
    else delete result.column_filters;
    return result;
  }
  function facetScope(value, column) {
    const checked = input(value), result = {};
    ['query', 'source', 'part_ref', 'status', 'deviation'].forEach(key => { result[key] = checked[key]; });
    result.column_filters = Object.fromEntries(Object.entries(checked.column_filters).filter(([key]) => key !== column));
    return result;
  }
  function create(supplied) {
    const io = supplied || window.APSResourceAPI.create();
    const parameters = value => transport(input(value));
    function facet(kind, request, signal, selection) {
      if (kind !== 'calibration' || !(request.column in sorts)) throw failure('校准列值对象无效。');
      const { scope, column, ...query } = request;
      return io.query('calibration/' + (selection ? 'facet-selection/' : 'facets/') + column, { ...query, scope: JSON.stringify(scope) }, signal);
    }
    return { read: (value, signal) => io.query('calibration', parameters(value), signal),
      detail: (value, query, signal) => { if (!ref(value) || !query.snapshot_ref) throw failure('所选记录或原快照缺失。'); return io.query('calibration/' + value, parameters(query), signal); }, download,
      facets: (kind, request, signal) => facet(kind, request, signal, false),
      facetSelection: (kind, request, signal) => facet(kind, request, signal, true) };
  }
  window.CalibrationAPI = { create, validate, input, initial, sorts, exportReason, failure, facetScope };
})();
