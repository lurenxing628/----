import T from './shared/network/transport.js';

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
async function read(workspace, signal) {
  const q = scope(workspace);
  return T.read('/api/workbench/v1/scheduling/candidates/' + workspace.candidate.candidate_ref + '/baseline', q, { signal, timeout: 60000 });
}
const RunBaselineAPI = { read, scope, resourceIdentity };
export { RunBaselineAPI, read, scope, resourceIdentity };
export default RunBaselineAPI;
