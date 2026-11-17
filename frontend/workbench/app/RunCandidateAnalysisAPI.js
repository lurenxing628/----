import { check } from './RunCandidateAPI.js';
import T from './shared/network/transport.js';
import { ref48 } from './shared/contract/kit.js';

// 候选子读取只在主结果就绪后发起：runRef 取主结果的 candidate.run_ref，是必需的预期身份；读到的数据不属于它就不显示。
async function read(candidateRef, runRef, leaf, signal) {
  check(ref48(candidateRef) && ref48(runRef));
  const value = await T.read('/api/workbench/v1/scheduling/candidates/' + candidateRef + '/' + leaf, {}, { signal, timeout: 60000 });
  check(value.data.candidate_ref === candidateRef && value.data.run_ref === runRef, '读到的数据不属于所选候选方案的排产记录。');
  return value;
}
const analysis = (candidateRef, runRef, signal) => read(candidateRef, runRef, 'analysis', signal);
const adoptions = (candidateRef, runRef, signal) => read(candidateRef, runRef, 'adoptions', signal);
const RunCandidateAnalysisAPI = { analysis, adoptions };
export { RunCandidateAnalysisAPI, analysis, adoptions };
export default RunCandidateAnalysisAPI;
