import DashboardContract from './DashboardContract.js';
import RunCandidateAPI from './RunCandidateAPI.js';

const C = DashboardContract, A = RunCandidateAPI;

function context(value) {
  C.check(C.object(value) && Object.keys(value).every(key => ['run_ref', 'candidate_ref', 'range_start', 'range_end', 'batch_ref'].includes(key)), '候选方案比较条件无效，本页内容没有变化。请重新选择排产记录和候选方案。');
  for (const key of ['run_ref', 'candidate_ref', 'batch_ref']) if (value[key] !== undefined) C.check(C.ref(value[key]));
  C.check(!value.candidate_ref || value.run_ref);
  if (value.range_start !== undefined || value.range_end !== undefined) C.check(A.time(value.range_start) && A.time(value.range_end) && value.range_start < value.range_end);
  return { ...value };
}

function rangeFor(input) {
  const start = input && input.start_date + 'T00:00:00', raw = input && input.end_date + 'T00:00:00';
  C.check(A.time(start) && A.time(raw), '这次排产没有有效的提交时间范围，无法比较。请重新选择排产记录。');
  const end = new Date(Date.parse(raw + 'Z') + 86400000).toISOString().slice(0, 19);
  C.check(A.time(end) && start < end); return { range_start: start, range_end: end };
}

function validate(payload, scope) {
  const d = payload && payload.data;
  C.check(C.object(d) && C.object(d.candidate) && C.object(d.generation) && C.object(d.baseline) && C.object(d.time_scope));
  A.summary(d.candidate, scope.run_ref);
  C.check(d.candidate.candidate_ref === scope.candidate_ref, '返回的候选与所选方案不一致，请重新选择。');
  const g = d.generation, input = g.input;
  C.check(g.run_ref === d.candidate.run_ref && (!scope.run_ref || g.run_ref === scope.run_ref)
    && C.object(input) && Array.isArray(input.batch_refs));
  const expected = scope.batch_ref ? [scope.batch_ref] : input.batch_refs.slice().sort();
  const bounds = scope.range_start && scope.range_end ? { range_start: scope.range_start, range_end: scope.range_end } : rangeFor(input);
  C.check(d.time_scope.range_start === bounds.range_start && d.time_scope.range_end === bounds.range_end
    && d.batch_ref === (scope.batch_ref || null) && C.equal(d.batch_refs, expected)
    && (d.baseline.available ? C.ref(d.baseline.baseline_ref) : d.baseline.baseline_ref === null));
  return d;
}

async function read(value, signal) {
  const scope = context(value);
  C.check(scope.candidate_ref && Boolean(scope.range_start) === Boolean(scope.range_end), '请先选择候选并填写两个方案共同的开始和结束时间。');
  const query = {
    ...(scope.range_start && scope.range_end ? { range_start: scope.range_start, range_end: scope.range_end } : {}),
    ...(scope.batch_ref ? { batch_ref: scope.batch_ref } : {})
  };
  const payload = await C.read('/api/workbench/v1/dashboard/candidates/' + scope.candidate_ref + '/comparison', query, signal);
  validate(payload, scope); return payload;
}

const DashboardCandidateComparisonAPI = { read, validate, context, rangeFor };

export { DashboardCandidateComparisonAPI, read, validate, context, rangeFor };
export default DashboardCandidateComparisonAPI;
