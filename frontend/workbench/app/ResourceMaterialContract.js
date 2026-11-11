import APSWorkbenchTransport from './shared/network/transport.js';
import APSResourceContract from './resource-contract.js';

const C = APSResourceContract;
const token = value => typeof value === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value);
function create(kind = 'material', label = '物料') {
  const fields = { business_code: '物料编号', label: '名称', spec: '规格', unit: '单位', stock_qty: '库存数量', status: '状态', remark: '备注', created_at: '创建时间' };
  const results = { new: '新增', update: '更新', unchanged: '不变', delete: '删除', rejected: '拒绝' };
  const paths = {
    import: 'imports/' + kind + '/preview', bulk: 'entities/' + kind + '/bulk-preview', export: 'exports/' + kind + '/preview',
    download: 'exports/' + kind, template: 'templates/' + kind
  };
  function preview(result, mode, expected) {
    const data = result.data;
    if (!token(data.preview_ref) || data.operation !== kind + (mode === 'import' ? '.import' : '.bulk_delete'))
      throw C.failure('预检结果不完整，本批没有提交。请重新预检。');
    if (mode === 'import' && data.format !== expected)
      throw C.failure('导入预检的文件格式或增量方式不一致，本批没有提交。');
    if (mode === 'bulk' && (data.rows.length !== expected.length
        || !data.rows.every((row, index) => row.entity_ref === expected[index])))
      throw C.failure('删除预检与勾选的' + label + '不一致，本批没有提交。');
    return result;
  }
  function exportPreview(result, selection) {
    const data = result.data;
    if (!token(data.export_ref) || data.selection !== selection) throw C.failure('导出预检内容不完整，没有开始下载。');
    return result;
  }
  function source(request) { return request.source || request.scope && request.scope.source; }
  function selection(request) {
    if (!Array.isArray(request.refs) || request.refs.some(ref => typeof ref !== 'string' || !/^[0-9a-f]{48}$/.test(ref))
        || new Set(request.refs).size !== request.refs.length) throw C.failure('缺少明确勾选的' + label + '，请重新勾选。');
    return request.refs;
  }
  function listContext(request) {
    const input = request.scope, scope = {};
    ['query', 'status', 'sort', 'direction'].forEach(key => {
      if (C.own(input, key) && input[key] !== undefined && !(key === 'status' && (input[key] === '' || input[key] === null))) scope[key] = input[key];
    });
    if (C.own(input, 'column_filters')) {
      if (!C.object(input.column_filters)) throw C.failure('列筛选范围不完整，请刷新列表。');
      if (Object.keys(input.column_filters).length) scope.column_filters = input.column_filters;
    }
    if (kind === 'op_type') {
      if (!['internal', 'external'].includes(input.category)) throw C.failure('缺少工种类别，请关闭向导，重新打开自制或外协工种。');
      scope.category = input.category;
    }
    const snapshot = request.snapshot_ref || input.snapshot_ref;
    const size = request.page && request.page.size || request.page_size || input.size;
    if (!token(snapshot) || !Number.isSafeInteger(size) || size < 1 || size > 200)
      throw C.failure('翻页位置已失效，请关闭向导后回到第 1 页重新查询。');
    return { scope, snapshot_ref: snapshot, page_size: size };
  }
  function requestBody(mode, request, selected) {
    const body = listContext(request);
    if (mode === 'bulk') return { ...body, action: 'delete', refs: selection(request) };
    return { ...body, selection: selected, ...(selected === 'selected' ? { refs: selection(request) } : {}) };
  }
  function blocked(result, requestedSource) {
    if (!result) return '请先完成预检。';
    if (requestedSource !== 'production') return '当前不是生产数据，不能提交。';
    const data = result.data, context = data.write_context;
    if (!data.can_confirm || data.summary.rejected) return '存在未通过检查的行，请修正后重新预检。';
    if (context.capabilities[data.operation] !== true) {
      const reason = context.blocked_reasons.find(item => item.action === data.operation);
      return reason ? reason.message : '系统不允许本次确认。';
    }
    if (Date.now() >= Date.parse(data.expires_at)) return '预检结果已过期，请重新预检。';
    return '';
  }
  async function validateFile(file, format) {
    if (!file || !['csv', 'xlsx'].includes(format) || !file.name.toLowerCase().endsWith('.' + format))
      throw C.failure('请选择与文件格式一致的 .csv 或 .xlsx 文件。');
    if (!file.size) throw C.failure('文件为空，请重新选择。');
    const bytes = new Uint8Array(await file.slice(0, 4).arrayBuffer());
    if (format === 'xlsx' && (bytes[0] !== 80 || bytes[1] !== 75 || bytes[2] !== 3 || bytes[3] !== 4))
      throw C.failure('文件内容不是 XLSX 工作簿，请勿只修改扩展名。');
    if (format === 'csv' && (bytes.includes(0) || bytes[0] === 80 && bytes[1] === 75))
      throw C.failure('文件内容不是 UTF-8 CSV，请核对文件格式。');
  }
  function saveDownload(download, format) {
    if (download.contentType !== APSWorkbenchTransport.types[format]) throw C.failure('下载文件与所选格式不一致，没有保存文件。');
    APSWorkbenchTransport.saveBlob(download.filename, download.blob);
    return download.filename;
  }
  const confirmationHint = kind === 'material' ? '涉及已有物料需求，需核对修改前后内容。' : '涉及关键项或已有关联，需核对修改前后内容。';
  const acknowledgeHint = kind === 'material' ? '已核对在用物料的修改前后内容，确认这些更新。' : '已核对关键项和关联关系的修改前后内容，确认这些更新。';
  const rowsMatchSelection = true;
  return { kind, label, fields, results, paths, preview, exportPreview, source, selection, listContext, requestBody, blocked, validateFile, saveDownload, confirmationHint, acknowledgeHint, rowsMatchSelection };
}
const defaultInstance = create();
const APSResourceMaterial = { ...defaultInstance, create };
export { APSResourceMaterial, create };
export default APSResourceMaterial;
