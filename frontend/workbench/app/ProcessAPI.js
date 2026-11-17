import APSResourceAPI from './resource-api.js';
import P from './ProcessContract.js';
import { object, failure, ref48 } from './shared/contract/kit.js';

const base = APSResourceAPI.forNamespace('process');
function part(kind, ref) {
  if (kind !== 'part' || ref != null && !ref48(ref))
    throw failure('这条零件记录已失效，请返回列表重新选择。');
  return 'entities/part' + (ref == null ? '' : '/' + ref);
}
function tableRequest(scope) {
  const value = { ...scope };
  ['sort', 'column_filters'].forEach(key => { if (Array.isArray(value[key]) || object(value[key])) value[key] = JSON.stringify(value[key]); });
  return value;
}
function facetPath(kind, request, selection) {
  part(kind);
  if (!P.columns.some(column => column.key === request.column)) throw failure('此工艺列不支持筛选。');
  return 'process-table/' + (selection ? 'facet-selection/' : 'facets/') + request.column;
}
function filePath(kind, action) {
  if (!['route', 'hours'].includes(kind)) throw failure('文件类型必须是工艺路线或工时定额。');
  return 'process-files/' + kind + '/' + action;
}
// 零件工艺的读写；待确认记录与命令会话走 'process' 命名空间。
const APSProcessAPI = {
  pendingKey: base.pendingKey,
  lookup: base.lookup,
  readPending: base.readPending,
  savePending: base.savePending,
  clearPending: base.clearPending,
  list(kind, scope, signal) { return base.query(part(kind), tableRequest(scope), signal); },
  facets(kind, request, signal) {
    const { column, scope, ...query } = request;
    return base.query(facetPath(kind, request, false), { ...query, scope: JSON.stringify(scope) }, signal);
  },
  facetSelection(kind, request, signal) {
    const { column, scope, ...query } = request;
    return base.query(facetPath(kind, request, true), { ...query, scope: JSON.stringify(scope) }, signal);
  },
  bulkPreview(body, signal) { return base.preview('process/parts/bulk-preview', body, signal); },
  filePreview(kind, mode, body, signal) {
    if (!['import', 'export'].includes(mode)) throw failure('工艺文件操作不正确。');
    return base.preview(filePath(kind, mode === 'import' ? 'preview' : 'export-preview'), body, signal);
  },
  fileDownload(kind, template, scope, signal) {
    if (typeof template !== 'boolean') throw failure('工艺文件下载操作不正确。');
    return base.download(filePath(kind, template ? 'template' : 'export'), scope, signal);
  },
  detail(kind, ref, signal) {
    if (ref == null) throw failure('没有指定要打开的零件，请返回列表重新选择。');
    return base.query(part(kind, ref), {}, signal);
  },
  routePreview(ref, body, signal) {
    if (ref == null) throw failure('没有指定要预检的零件，请返回列表重新选择。');
    part('part', ref);
    return base.preview('process/' + ref + '/route-preview', body, signal);
  },
  stagePreview(ref, action, input, snapshotRef, signal) {
    part('part', ref);
    if (ref == null || !['source_confirm', 'groups_confirm'].includes(action) || typeof snapshotRef !== 'string' || !snapshotRef)
      throw failure('归属检查缺少当前零件资料，请刷新后重试。');
    return base.preview('process/' + ref + '/stage-preview', { action, input, snapshot_ref: snapshotRef }, signal);
  },
  command(kind, action, ref, body) {
    if (kind === 'process' && action === 'create' && ref === null) return base.execute('process/parts/create', body);
    if (kind === 'process_bulk' && action === 'confirm' && typeof ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(ref)
        && body.input && body.input.preview_ref === ref) return base.execute('process/parts/bulk-confirm', body);
    if (['process_route_import', 'process_hours_import'].includes(kind) && action === 'confirm' && typeof ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(ref)
        && body.input && body.input.preview_ref === ref) return base.execute(filePath(kind === 'process_route_import' ? 'route' : 'hours', 'confirm'), body);
    part('part', ref);
    if (kind !== 'process' || ref == null || !['route_confirm', 'source_confirm', 'hours_confirm', 'groups_confirm'].includes(action))
      throw failure('工艺操作与所选零件不一致。');
    return base.execute('process/' + ref + '/' + action, body);
  }
};

export { APSProcessAPI };
export default APSProcessAPI;
