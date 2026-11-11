import RunCandidateAPI from './RunCandidateAPI.js';
import APSWorkbenchTransport from './shared/network/transport.js';

const A = RunCandidateAPI, T = APSWorkbenchTransport, { check, ref } = A;
async function read(candidateRef, runRef, leaf, signal) {
  check(ref(candidateRef) && (!runRef || ref(runRef)));
  const value = await T.read('/api/workbench/v1/scheduling/candidates/' + candidateRef + '/' + leaf, {}, { signal, timeout: 60000 });
  const d = value.data;
  check(d.candidate_ref === candidateRef && ref(d.run_ref) && (!runRef || d.run_ref === runRef));
  return value;
}
const analysis = (candidateRef, runRef, signal) => read(candidateRef, runRef, 'analysis', signal);
const adoptions = (candidateRef, runRef, signal) => read(candidateRef, runRef, 'adoptions', signal);
const RunCandidateAnalysisAPI = { analysis, adoptions };
export { RunCandidateAnalysisAPI, analysis, adoptions };
export default RunCandidateAnalysisAPI;
