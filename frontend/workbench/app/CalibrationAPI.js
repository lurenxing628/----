(function () {
  'use strict';
  const base = '/api/workbench/v1/calibration';
  const defaults = { query: '', source: null, part_ref: null, status: 'all', deviation: 'all', page: 1, size: 20, sort: 'part_no', direction: 'asc', column_filters: {} };
  const sorts = { part_no: '图号', operation_label: '工序名称', old_unit_hours: '原单件定额', suggested_unit_hours: '建议单件定额', sample_count: '可用记录数', absolute_deviation_percent: '绝对偏差', status: '状态' };
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const count = value => Number.isInteger(value) && value >= 0;
  const number = value => value === null || typeof value === 'number' && Number.isFinite(value);
  function failure(message, code = null) { const error = new Error(message); error.committed = false; error.code = code; error.fields = []; return error; }
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
    result.column_filters = window.ResourceTableFilterModel.rules(result.column_filters);
    return result;
  }
  // 页面上下文只来自本页快照和执行复盘的返回入口，都只写 scope、table、selected、sample_ref、table_widths。
  function initial(value) {
    if (!object(value) || Object.keys(value).some(key => !['scope', 'table', 'selected', 'sample_ref', 'table_widths'].includes(key))) throw failure('无法识别所选完工记录来源。');
    if (value.selected != null && !ref(value.selected) || value.sample_ref != null && !ref(value.sample_ref)) throw failure('已选记录编号无效。');
    if (value.table_widths !== undefined && (!object(value.table_widths) || Object.keys(value.table_widths).some(key => !(key in sorts)
      || !Number.isFinite(value.table_widths[key]) || value.table_widths[key] < 56 || value.table_widths[key] > 16384))) throw failure('校准表格列宽记录无效。');
    return input({ ...value.scope, ...value.table });
  }
  const read = (value, signal) => window.APSWorkbenchTransport.read(base, encode(input(value)), { signal });
  async function readView(value, signal) {
    const wanted = input(value);
    return validate(await read(wanted, signal), wanted);
  }
  function detail(value, query, signal) {
    if (!ref(value) || !query.snapshot_ref) throw failure('所选记录或数据版本缺失。');
    return window.APSWorkbenchTransport.read(base + '/' + value, encode(input(query)), { signal });
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
    if (!samples.every(sample => {
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
    })) return false;
    const selected = samples.filter(sample => sample.selected);
    return selected.length === row.sample_count && samples.filter(sample => sample.eligible).length === row.eligible_sample_count
      && selected.every(sample => row.sample_refs.includes(sample.sample_ref) && row.sample_revisions.some(revision => object(revision)
        && revision.sample_ref === sample.sample_ref && revision.sample_revision === sample.sample_revision && revision.template_revision === sample.template_revision
        && JSON.stringify(revision.report_revision_refs) === JSON.stringify(sample.report_revision_refs)));
  }
  function validate(result, query, detailRef) {
    // 信封已由 transport 校验；本页要按快照绑定明细和导出，所以快照必须非空。
    const data = result.data, meta = result.meta;
    if (!meta.snapshot_ref || !object(data.scope) || !object(data.summary) || !object(data.capabilities) || !Array.isArray(data.blocked_reasons)
      || !Array.isArray(data.source_constraints) || typeof data.lineage_available !== 'boolean' || !object(data.exports) || data.exports.url !== base + '/export'
      || data.exports.scope !== 'all_filtered_suggestions' || !Array.isArray(data.exports.formats)) throw failure('校准数据不完整，未使用样例或零值替代。');
    const wanted = input(query);
    if (wanted.snapshot_ref && wanted.snapshot_ref !== meta.snapshot_ref) throw failure(window.WorkbenchTerms.outcomes.stale, 'snapshot_stale');
    if (Object.keys(defaults).filter(key => !['page', 'column_filters'].includes(key)).some(key => data.scope[key] !== wanted[key])
      // 后端在没有列筛选时省略 scope.column_filters（core/models/workbench_calibration.py scope()）。
      || window.ResourceTableFilterModel.signature(data.scope.column_filters === undefined ? {} : data.scope.column_filters) !== window.ResourceTableFilterModel.signature(wanted.column_filters)) throw failure('返回筛选范围不一致，未改选其他来源。', 'snapshot_stale');
    if (!['total', 'suggested', 'insufficient_data', 'over_20_percent'].every(key => count(data.summary[key]))
      || data.summary.total !== data.summary.suggested + data.summary.insufficient_data) throw failure('校准汇总数量不一致。');
    if (detailRef) {
      if (!validRow(data.suggestion, meta) || data.suggestion.suggestion_ref !== detailRef || !validSamples(data)) throw failure('完工记录分组或来源不一致，没有当作可用记录显示。');
    } else if (!Array.isArray(data.items) || !data.items.every(row => validRow(row, meta)) || !data.page || !count(data.page.total)
      || data.page.number !== wanted.page || data.page.size !== wanted.size || data.page.total !== data.summary.total
      || data.page.total_pages !== Math.ceil(data.page.total / wanted.size) || data.items.length !== Math.max(0, Math.min(wanted.size, data.page.total - (wanted.page - 1) * wanted.size))) throw failure('校准列表或分页数量不一致。');
    return result;
  }
  function exportReason(data, format) {
    if (!data || !data.capabilities || data.capabilities.export !== true) return '当前来源暂不能导出。';
    if (!data.summary.total) return '当前筛选没有可导出的记录。';
    if (!data.exports.formats.includes(format)) return '当前来源不支持此导出格式。';
    return '';
  }
  async function download(result, value, format, signal) {
    const query = input(value), reason = exportReason(result.data, format);
    if (reason) throw failure(reason);
    if (!query.snapshot_ref || query.snapshot_ref !== result.meta.snapshot_ref) throw failure('导出的数据版本缺失或不一致，请刷新后重试。', 'snapshot_stale');
    const file = await window.APSWorkbenchTransport.download(base + '/export', encode({ ...query, format }), { signal, types: [window.APSWorkbenchTransport.types[format]] });
    if (file.header('X-Workbench-Snapshot-Ref') !== query.snapshot_ref || file.header('X-Workbench-As-Of') !== result.meta.as_of
      || file.header('X-Workbench-Row-Count') !== String(result.data.summary.total)) throw failure('导出的数据版本或总行数不一致，文件没有保存，请刷新后重试。', 'snapshot_stale');
    if (signal.aborted) throw failure('导出已取消，文件未保存。');
    window.APSWorkbenchTransport.saveBlob(file.filename, file.blob);
    return { rows: result.data.summary.total };
  }
  // column_filters 已由 input() 规范成对象；空对象不上送。
  function encode(value) {
    const result = { ...value };
    if (Object.keys(result.column_filters).length) result.column_filters = JSON.stringify(result.column_filters);
    else delete result.column_filters;
    return result;
  }
  function facetScope(value, column) {
    const checked = input(value), result = {};
    ['query', 'source', 'part_ref', 'status', 'deviation'].forEach(key => { result[key] = checked[key]; });
    result.column_filters = Object.fromEntries(Object.entries(checked.column_filters).filter(([key]) => key !== column));
    return result;
  }
  function facet(kind, request, signal, selection) {
    if (kind !== 'calibration' || !(request.column in sorts)) throw failure('校准列筛选项无效。');
    const { scope, column, ...query } = request;
    return window.APSWorkbenchTransport.read(base + (selection ? '/facet-selection/' : '/facets/') + column, { ...query, scope: JSON.stringify(scope) }, { signal });
  }
  window.CalibrationAPI = { read, readView, detail, download, validate, input, initial, sorts, exportReason, failure, facetScope,
    facets: (kind, request, signal) => facet(kind, request, signal, false),
    facetSelection: (kind, request, signal) => facet(kind, request, signal, true) };
})();
