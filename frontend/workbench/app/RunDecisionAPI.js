import { check } from './RunCandidateAPI.js';
import G from './RunGenerationContract.js';
import T from './shared/network/transport.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import { object, ref48, localTime } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：各读取与请求范围、数据版本一致，参照安排属于所查的排产记录。
const queryKeys = ['selected_candidate_ref', 'reference_candidate_ref', 'comparison_mode', 'resource_view', 'range_start', 'range_end', 'snapshot_ref'];
function bindSnapshot(payload, query) {
  if (query.snapshot_ref) check(payload.meta.snapshot_ref === query.snapshot_ref, '比较资料已更新，请刷新后重试。');
}
// 各 *Scope 只保留填了值的筛选（空串、null、undefined 都不进 q）。
function scope(runRef, query) {
  check(ref48(runRef), '请从排产记录打开方案对比。');
  const value = { comparison_mode: 'candidates', resource_view: 'selected_batches' };
  queryKeys.forEach(key => { if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key]; });
  check(['candidates', 'admission_official'].includes(value.comparison_mode), '请选择本次排产的方案或排产时的正式计划进行比较。');
  check(['selected_batches', 'full_candidate'].includes(value.resource_view), '请选择资源统计范围。');
  check(value.comparison_mode !== 'admission_official' || value.reference_candidate_ref === undefined, '比较方式与比较基准不匹配，请从排产记录重新打开方案对比。');
  ['selected_candidate_ref', 'reference_candidate_ref'].forEach(key => check(value[key] === undefined || ref48(value[key]), '方案选择已失效，请重新选择。'));
  if (value.range_start !== undefined || value.range_end !== undefined)
    check(localTime(value.range_start) && localTime(value.range_end) && value.range_start < value.range_end, '请同时填写开始和结束时间，结束须晚于开始。');
  return value;
}
const completionFilters = ['all', 'complete', 'unfinished', 'ordinary', 'deferred', 'unknown'];
function completionScope(runRef, query) {
  const value = { ...scope(runRef, query), completion_filter: 'all', sort: 'batch_id', order: 'asc', page: 1, size: 20 };
  ['completion_filter', 'sort', 'order', 'page', 'size'].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  check(ref48(value.selected_candidate_ref), '请选择要查看批次安排的方案。');
  check(completionFilters.includes(value.completion_filter) && value.sort === 'batch_id' && ['asc', 'desc'].includes(value.order), '批次安排的筛选或排序条件无效，请重新选择。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '批次清单每页支持 20 或 50 条，请重新选择页码。');
  return value;
}
function processScope(runRef, query) {
  const value = { ...scope(runRef, query), record_kind: 'attempts', order: 'asc', page: 1, size: 20 };
  ['process_candidate_ref', 'objective', 'record_kind', 'sort', 'order', 'page', 'size'].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  if (value.process_candidate_ref === undefined && value.selected_candidate_ref) value.process_candidate_ref = value.selected_candidate_ref;
  if (value.sort === undefined) value.sort = value.record_kind === 'progress' ? 'elapsed_ms' : 'rank';
  check(value.process_candidate_ref === undefined || ref48(value.process_candidate_ref), '优化过程的方案选择已失效，请重新选择方案。');
  check(value.objective === undefined || G.objective(value.objective), '请选择有效的优化方向。');
  check(['attempts', 'progress'].includes(value.record_kind)
    && (value.record_kind === 'progress' ? ['event_index', 'elapsed_ms', 'primary_value'] : ['rank', 'elapsed_ms']).includes(value.sort)
    && ['asc', 'desc'].includes(value.order), '优化过程的筛选或排序条件无效，请重新选择。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '优化过程每页支持 20 或 50 条，请重新选择页码。');
  return value;
}
function detailScope(runRef, query, section) {
  const value = { ...scope(runRef, query), page: 1, size: 20, change_kind: 'all', sort: section === 'batches' ? 'worsened' : 'sequence', order: section === 'batches' ? 'desc' : 'asc' };
  if (section === 'batches') value.delivery_filter = 'all';
  ['page', 'size', 'change_kind', 'sort', 'order', 'batch_ref', ...(section === 'operations' ? ['resource_ref'] : ['delivery_filter', 'selected_batch_ref'])].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  check(ref48(value.selected_candidate_ref), '请选择需要查看的方案。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '明细每页支持 20 或 50 条，请重新选择页码。');
  if (value.sort === 'current_priority' && query.order === undefined) value.order = 'asc';
  ['batch_ref', 'resource_ref', 'selected_batch_ref'].forEach(key => check(value[key] === undefined || ref48(value[key]), '明细的批次或资源选择已失效，请重新选择。'));
  if (section === 'batches') check(['all', 'attention', 'overdue', 'deferred', 'unplanned', 'on_time'].includes(value.delivery_filter), '请选择需要查看的交付问题。');
  return value;
}
const preparationSorts = ['sequence', 'batch_id', 'after_setup_hours', 'after_required_hours', 'setup_delta_hours'];
const changeoverSorts = ['next_start', 'machine_label', 'next_batch_id'];
function preparationScope(runRef, query, section = 'preparation') {
  check(['preparation', 'changeovers'].includes(section), '请选择准备需求或工种切换明细。');
  const value = { ...scope(runRef, query), page: 1, size: 20, sort: section === 'preparation' ? 'sequence' : 'next_start', order: 'asc',
    ...(section === 'preparation' ? { allocation_state: 'all', work_scope: 'all' } : { event_side: 'all' }) };
  ['page', 'size', 'sort', 'order', 'machine_ref', ...(section === 'preparation' ? ['batch_ref', 'allocation_state', 'work_scope'] : ['event_side'])].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  check(ref48(value.selected_candidate_ref), '请选择需要查看的方案。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '准备与切换明细每页支持 20 或 50 条。');
  ['machine_ref', 'batch_ref'].forEach(key => check(value[key] === undefined || ref48(value[key]), '准备与切换明细的批次或设备选择已失效，请重新选择。'));
  check(['asc', 'desc'].includes(value.order) && (section === 'preparation' ? preparationSorts : changeoverSorts).includes(value.sort), '准备与切换排序无效，请重新选择。');
  check(section === 'preparation' ? ['all', 'remaining'].includes(value.work_scope) && ['all', ...Object.keys(WorkbenchTerms.preparation_allocations)].includes(value.allocation_state)
    : ['all', 'selected', 'reference'].includes(value.event_side), '准备与切换筛选无效，请重新选择。');
  return value;
}
function resourceFilters(query, section = 'resources') {
  const value = { resource_kind: 'machine', grain: 'day', pressure_threshold: 0.9, page: 1, size: 20 };
  const keys = ['resource_kind', 'resource_ref', 'grain', 'pressure_threshold', 'page', 'size'];
  if (section === 'resources') {
    Object.assign(value, { pressure_filter: 'all', sort: 'after_peak_utilization', order: 'desc', heatmap_page: 1, heatmap_size: 7 });
    keys.push('pressure_filter', 'sort', 'order', 'heatmap_page', 'heatmap_size', 'display_start', 'display_end');
  } else keys.push('bucket_start', 'bucket_end');
  keys.forEach(key => { if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key]; });
  check(['machine', 'operator'].includes(value.resource_kind), '请选择设备或人员。');
  check(value.resource_ref === undefined || ref48(value.resource_ref), '设备或人员选择已失效，请重新选择。');
  check(['hour', 'shift', 'day', 'week'].includes(value.grain) && typeof value.pressure_threshold === 'number'
    && Number.isFinite(value.pressure_threshold) && value.pressure_threshold > 0 && value.pressure_threshold <= 1,
  '请选择时间粒度与有效的高负荷关注线。');
  const rangeKeys = section === 'resources' ? ['display_start', 'display_end'] : ['bucket_start', 'bucket_end'];
  if (rangeKeys.some(key => value[key] !== undefined)) check(rangeKeys.every(key => localTime(value[key]))
    && value[rangeKeys[0]] < value[rangeKeys[1]]
    && (section !== 'resources' || value.grain === 'hour'), '时段起止要同时填写，结束时间须晚于开始时间。');
  if (section === 'resources') check(['all', 'high_pressure', 'zero_capacity', 'conflicts', 'unknown', 'demand_overload'].includes(value.pressure_filter), '请选择资源负荷筛选。');
  if (section === 'resource-days') check(ref48(value.resource_ref), '请选择要查看逐日明细的设备或人员。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '资源明细每页支持 20 或 50 条，请重新选择。');
  if (section === 'resources') check(Number.isInteger(value.heatmap_page) && value.heatmap_page > 0 && [7, 14, 31].includes(value.heatmap_size), '热力图每页支持 7、14 或 31 天，请重新选择。');
  if (query.snapshot_ref !== undefined && query.snapshot_ref !== null && query.snapshot_ref !== '') value.snapshot_ref = query.snapshot_ref;
  return value;
}
function resourceScope(runRef, query, section = 'resources') {
  const value = { ...scope(runRef, query), ...resourceFilters(query, section) };
  check(ref48(value.selected_candidate_ref), '请选择查看方案及设备或人员。');
  return value;
}
function savedResourceView(query, cohort, comparison) {
  const next = { ...query }, refs = cohort[next.resource_kind || 'machine'];
  if (next.resource_ref && !refs.includes(next.resource_ref)) { delete next.resource_ref; delete next.snapshot_ref; next.page = 1; }
  if (comparison && next.display_start && (next.display_start < comparison.range_start || next.display_end > comparison.range_end)) {
    delete next.display_start; delete next.display_end; delete next.snapshot_ref; next.heatmap_page = 1;
  }
  return next;
}
// 资源首屏的 data 在方案对比首屏之外多带 resource_result（内嵌的资源读取结果）与 resource_query（实际采用的资源筛选）。
function _validateResourceWorkspace(payload, q, filters) {
  bindSnapshot(payload, q);
  // scope.resource_refs 由后端恒定构造为 {machine, operator}（decision_source.py），信封已由传输层校验，这里直接用。
  const data = payload.data, resources = data.resource_result, cohort = data.scope.resource_refs;
  const candidate = data.candidates.find(row => row.candidate_ref === data.scope.selected_candidate_ref);
  if (!candidate) {
    check(resources === null, '当前方案没有可查看的资源结果，请刷新方案对比。'); return data;
  }
  check(object(resources) && typeof resources.ok === 'boolean', '资源读取结果未记录，请刷新方案对比。');
  // 内嵌的资源结果没有经过传输层：成功时按同一份查询信封核对；失败时原样留给资源页签，由 APSWorkbenchTransport.envelopeFailure 统一解析。
  if (resources.ok === true) {
    T.envelope(resources);
    bindSnapshot(resources, savedResourceView(filters, cohort, data.scope));
  }
  return data;
}
const BASE = '/api/workbench/v1/scheduling/runs/';
const read = (runRef, leaf, query, signal) => T.read(BASE + runRef + '/decision' + leaf, query, { signal, timeout: 60000 });
const RunDecisionAPI = {
  async decision(runRef, query, signal) { const q = scope(runRef, query), value = await read(runRef, '', q, signal); bindSnapshot(value, q); return value; },
  async decisionSummary(runRef, query, signal) { const q = scope(runRef, query), value = await read(runRef, '/summary', q, signal); bindSnapshot(value, q); return value; },
  async resourceWorkspace(runRef, query, savedQuery, signal) {
    const q = scope(runRef, query), filters = resourceFilters(savedQuery), wire = { ...filters }, resourceSnapshot = wire.snapshot_ref;
    delete wire.snapshot_ref;
    const value = await read(runRef, '/resource-workspace', { ...q, ...wire, ...(resourceSnapshot !== undefined ? { resource_snapshot_ref: resourceSnapshot } : {}) }, signal);
    _validateResourceWorkspace(value, q, filters); return value;
  },
  async decisionDetails(runRef, query, section, signal) { const q = detailScope(runRef, query, section), value = await read(runRef, '/' + section, q, signal); bindSnapshot(value, q); return value; },
  async completionBatches(runRef, query, signal) {
    const q = completionScope(runRef, query), value = await read(runRef, '/completion-batches', q, signal); bindSnapshot(value, q); return value;
  },
  async process(runRef, query, signal) { const q = processScope(runRef, query), value = await read(runRef, '/process', q, signal); bindSnapshot(value, q); return value; },
  async referenceWorkspace(runRef, query, signal) {
    const q = { ...scope(runRef, { ...query, comparison_mode: 'admission_official' }) };
    if (query.batch_ref) q.batch_ref = query.batch_ref;
    const value = await read(runRef, '/reference-workspace', q, signal); bindSnapshot(value, q);
    check(value.data.candidate.run_ref === runRef, '候选方案不属于所选排产记录。'); return value;
  },
  async resources(runRef, query, signal) {
    const q = resourceScope(runRef, query), value = await read(runRef, '/resources', q, signal);
    bindSnapshot(value, q); return value;
  },
  async resourceDays(runRef, query, signal) {
    const q = resourceScope(runRef, query, 'resource-days'), value = await read(runRef, '/resource-days', q, signal);
    bindSnapshot(value, q); return value;
  },
  async preparation(runRef, query, signal) { const q = preparationScope(runRef, query), value = await read(runRef, '/preparation', q, signal); bindSnapshot(value, q); return value; },
  async changeovers(runRef, query, signal) { const q = preparationScope(runRef, query, 'changeovers'), value = await read(runRef, '/changeovers', q, signal); bindSnapshot(value, q); return value; },
  async decisionExport(runRef, query, snapshotRef, format, signal, section) {
    check(['csv', 'xlsx'].includes(format) && typeof snapshotRef === 'string' && snapshotRef.length > 0);
    const detailSection = query.filter_section || (['batches', 'operations', 'resources', 'resource-days', 'preparation', 'changeovers', 'process'].includes(section) ? section : null);
    const q = detailSection === 'process' ? processScope(runRef, query) : ['preparation', 'changeovers'].includes(detailSection) ? preparationScope(runRef, query, detailSection)
      : ['resources', 'resource-days'].includes(detailSection) ? resourceScope(runRef, query, detailSection) : detailSection ? detailScope(runRef, query, detailSection) : scope(runRef, query);
    for (const key of ['page', 'size', 'heatmap_page', 'heatmap_size']) delete q[key];
    const file = await T.download(BASE + runRef + '/decision/export', { ...q, ...(detailSection ? { filter_section: detailSection } : {}), snapshot_ref: snapshotRef, format, section },
      { signal, timeout: 60000, types: [T.types[format]] });
    check(file.header('X-Workbench-Run-Ref') === runRef && file.header('X-Workbench-Snapshot-Ref') === snapshotRef, '比较资料已更新，请关闭导出窗口，刷新后重新导出。');
    // 传输层已校验附件、文件名与后缀、格式、魔数与非空；这里只断言本领域业务头。
    const rowCount = file.header('X-Workbench-Row-Count');
    check(rowCount !== null && /^\d+$/.test(rowCount), '导出文件没有读取到内容，请重新点击下载。');
    return { blob: file.blob, row_count: Number(rowCount), filename: file.filename };
  },
  resourceFilters, savedResourceView, scope, detailScope,
  completionScope, processScope, resourceScope, preparationScope
};
export { RunDecisionAPI, resourceFilters, savedResourceView, scope, detailScope,
  completionScope, processScope, resourceScope, preparationScope };
export default RunDecisionAPI;
