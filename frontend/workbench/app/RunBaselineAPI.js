import APSWorkbenchTransport from './shared/network/transport.js';

const T = APSWorkbenchTransport;
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
function check(ok) { if (!ok) throw new Error('原安排对照缺失，或者跟当前候选方案范围不一致，没有显示上次结果。请点「刷新原安排」。'); }
function scope(data) {
  const q = { sort: 'sequence', order: 'asc' }, t = data.time_scope;
  if (t.range_start !== null || t.range_end !== null) { q.range_start = t.range_start; q.range_end = t.range_end; }
  if (data.batch_ref !== null) q.batch_ref = data.batch_ref;
  return q;
}
function resourceIdentity(side, kind) {
  const value = side[kind];
  if (value !== null) return value.ref === null ? undefined : value.ref;
  return side.data_gaps.some(gap => gap.field === kind || gap.field === kind + '.ref') ? undefined : null;
}
function _validate(payload, workspace) {
  const d = payload.data, wg = workspace.generation;
  check(object(d.candidate) && d.candidate.candidate_ref === workspace.candidate.candidate_ref
    && d.batch_ref === (workspace.batch_ref ?? null) && object(d.time_scope)
    && d.time_scope.range_start === workspace.time_scope.range_start && d.time_scope.range_end === workspace.time_scope.range_end
    && object(d.generation) && d.generation.run_ref === wg.run_ref
    && object(d.baseline) && d.baseline.kind === 'admission_official'
    && d.baseline.baseline_ref === wg.baseline.baseline_ref);
  return d;
}
async function read(workspace, signal) {
  const q = scope(workspace);
  const payload = await T.read('/api/workbench/v1/scheduling/candidates/' + workspace.candidate.candidate_ref + '/baseline', q, { signal, timeout: 60000 });
  _validate(payload, workspace); return payload;
}
const RunBaselineAPI = { read, scope, resourceIdentity };
export { RunBaselineAPI, read, scope, resourceIdentity };
export default RunBaselineAPI;
