import APSWorkbenchTransport from './shared/network/transport.js';
import ResourceTableFilterModel from './ResourceTableFilterModel.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const base = '/api/workbench/v1/calibration';
const defaults = { query: '', source: null, part_ref: null, status: 'all', deviation: 'all', page: 1, size: 20, sort: 'part_no', direction: 'asc', column_filters: {} };
const sorts = { part_no: '图号', operation_label: '工序名称', old_unit_hours: '原单件定额', suggested_unit_hours: '建议单件定额', sample_count: '可用记录数', absolute_deviation_percent: '绝对偏差', status: '状态' };
const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const count = value => Number.isInteger(value) && value >= 0;
// 定额与绝对偏差：空或有限非负数；负值是数据损坏，直接拒绝。
const nonnegative = value => value === null || typeof value === 'number' && Number.isFinite(value) && value >= 0;

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
  result.column_filters = ResourceTableFilterModel.rules(result.column_filters);
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

async function readView(value, signal) {
  const wanted = input(value);
  return _validate(await APSWorkbenchTransport.read(base, encode(wanted), { signal }), wanted);
}

async function detail(value, query, signal) {
  const wanted = input(query);
  if (!ref(value) || !wanted.snapshot_ref) throw failure('所选记录或数据版本缺失。');
  return _validate(await APSWorkbenchTransport.read(base + '/' + value, encode(wanted), { signal }), wanted, value);
}

// 建议行里被模板采用绑定的事实：采用预检与本机采用记录都按这一条规则校验，
// 校验过的行由 CalibrationAdoptionAPI.binding 直接取字段。后端每行都给全这些键（calibration/method.py build_suggestion）。
const bindingFields = ['template_operation_ref', 'template_revision', 'template_snapshot', 'part_ref', 'part_no', 'part_name', 'sequence', 'operation_label', 'source',
  'old_unit_hours', 'suggested_unit_hours', 'sample_count', 'eligible_sample_count', 'candidate_count', 'excluded_count', 'sample_refs', 'sample_revisions', 'exclusion_reasons', 'method_version'];
const filled = value => typeof value === 'string' && value.length > 0;

function validBinding(row) {
  return object(row) && bindingFields.every(key => Object.prototype.hasOwnProperty.call(row, key)) && ref(row.template_operation_ref) && ref(row.part_ref)
    && Number.isInteger(row.template_revision) && row.template_revision > 0 && filled(row.template_snapshot) && filled(row.method_version)
    && ['part_no', 'part_name', 'operation_label'].every(key => typeof row[key] === 'string') && Number.isInteger(row.sequence)
    && nonnegative(row.old_unit_hours) && nonnegative(row.suggested_unit_hours)
    && ['sample_count', 'eligible_sample_count', 'candidate_count', 'excluded_count'].every(key => count(row[key]))
    && row.sample_count <= 20 && row.sample_count <= row.eligible_sample_count && row.eligible_sample_count <= row.candidate_count
    && row.excluded_count === row.candidate_count - row.sample_count && Array.isArray(row.sample_refs) && row.sample_refs.length === row.sample_count
    && row.sample_refs.every(ref) && new Set(row.sample_refs).size === row.sample_count && Array.isArray(row.sample_revisions)
    && row.sample_revisions.length === row.sample_count && row.sample_revisions.every((revision, index) => object(revision) && revision.sample_ref === row.sample_refs[index]
      && filled(revision.sample_revision) && revision.template_revision === row.template_revision && Array.isArray(revision.report_revision_refs) && revision.report_revision_refs.every(ref))
    && Array.isArray(row.exclusion_reasons);
}

function _validate(result, wanted, detailRef) {
  // 信封已由 transport 校验；本页要按快照绑定明细和导出，所以快照必须非空。
  const data = result.data, meta = result.meta;
  if (!meta.snapshot_ref || !object(data.scope)) throw failure('校准数据不完整，未使用样例或零值替代。');
  if (wanted.snapshot_ref && wanted.snapshot_ref !== meta.snapshot_ref) throw failure(WorkbenchTerms.outcomes.stale, 'snapshot_stale');
  if (Object.keys(defaults).filter(key => !['page', 'column_filters'].includes(key)).some(key => data.scope[key] !== wanted[key])
    // 后端在没有列筛选时省略 scope.column_filters（core/models/workbench_calibration.py scope()）。
    || ResourceTableFilterModel.signature(data.scope.column_filters === undefined ? {} : data.scope.column_filters) !== ResourceTableFilterModel.signature(wanted.column_filters)) throw failure('返回筛选范围不一致，未改选其他来源。', 'snapshot_stale');
  if (detailRef) {
    if (!object(data.suggestion) || data.suggestion.template_operation_ref !== detailRef)
      throw failure('完工记录分组或来源不一致，没有当作可用记录显示。');
  } else if (!object(data.page) || data.page.number !== wanted.page || data.page.size !== wanted.size)
    throw failure('校准列表或分页数量不一致。');
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
  const file = await APSWorkbenchTransport.download(base + '/export', encode({ ...query, format }), { signal, types: [APSWorkbenchTransport.types[format]] });
  if (file.header('X-Workbench-Snapshot-Ref') !== query.snapshot_ref || file.header('X-Workbench-As-Of') !== result.meta.as_of
    || file.header('X-Workbench-Row-Count') !== String(result.data.summary.total)) throw failure('导出的数据版本或总行数不一致，文件没有保存，请刷新后重试。', 'snapshot_stale');
  if (signal.aborted) throw failure('导出已取消，文件未保存。');
  APSWorkbenchTransport.saveBlob(file.filename, file.blob);
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
  return APSWorkbenchTransport.read(base + (selection ? '/facet-selection/' : '/facets/') + column, { ...query, scope: JSON.stringify(scope) }, { signal });
}

const facets = (kind, request, signal) => facet(kind, request, signal, false);
const facetSelection = (kind, request, signal) => facet(kind, request, signal, true);

const CalibrationAPI = {
  readView, detail, download, input, initial, sorts, exportReason, failure, facetScope, bindingFields, validBinding,
  facets, facetSelection
};

export {
  CalibrationAPI, readView, detail, download, input, initial, sorts, exportReason, failure, facetScope, bindingFields, validBinding,
  facets, facetSelection
};
export default CalibrationAPI;
