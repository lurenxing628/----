import T from './shared/network/transport.js';
import { pendingStore } from './shared/session/pending-store.js';
import { useQuery } from './shared/session/query.js';
import APSResourceContract, { createIntent } from './resource-contract.js';
import { object, ref48, token32, failure } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证（基础资料族）：列表页落在有效页码上（越过末页时收缩重读，与第一读同一数据版本），详情属于所选记录，
// 关联列表属于所查工种与类别，设备关联预检属于这个人员且带确认许可，命令结果已到终态。
const prefix = '/api/workbench/v1/';
const kinds = new Set(['material', 'op_type', 'machine', 'operator', 'supplier', 'machine_group', 'shift_profile']);
const fileKinds = new Set(['material', 'op_type', 'machine', 'operator', 'supplier']);
// 只有增量导入和导出、没有批量删除的文件家族：关联资料与日历，各自的确认路径挂在哪个文件入口下。
const importOnlyBase = { operator_machine: 'relation-files', work_calendar: 'calendar-files', operator_calendar: 'calendar-files' };
const importOnlyKinds = new Set(Object.keys(importOnlyBase));
// 个人日历的三个写入动作；意图里保持 kind=operator，保存后的刷新逻辑才认得出该读哪一页。
const calendarActions = new Map([['calendar_upsert', 'upsert'], ['calendar_delete', 'delete'],
  ['calendar_range_clear', 'range-clear']]);
