import T from './shared/network/transport.js';
import { ref48, failure } from './shared/contract/kit.js';

const ROOT = '/api/workbench/v1/';
const topics = ['delivery', 'records', 'machines', 'people', 'quality'];
const scopeKeys = ['source', 'plan_ref', 'plan_finish_date_from', 'plan_finish_date_to', 'batch_ref', 'resource_type', 'resource_ref', 'query', 'focus'];
const sorts = {
  delivery: ['batch_label', 'planned_end', 'finish_deviation_minutes', 'effective_processing_hours'],
  records: ['event_time', 'batch_label', 'completed_quantity', 'effective_processing_hours'],
  machines: ['resource_label', 'production_reports', 'effective_processing_hours'],
  people: ['resource_label', 'production_reports', 'effective_processing_hours'],
  quality: ['batch_label', 'production_report_count', 'data_quality']
};

function scope(value = {}) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !scopeKeys.includes(key) && key !== 'kind')
    || value.kind !== undefined && value.kind !== 'execution_analysis')
    throw failure('传入范围里有本页不支持的条件，没有忽略日期或批次筛选。');
  const result = { source: 'production' };
  scopeKeys.forEach(key => { if (value[key] !== undefined && value[key] !== null && value[key] !== '') result[key] = value[key]; });
  return result;
}

function table(value = {}, topic = 'delivery') {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw failure('报表查看状态无效，未改到默认页。');
  const result = {
    topic, page: value.page === undefined ? 1 : value.page, size: value.size === undefined ? 20 : value.size,
    sort: value.sort === undefined ? sorts[topic][0] : value.sort, direction: value.direction === undefined ? 'asc' : value.direction
  };
  if (value.topic !== undefined && value.topic !== topic || !Number.isSafeInteger(result.page) || result.page < 1
    || ![10, 20, 50].includes(result.size) || !sorts[topic].includes(result.sort) || !['asc', 'desc'].includes(result.direction))
    throw failure('报表专题、排序或分页无效，未改到其他查看状态。');
  return result;
}

async function readView(input, signal) {
  const result = await read(input, signal);
  if (input.snapshot_ref && result.meta.snapshot_ref !== input.snapshot_ref)
    throw failure('数据已更新，请刷新后重试。');
  if (input.plan_ref && result.data.plan.plan_ref !== input.plan_ref)
    throw failure('刷新后的计划与原查看状态不一致，没有改用其他来源。');
  return result;
}

// 信封已由 transport.js 的 envelope() 校验；报表的翻页、详情与导出都绑定快照，这里断言快照非空。
function validate(result) {
  if (!result.meta.snapshot_ref)
    throw failure('读到的报表数据不完整，请刷新重试。');
  return result;
}

async function read(input, signal) { return validate(await T.read(ROOT + 'analytics', input, { signal, timeout: 20000 })); }

async function detail(ref, input, signal) {
  if (!ref48(ref)) throw failure('工序编号无效，没有定位其他工序。');
  const result = validate(await T.read(ROOT + 'analytics/operations/' + ref, input, { signal, timeout: 20000 }));
  if (result.data.detail.operation.operation_ref !== ref
    || result.meta.snapshot_ref !== input.snapshot_ref
    || input.plan_ref && result.data.plan.plan_ref !== input.plan_ref)
    throw failure('工序详情与原工序、计划或当前数据版本不一致，没有改指其他工序。');
  return result;
}

// kind 来自报表下拉框的四个固定选项。
async function catalog(kind, input, signal) {
  return validate(await T.read(ROOT + 'reports/' + kind, input, { signal, timeout: 20000 }));
}

// 数据版本取自 validate 核过非空的读取结果；导出地址可能来自后端的 exports.url，这里核对它属于报表导出。
async function download(path, input, signal) {
  if (!/^\/api\/workbench\/v1\/(analytics|reports\/(overdue|utilization|downtime|official-review))\/export$/.test(path))
    throw failure('导出地址无效，请刷新后重试。');
  const file = await T.download(path, input, { signal, timeout: 20000, types: [T.types[input.format]] });
  T.saveBlob(file.filename, file.blob);
  return { filename: file.filename, bytes: file.blob.size };
}

const ReportAPI = { read, detail, catalog, download, scope, table, readView, validate, topics, sorts };

export { ReportAPI, read, detail, catalog, download, scope, table, readView, validate, topics, sorts };
export default ReportAPI;
