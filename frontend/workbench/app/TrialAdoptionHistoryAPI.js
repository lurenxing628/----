import C from './TrialContract.js';
import TrialAPI from './TrialAPI.js';
import { ref48 } from './shared/contract/kit.js';

const states = ['all', 'current', 'historical', 'unavailable'];
async function read(scenarioRef, q, signal) {
  C.check(ref48(scenarioRef) && states.includes(q.status) && Number.isSafeInteger(q.page) && q.page > 0
    && Number.isSafeInteger(q.size) && q.size > 0 && q.size <= 50);
  return TrialAPI.read('/trial/scenarios/' + scenarioRef + '/adoption-history', q, signal);
}
const TrialAdoptionHistoryAPI = { read, states };
export { TrialAdoptionHistoryAPI, read, states };
export default TrialAdoptionHistoryAPI;
