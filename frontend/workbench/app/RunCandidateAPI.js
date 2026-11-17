import T from './shared/network/transport.js';
import { object, ref48, token32, localTime, checker } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：候选列表属于所查的排产记录，候选详情钉在请求的数据版本上，从排产记录进入时候选属于这次排产。
const BASE = '/api/workbench/v1/scheduling';
const count = v => Number.isSafeInteger(v) && v >= 0;
const check = checker('候选数据不完整或不一致，请刷新后重试。');
function exactKeys(v, allowed) {
  return object(v) && Object.keys(v).every(k => allowed.includes(k));
}
function catalogScope(query) {
  check(exactKeys(query, ['page', 'size', 'status', 'sort', 'order', 'snapshot_ref']));
  const q = { page: 1, size: 20, status: 'all', sort: 'sequence', order: 'asc', ...query };
  check(Number.isInteger(q.page) && q.page >= 1 && q.page <= 256 && Number.isInteger(q.size) && q.size >= 1 && q.size <= 50
    && ['all', 'completed', 'partial'].includes(q.status) && ['sequence', 'label', 'task_count'].includes(q.sort)
    && ['asc', 'desc'].includes(q.order) && (q.snapshot_ref === undefined || token32(q.snapshot_ref)));
  if (q.snapshot_ref === undefined) delete q.snapshot_ref;
  return q;
}
function _validateCatalog(v, q) {
  check(token32(v.meta.snapshot_ref) && (!q.snapshot_ref || v.meta.snapshot_ref === q.snapshot_ref));
  return v.data;
}
function workspaceScope(candidateRef, query) {
  check(ref48(candidateRef), '请选择有效的候选方案。');
  check(exactKeys(query, ['range_start', 'range_end', 'batch_ref', 'sort', 'order', 'snapshot_ref']));
  const q = { sort: 'sequence', order: 'asc', ...query };
  check(['sequence', 'start', 'end'].includes(q.sort) && ['asc', 'desc'].includes(q.order)
    && (q.batch_ref === undefined || ref48(q.batch_ref)) && (q.snapshot_ref === undefined || token32(q.snapshot_ref)));
  // 时间只认后端 isoformat 的规范形状，同一规范下直接比字符串就是比时刻。
  if (q.range_start !== undefined || q.range_end !== undefined) check(localTime(q.range_start) && localTime(q.range_end)
    && q.range_start < q.range_end, '读取范围需要成对时间，开始须早于结束。');
  return q;
}
function _validateWorkspace(v, q) {
  check(!q.snapshot_ref || q.snapshot_ref === v.meta.snapshot_ref);
  return v.data;
}
// 文件名非空与后缀由传输层按 Content-Type 断言；这里只核对本领域业务头与当前读取范围。
function download(value, result) {
  const d = result.data;
  check(value.candidate_ref === d.candidate.candidate_ref && value.snapshot_ref === result.meta.snapshot_ref && value.task_count === d.task_count
    && value.row_count === Math.max(1, d.task_count + d.unplanned_operation_count), '下载结果与当前完整范围不一致，没有保存文件。');
  return value;
}
const read = (path, query, signal) => T.read(BASE + path, query, { signal, timeout: 60000 });
async function identity(candidateRef, signal) {
  check(ref48(candidateRef)); return read('/candidates/' + candidateRef + '/identity', {}, signal);
}
async function catalog(runRef, query, signal) {
  check(ref48(runRef)); const q = catalogScope(query), value = await read('/runs/' + runRef + '/candidates', q, signal);
  _validateCatalog(value, q); check(value.data.run_ref === runRef); return value;
}
// 从某次排产记录进入时带 runRef：读到的候选方案必须属于这次排产。
async function workspace(candidateRef, query, signal, runRef) {
  const q = workspaceScope(candidateRef, query), value = await read('/candidates/' + candidateRef + '/workspace', q, signal);
  _validateWorkspace(value, q);
  check(!runRef || value.data.candidate.run_ref === runRef, '候选方案不属于所选排产记录。');
  return value;
}
// 传输层已校验附件、文件名与后缀、格式、魔数与非空；这里只取文件与本领域的四个响应头，与当前读取范围的核对在 download() 里做。
async function exportFile(candidateRef, query, snapshotRef, fmt, signal) {
  check(token32(snapshotRef) && ['csv', 'xlsx'].includes(fmt)); const q = workspaceScope(candidateRef, { ...query, snapshot_ref: snapshotRef });
  const file = await T.download(BASE + '/candidates/' + candidateRef + '/export', { ...q, format: fmt }, { signal, timeout: 60000, types: [T.types[fmt]] });
  const headerCount = key => { const raw = file.header(key); check(raw !== null && /^\d+$/.test(raw) && count(Number(raw))); return Number(raw); };
  return { blob: file.blob, filename: file.filename, candidate_ref: file.header('X-Workbench-Candidate-Ref'),
    snapshot_ref: file.header('X-Workbench-Snapshot-Ref'), task_count: headerCount('X-Workbench-Task-Count'), row_count: headerCount('X-Workbench-Row-Count') };
}
const RunCandidateAPI = { identity, catalog, workspace, export: exportFile, check, catalogScope,
  workspaceScope, download };
export { RunCandidateAPI, identity, catalog, workspace, exportFile as export, check, catalogScope,
  workspaceScope, download };
export default RunCandidateAPI;
