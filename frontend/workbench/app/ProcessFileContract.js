import C from './resource-contract.js';
import A from './ProcessActionContract.js';
import ResourceTableFilterModel from './ResourceTableFilterModel.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import { failure, object, ref48, token32 } from './shared/contract/kit.js';

function kind(value) { if (!['route', 'hours'].includes(value)) throw failure('文件类型必须是工艺路线或工时定额。'); return value; }
function operation(value) { return 'process_' + kind(value) + '_import.confirm'; }
function hoursCounts(data) {
  return { changed: data.summary.new + data.summary.update,
    unchanged: data.summary.unchanged, rejected: data.summary.rejected };
}
function preview(result, requestedKind, format, request) {
  const d = result.data;
  if (d.kind !== kind(requestedKind) || d.operation !== operation(requestedKind) || !token32(d.preview_ref) || d.format !== format)
    throw failure('文件预检内容、原记录或统计不完整，不能确认导入。');
  if (request.target_ref && (!ref48(request.target_ref) || d.rows.some(row => row.entity_ref !== request.target_ref && row.result !== 'rejected')
      || d.affected_groups.some(group => group.part_ref !== request.target_ref))) throw failure('文件包含其他零件，不能从当前详情提交。');
  return result;
}
function confirmInput(data, groupRefs, zero) {
  const groupSet = new Set(groupRefs);
  if (groupSet.size !== groupRefs.length || groupRefs.length !== data.affected_groups.length
      || data.affected_groups.some(group => !groupSet.has(group.ref))) throw failure('请逐项核对并勾选全部受影响的外协组，未自动解除任何组。');
  if (typeof zero !== 'boolean' || data.zero_review_required && !zero) throw failure('单件工时为 0，排产只计算换型工时。请按 0 导入。');
  return { preview_ref: data.preview_ref, discard_group_refs: groupRefs, confirm_zero_unit_hours: zero };
}
function exportBody(request, selection, format) {
  if (!['all', 'filtered', 'explicit'].includes(selection) || !['csv', 'xlsx'].includes(format)) throw failure('请先选择导出范围和文件格式。');
  if (request.target_ref) {
    if (selection !== 'explicit' || !ref48(request.target_ref) || !token32(request.snapshot_ref) || !Number.isSafeInteger(request.page_size)
        || request.page_size < 1 || request.page_size > 200) throw failure('当前详情只导出这条零件，请刷新详情后再试。');
    return { format, selection, scope: {}, snapshot_ref: request.snapshot_ref, page_size: request.page_size, target_ref: request.target_ref, refs: [request.target_ref] };
  }
  return { ...A.listContext(request), format, selection, ...(selection === 'explicit' ? { refs: A.selection(request.refs, true) } : {}) };
}
function exportPreview(result, requestedKind, body) {
  const d = result.data;
  if (!token32(d.export_ref) || d.selection !== body.selection || d.kind !== kind(requestedKind) || d.format !== body.format
      || d.target_ref !== (body.target_ref ?? null)
      || body.selection === 'filtered' && ResourceTableFilterModel.signature(A.scope(d.scope)) !== ResourceTableFilterModel.signature(A.scope(body.scope))
      || body.selection === 'explicit' && d.part_count !== body.refs.length)
    throw failure('导出预检的类型、范围或数量不完整，未下载文件。');
  return result;
}
function receipt(result, intent, requestedKind, targetRef) {
  if (!intent || intent.kind !== 'process_' + kind(requestedKind) + '_import' || intent.action !== 'confirm' || intent.ref !== undefined && !token32(intent.ref)
      || C.receipt(result) !== 'terminal' || !['committed', 'unchanged'].includes(result.result) || !object(result.data) || result.data.kind !== requestedKind
      || targetRef && (!Array.isArray(result.data.affected_refs) || !result.data.affected_refs.every(ref => ref === targetRef)))
    // 回执在命令发出之后核对：对不上时结果未知，本机待确认记录不能清。
    throw failure(WorkbenchTerms.outcomes.pending('导入'), { committed: 'unknown' });
  return result.data;
}
const APSProcessFiles = { kind, operation, preview, confirmInput, exportBody, exportPreview, receipt, hoursCounts };

export { APSProcessFiles, kind, operation, preview, confirmInput, exportBody, exportPreview, receipt, hoursCounts };
export default APSProcessFiles;
