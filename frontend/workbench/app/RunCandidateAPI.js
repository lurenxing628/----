import APSWorkbenchTransport from './shared/network/transport.js';

const T = APSWorkbenchTransport;
const BASE = '/api/workbench/v1/scheduling';
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
function check(value, message = '候选数据不完整或不一致，请刷新后重试。') { if (!value) throw new Error(message); }
function exactKeys(v, allowed) {
  return object(v) && Object.keys(v).every(k => allowed.includes(k));
}
function time(v) {
  if (!text(v) || !/^(?!0000)\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?![\s\S])/.test(v)) return false;
  const calendar = v.slice(0, 19), n = Date.parse(calendar + 'Z');
  return Number.isFinite(n) && new Date(n).toISOString().slice(0, 19) === calendar;
}
// Legacy scopes accept 1–6 fractional digits. Compare without Date's millisecond truncation or rewriting the supplied scope.
const timeKey = value => value.slice(0, 19) + '.' + (value.split('.')[1] || '').padEnd(6, '0');
function summary(v, runRef) {
  check(object(v) && ref(v.candidate_ref) && ref(v.run_ref) && (!runRef || v.run_ref === runRef));
  return v;
}
function validateIdentity(v, candidateRef) {
  const data = v.data;
  check(ref(candidateRef) && data.candidate_ref === candidateRef
    && ref(data.run_ref) && data.status === 'completed', '候选身份与所选方案不一致，请重新打开。');
  return data;
}
function catalogScope(query) {
  check(exactKeys(query, ['page', 'size', 'status', 'sort', 'order', 'snapshot_ref']));
  const q = { page: 1, size: 20, status: 'all', sort: 'sequence', order: 'asc', ...query };
  check(Number.isInteger(q.page) && q.page >= 1 && q.page <= 256 && Number.isInteger(q.size) && q.size >= 1 && q.size <= 50
    && ['all', 'completed', 'partial'].includes(q.status) && ['sequence', 'label', 'task_count'].includes(q.sort)
    && ['asc', 'desc'].includes(q.order) && (q.snapshot_ref === undefined || token(q.snapshot_ref)));
  if (q.snapshot_ref === undefined) delete q.snapshot_ref;
  return q;
}
function _validateCatalog(v, runRef, q) {
  const d = v.data;
  check(ref(runRef) && d.run_ref === runRef && object(d.page)
    && d.page.number === q.page && d.page.size === q.size
    && token(v.meta.snapshot_ref) && (!q.snapshot_ref || v.meta.snapshot_ref === q.snapshot_ref));
  return d;
}
function workspaceScope(candidateRef, query) {
  check(ref(candidateRef), '请选择有效的候选方案。');
  check(exactKeys(query, ['range_start', 'range_end', 'batch_ref', 'sort', 'order', 'snapshot_ref']));
  const q = { sort: 'sequence', order: 'asc', ...query };
  check(['sequence', 'start', 'end'].includes(q.sort) && ['asc', 'desc'].includes(q.order)
    && (q.batch_ref === undefined || ref(q.batch_ref)) && (q.snapshot_ref === undefined || token(q.snapshot_ref)));
  if (q.range_start !== undefined || q.range_end !== undefined) check(time(q.range_start) && time(q.range_end)
    && timeKey(q.range_start) < timeKey(q.range_end), '读取范围需要成对时间，开始须早于结束。');
  return q;
}
function _validateWorkspace(v, candidateRef, q) {
  const d = v.data;
  check(object(d.candidate) && d.candidate.candidate_ref === candidateRef
    && ref(d.candidate.run_ref)
    && (!q.snapshot_ref || q.snapshot_ref === v.meta.snapshot_ref) && d.batch_ref === (q.batch_ref ?? null)
    && object(d.time_scope) && d.time_scope.range_start === (q.range_start ?? null) && d.time_scope.range_end === (q.range_end ?? null));
  return d;
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
  check(ref(candidateRef)); const value = await read('/candidates/' + candidateRef + '/identity', {}, signal);
  validateIdentity(value, candidateRef); return value;
}
async function catalog(runRef, query, signal) {
  check(ref(runRef)); const q = catalogScope(query), value = await read('/runs/' + runRef + '/candidates', q, signal);
  _validateCatalog(value, runRef, q); return value;
}
async function workspace(candidateRef, query, signal) {
  const q = workspaceScope(candidateRef, query), value = await read('/candidates/' + candidateRef + '/workspace', q, signal);
  _validateWorkspace(value, candidateRef, q); return value;
}
// 传输层已校验附件、文件名与后缀、格式、魔数与非空；这里只取文件与本领域的四个响应头，与当前读取范围的核对在 download() 里做。
async function exportFile(candidateRef, query, snapshotRef, fmt, signal) {
  check(token(snapshotRef) && ['csv', 'xlsx'].includes(fmt)); const q = workspaceScope(candidateRef, { ...query, snapshot_ref: snapshotRef });
  const file = await T.download(BASE + '/candidates/' + candidateRef + '/export', { ...q, format: fmt }, { signal, timeout: 60000, types: [T.types[fmt]] });
  const headerCount = key => { const raw = file.header(key); check(raw !== null && /^\d+$/.test(raw) && count(Number(raw))); return Number(raw); };
  return { blob: file.blob, filename: file.filename, candidate_ref: file.header('X-Workbench-Candidate-Ref'),
    snapshot_ref: file.header('X-Workbench-Snapshot-Ref'), task_count: headerCount('X-Workbench-Task-Count'), row_count: headerCount('X-Workbench-Row-Count') };
}
const RunCandidateAPI = { identity, catalog, workspace, export: exportFile, check, ref, time, timeKey, summary, validateIdentity, catalogScope,
  workspaceScope, download };
export { RunCandidateAPI, identity, catalog, workspace, exportFile as export, check, ref, time, timeKey, summary, validateIdentity, catalogScope,
  workspaceScope, download };
export default RunCandidateAPI;