// 资源家族的文件只有 CSV 与 XLSX 两种。
const fileTypes = [T.types.csv, T.types.xlsx];
// 本地查不到确定结果：保持“结果未知”，由用户点「查询结果」。
const UNKNOWN = { committed: 'unknown' };
// 资源家族沿用相对路径；拼成工作台绝对路径后再交给 transport。
const absolute = path => path.startsWith('/') ? path : prefix + path;
function resource(kind, ref) {
  if (!kinds.has(kind)) throw failure('不支持这类基础资料。');
  if (ref != null && !ref48(ref)) throw failure('这条记录已失效，请重新选择。');
  return 'entities/' + kind + (ref == null ? '' : '/' + ref);
}
function tableScope(scope = {}) {
  if (!object(scope)) throw failure('列表范围不完整，请刷新后重试。');
  const result = { ...scope };
  ['status', 'category', 'snapshot_ref'].forEach(key => { if (result[key] === '' || result[key] === null || result[key] === undefined) delete result[key]; });
  if (Object.prototype.hasOwnProperty.call(result, 'column_filters')) {
    if (!object(result.column_filters)) throw failure('列筛选范围不完整，请刷新列表后重新筛选。');
    if (!Object.keys(result.column_filters).length) delete result.column_filters;
  }
  return result;
}
function terminal(payload) {
  return payload.ok === true && ['committed', 'unchanged', 'partial'].includes(payload.result)
    && typeof payload.receipt_ref === 'string' && !!payload.receipt_ref
    && object(payload.data);
}
// 本机记录的唯一校验点（只在读取磁盘时调用）。预检编号同时是确认凭据，pendingRecord 不把它写进磁盘，所以这类记录允许不带 ref。
function validIntent(value) {
  if (!object(value) || typeof value.request_key !== 'string' || !/^resource-[0-9a-f]{48}$/.test(value.request_key)) return false;
  const previewToken = value.ref === undefined || token32(value.ref);
  if (value.kind === 'operator' && (value.action === 'machine_permissions' || calendarActions.has(value.action)))
    return value.category === undefined && ref48(value.ref);
  if (value.kind === 'machine' && ['downtime_create', 'downtime_update', 'downtime_cancel'].includes(value.action))
    return value.category === undefined && ref48(value.ref);
  if (value.kind === 'calendar') return (
    ['upsert', 'delete'].includes(value.action) && typeof value.ref === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value.ref)
    || value.action === 'confirm' && (value.ref === undefined || typeof value.ref === 'string' && /^[0-9a-f]{32}$/.test(value.ref))
    || value.action === 'defaults' && value.ref === 'calendar-defaults');
  if (value.kind === 'process') return value.category === undefined && (value.action === 'create' && value.ref === null
    || ['route_confirm', 'source_confirm', 'hours_confirm', 'groups_confirm'].includes(value.action) && ref48(value.ref));
  if (['process_bulk', 'process_route_import', 'process_hours_import'].includes(value.kind)) return value.action === 'confirm'
    && previewToken && value.category === undefined;
  if (value.kind === 'batch') {
    return value.category === undefined && (value.action === 'create' && value.ref === null
      || ['update', 'delete', 'materials_update', 'split_confirm', 'sync_confirm'].includes(value.action) && ref48(value.ref)
      || value.action === 'operation_update' && ref48(value.ref) && ref48(value.operation_ref)
      || ['bulk_confirm', 'import_confirm'].includes(value.action) && previewToken);
  }
  if (value.kind === 'execution') return value.category === undefined
    && (['create', 'supplement', 'correct', 'report_void'].includes(value.action) && ref48(value.ref)
      || value.action === 'import_confirm' && previewToken);
  const importOnly = typeof value.kind === 'string' && /^(.+)_import$/.exec(value.kind);
  if (importOnly && importOnlyKinds.has(importOnly[1])) return value.action === 'confirm' && value.category === undefined
    && previewToken;
  const file = typeof value.kind === 'string' && /^(material|op_type|machine|operator|supplier)_(import|bulk)$/.exec(value.kind);
  if (file) return value.action === 'confirm' && previewToken
    && (file[1] === 'op_type' ? ['internal', 'external'].includes(value.category) : value.category === undefined);
  return kinds.has(value.kind) && ['create', 'update', 'delete'].includes(value.action)
    && (value.action === 'create' ? value.ref === null : ref48(value.ref))
    && (value.category === undefined || ['internal', 'external', 'both'].includes(value.category));
}
function pendingRecord(intent) {
  const stored = { kind: intent.kind, action: intent.action, request_key: intent.request_key };
  // A retained preview ref is also its confirmation credential; recovery only looks up the request key.
  if (intent.ref !== undefined && !token32(intent.ref)) stored.ref = intent.ref;
  if (intent.category !== undefined) stored.category = intent.category;
  if (intent.kind === 'batch' && intent.action === 'operation_update') stored.operation_ref = intent.operation_ref;
  return stored;
}
function matchesNamespace(namespace, intent) {
  if (namespace === 'resources') return kinds.has(intent.kind);
  if (namespace === 'calendar') return intent.kind === 'calendar';
  if (namespace === 'process') return ['process', 'process_bulk', 'process_route_import', 'process_hours_import'].includes(intent.kind);
  if (namespace === 'batches') return intent.kind === 'batch';
  if (namespace === 'execution') return intent.kind === 'execution';
  if (namespace === 'catalog') return ['machine_group', 'shift_profile'].includes(intent.kind);
  const kind = namespace.slice(0, -6);
  if (importOnlyKinds.has(kind)) return intent.kind === kind + '_import';
  return fileKinds.has(kind) && [kind + '_import', kind + '_bulk'].includes(intent.kind);
}
// 各命名空间的写入路径：日历只有日历动作；文件入口只确认本次预检；其余是基础资料的增改删与人员、设备的附属动作。
// 工艺、批次、现场的写入路径由各自的领域 API 拼，不走这里。
function commandPath(namespace, kind, action, ref, body) {
  if (namespace === 'calendar') {
    if (kind !== 'calendar' || !['upsert', 'delete', 'confirm', 'defaults'].includes(action)) throw failure('工作日历操作不正确。');
    return 'calendar/' + (action === 'confirm' ? 'range/confirm' : action);
  }
  const files = /^(.+)_files$/.exec(namespace);
  if (files) {
    const family = files[1], importOnly = importOnlyKinds.has(family);
    if (!(importOnly ? [family + '_import'] : [family + '_import', family + '_bulk']).includes(kind) || action !== 'confirm'
        || body.input.preview_ref !== ref)
      throw failure('确认操作与当前预检结果不一致。');
    return importOnly ? importOnlyBase[family] + '/' + family + '/confirm'
      : kind === family + '_import' ? 'imports/' + family + '/confirm' : 'entities/' + family + '/bulk-confirm';
  }
  if (kind === 'machine' && ['downtime_create', 'downtime_update', 'downtime_cancel'].includes(action) && ref !== null)
    return resource(kind, ref) + '/downtimes/' + action.slice(9);
  if (kind === 'operator' && action === 'machine_permissions' && ref !== null)
    return resource(kind, ref) + '/machine-permissions/confirm';
  if (kind === 'operator' && calendarActions.has(action) && ref !== null)
    return resource(kind, ref) + '/calendar/' + calendarActions.get(action);
  if (!['create', 'update', 'delete'].includes(action) || (action === 'create') !== (ref === null))
    throw failure('保存操作与所选记录不一致。');
  return resource(kind, ref) + '/' + action;
}
function create(namespace) {
  if (!['resources', 'calendar', 'catalog', 'process', 'batches', 'execution'].includes(namespace)
      && ![...fileKinds, ...importOnlyKinds].some(kind => namespace === kind + '_files')) throw failure('基础资料操作入口不正确。');
  const pendingKey = 'aps_workbench_resource_pending_v1' + (namespace === 'resources' ? '' : '_' + namespace);
  const pending = pendingStore({
    key: pendingKey, storage: () => sessionStorage,
    validate: intent => validIntent(intent) && matchesNamespace(namespace, intent),
    encode: pendingRecord,
    readError: () => failure('读不到上次操作记录，请重新打开页面；暂时不能继续保存。', UNKNOWN),
    conflictError: () => failure('上次操作记录已变化，请刷新页面后核对结果。'),
    writeError: () => failure('本次没有提交：操作编号没能保存，请重新打开页面。'),
    removeError: () => failure('结果已确认，但上次操作记录没清掉；重新打开页面后可以再点「查询结果」。')
  });
  const api = {
    query(path, scope, signal) { return T.read(absolute(path), scope, { signal, timeout: 20000 }); },
    preview(path, body, signal) { return T.preview(absolute(path), body, { signal, timeout: 20000 }); },
    async execute(path, body) {
      const result = await T.command(absolute(path), body, { timeout: 20000, expect: prefix + 'commands/' + body.request_key });
      if (!terminal(result)) throw failure('保存结果不完整，还没确认。请点「查询结果」，不要重复提交。', UNKNOWN);
      return result;
    },
    list(kind, scope, signal) {
      const normalized = tableScope(scope);
      return normalized.column_filters ? api.preview(resource(kind) + '/query', normalized, signal) : api.query(resource(kind), normalized, signal);
    },
    // 列表页：总数变少让所请求的页越过末页时，钉住第一次读到的数据版本重读末页，筛选与排序不变；
    // 两次读到的必须是同一份列表的同一种分页，对不上就让用户回第 1 页，不拼两个版本。
    async listPage(kind, scope, signal) {
      const result = await api.list(kind, scope, signal), { total } = result.data.page;
      const last = Math.max(1, Math.ceil(total / scope.size));
      if (scope.page <= last) return result;
      const clamped = await api.list(kind, { ...scope, page: last, snapshot_ref: result.meta.snapshot_ref }, signal);
      if (clamped.data.page.number !== last || clamped.data.page.size !== scope.size || clamped.data.page.total !== total
          || clamped.meta.snapshot_ref !== result.meta.snapshot_ref || clamped.meta.source !== result.meta.source)
        throw failure('翻页位置已失效，请回到第 1 页重新查询。');
      return clamped;
    },
    facets(kind, request, signal) { return api.preview(resource(kind) + '/facets', { ...request, scope: tableScope(request.scope) }, signal); },
    facetSelection(kind, request, signal) { return api.preview(resource(kind) + '/facet-selection', { ...request, scope: tableScope(request.scope) }, signal); },
    choices(kind, scope, signal) { return api.list(kind, scope, signal); },
    // 详情只认所选记录：身份对不上就让用户刷新，不把别的记录当成这条打开。
    async detail(kind, ref, signal) {
      const result = await api.query(resource(kind, ref), {}, signal);
      if (result.data.ref !== ref) throw failure('读到的详情与所选记录不一致，请刷新后重试。');
      return result;
    },
    // 工种关联只认所查的工种与关联类别；翻页钉在第一页读到的数据版本上。
    async relations(ref, scope, signal) {
      const result = await api.query(resource('op_type', ref) + '/relations', scope, signal), data = result.data;
      if (data.parent_ref !== ref || data.parent_kind !== 'op_type' || data.relation !== scope.relation
          || scope.snapshot_ref && result.meta.snapshot_ref !== scope.snapshot_ref)
        throw failure('读到的关联记录或翻页位置不对，请回到第 1 页重新查询。');
      return result;
    },
    summary(signal) { return api.query('resources/summary', {}, signal); },
    calendarDefaults(signal) { return api.query('calendar/defaults', {}, signal); },
    // 设备关联预检只认这个人员，且后端给出了确认许可；返回预检数据本身。
    async machinePermissionsPreview(ref, body, signal) {
      const data = (await api.preview(resource('operator', ref) + '/machine-permissions/preview', body, signal)).data;
      if (data.operator_ref !== ref || data.write_context.capabilities['operator.machine_permissions'] !== true)
        throw failure('设备关联预检不完整，请重新预检。');
      return data;
    },
    async downtimes(ref, signal) {
      const result = await api.query(resource('machine', ref) + '/downtimes', {}, signal), data = result.data;
      if (data.entity_ref !== ref)
        throw failure('设备停机资料不完整，请刷新后重试。');
      return result;
    },
    command(kind, action, ref, body) { return api.execute(commandPath(namespace, kind, action, ref, body), body); },
    // key 来自已校验的本机意图（validIntent）；回执查询失败一律保持“结果未知”。
    async lookup(key) {
      const result = await T.lookup(prefix + 'commands/' + key, {}, { timeout: 20000 });
      if (object(result) && result.state === 'recorded' && result.may_be_in_flight === false && result.resolution === 'recorded' && object(result.receipt) && terminal(result.receipt)) return result.receipt;
      if (object(result) && result.state === 'not_observed' && result.receipt === null && result.may_be_in_flight === true && result.resolution === 'unresolved') return result;
      throw failure('上次操作的结果还没确认，请保留当前页面并点「查询结果」。', UNKNOWN);
    },
    download(path, scope, signal, options = {}) { return T.download(absolute(path), scope, { types: fileTypes, timeout: 20000, ...options, signal }); },
    pendingKey,
    createIntent,
    readPending: pending.read,
    savePending(intent) { return pending.save(intent, null); },
    clearPending(expected) { return pending.save(null, pendingRecord(expected)); }
  };
  return api;
}
// 每个命名空间在本页只有一个实例：组件按自己的领域取，待确认记录与命令会话按命名空间各自独立、跨重挂载保持。
const instances = new Map();
function forNamespace(namespace) {
  let api = instances.get(namespace);
  if (!api) instances.set(namespace, api = create(namespace));
  return api;
}
function useSummary(revision, enabled = true) {
  return useQuery(signal => forNamespace('resources').summary(signal), [revision], { enabled });
}
function useCounts(revision) {
  const read = useSummary(revision), data = read.result && read.result.data;
  const names = { process: 'part', op_int: 'internal_op_types', op_ext: 'external_op_types' };
  // 读取失败只有一份，在 counts.summary.error；各节点只带自己的数量。
  const counts = Object.fromEntries(Object.keys(APSResourceContract.nodes).map(node => [node, { total: data ? data.counts[names[node] || node] : null }]));
  counts.summary = { ...read, data };
  return counts;
}
const APSResourceAPI = { forNamespace, createIntent, useSummary, useCounts };
export { APSResourceAPI, forNamespace, createIntent, useSummary, useCounts };
export default APSResourceAPI;
