import TrialContract from './TrialContract.js';
import TrialAPI from './TrialAPI.js';

const C = TrialContract;
const states = ['all', 'current', 'historical', 'unavailable'];
function validate(value, scenarioRef, q) {
  const d = C.envelope(value, q), p = d.page, source = d.source;
  C.check(d.scope && d.scope.kind === 'trial_adoption_history' && d.scope.scenario_ref === scenarioRef
    && d.scope.source === 'production' && d.scope.status === q.status && d.scope.size === q.size);
  C.check(source && source.scenario_ref === scenarioRef);
  C.check(p && p.number === q.page && p.size === q.size);
  return value;
}
async function read(scenarioRef, q, signal) {
  C.check(C.ref(scenarioRef) && states.includes(q.status) && Number.isSafeInteger(q.page) && q.page > 0
    && Number.isSafeInteger(q.size) && q.size > 0 && q.size <= 50);
  return TrialAPI.read('/trial/scenarios/' + scenarioRef + '/adoption-history', q, signal,
    value => validate(value, scenarioRef, q));
}
const TrialAdoptionHistoryAPI = { read, states };
export { TrialAdoptionHistoryAPI, read, states };
export default TrialAdoptionHistoryAPI;
