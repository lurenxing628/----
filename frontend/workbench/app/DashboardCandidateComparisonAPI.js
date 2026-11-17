import C from './DashboardContract.js';
import { localTime, object, ref48 } from './shared/contract/kit.js';

function context(value) {
  C.check(object(value) && Object.keys(value).every(key => ['run_ref', 'candidate_ref', 'range_start', 'range_end', 'batch_ref'].includes(key)), '候选方案比较条件无效，本页内容没有变化。请重新选择排产记录和候选方案。');
  for (const key of ['run_ref', 'candidate_ref', 'batch_ref']) if (value[key] !== undefined) C.check(ref48(value[key]));
  C.check(!value.candidate_ref || value.run_ref);
  if (value.range_start !== undefined || value.range_end !== undefined) C.check(localTime(value.range_start) && localTime(value.range_end) && value.range_start < value.range_end);
  return { ...value };
}

function rangeFor(input) {
  const start = input && input.start_date + 'T00:00:00', raw = input && input.end_date + 'T00:00:00';
  C.check(localTime(start) && localTime(raw), '这次排产没有有效的提交时间范围，无法比较。请重新选择排产记录。');
  const end = new Date(Date.parse(raw + 'Z') + 86400000).toISOString().slice(0, 19);
  C.check(localTime(end) && start < end); return { range_start: start, range_end: end };
}

async function read(value, signal) {
  const scope = context(value);
  C.check(scope.candidate_ref && Boolean(scope.range_start) === Boolean(scope.range_end), '请先选择候选并填写两个方案共同的开始和结束时间。');
  const query = {
    ...(scope.range_start && scope.range_end ? { range_start: scope.range_start, range_end: scope.range_end } : {}),
    ...(scope.batch_ref ? { batch_ref: scope.batch_ref } : {})
  };
  const comparison = await C.read('/api/workbench/v1/dashboard/candidates/' + scope.candidate_ref + '/comparison', query, signal);
  // 请求只带候选编号，候选属于哪次排产由后端按候选查出；比较条件里的排产记录来自页面选择或恢复的浏览位置，这里核对两者是同一次排产。
  C.check(comparison.data.candidate.run_ref === scope.run_ref, '返回的候选不属于原排产记录，未改指其他记录。');
  return comparison;
}

const DashboardCandidateComparisonAPI = { read, context, rangeFor };

export { DashboardCandidateComparisonAPI, read, context, rangeFor };
export default DashboardCandidateComparisonAPI;
