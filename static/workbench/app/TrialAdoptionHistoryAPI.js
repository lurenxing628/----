(function () {
  'use strict';

  const C = window.TrialContract;
  const states = ['all', 'current', 'historical', 'unavailable'];
  function validate(value, scenarioRef, q) {
    const d = C.envelope(value, q),
      p = d.page,
      source = d.source;
    C.check(d.scope && d.scope.kind === 'trial_adoption_history' && d.scope.scenario_ref === scenarioRef && d.scope.source === 'production' && d.scope.status === q.status && d.scope.size === q.size);
    C.check(source && source.scenario_ref === scenarioRef && C.ref(source.draft_ref) && typeof source.name === 'string');
    C.base(source.base);
    C.check(source.baseline && (source.baseline.version === null && source.baseline.plan_ref === null || C.count(source.baseline.version) && source.baseline.version > 0 && C.ref(source.baseline.plan_ref)));
    C.check(p && p.number === q.page && p.size === q.size && C.count(p.total) && p.total <= 1000 && p.pages === Math.ceil(p.total / p.size) && C.count(d.total_adoptions) && d.total_adoptions >= p.total && Array.isArray(d.items) && d.items.length === Math.min(p.size, Math.max(0, p.total - (p.number - 1) * p.size)));
    const seen = new Set();
    d.items.forEach(r => {
      C.check(/^[a-f0-9]{32}$/.test(r.receipt_ref) && !seen.has(r.receipt_ref) && typeof r.request_key === 'string' && r.scenario_ref === scenarioRef && r.draft_ref === source.draft_ref && states.slice(1).includes(r.current_state) && (q.status === 'all' || q.status === r.current_state));
      seen.add(r.receipt_ref);
      const plan = r.committed_plan,
        current = r.official_plan;
      C.check(plan && C.ref(plan.plan_ref) && C.count(plan.version) && plan.version > source.baseline.version && C.count(plan.row_count) && typeof r.committed_at_utc === 'string' && /^\d{4}-\d{2}-\d{2}T.*Z$/.test(r.committed_at_utc) && Number.isFinite(Date.parse(r.committed_at_utc)));
      C.check(C.object(r.adoption) && ['reason', 'declared_operator', 'application_operator', 'adopted_at'].every(k => r.adoption[k] === null || typeof r.adoption[k] === 'string'));
      C.issues(r.evidence_gaps);
      if (current !== null) {
        C.check(current.plan_ref === plan.plan_ref && String(current.version) === String(plan.version) && current.kind === 'official' && typeof current.is_current_official === 'boolean' && current.capabilities && typeof current.capabilities.view === 'boolean');
        C.check(r.current_state === (current.capabilities.view ? current.is_current_official ? 'current' : 'historical' : 'unavailable'));
      } else C.check(r.current_state === 'unavailable' && r.evidence_gaps.length > 0);
    });
    return value;
  }
  async function read(scenarioRef, q, signal) {
    C.check(C.ref(scenarioRef) && states.includes(q.status) && Number.isSafeInteger(q.page) && q.page > 0 && Number.isSafeInteger(q.size) && q.size > 0 && q.size <= 50);
    const value = await window.TrialAPI.read('/trial/scenarios/' + scenarioRef + '/adoption-history', q, signal);
    return validate(value, scenarioRef, q);
  }
  window.TrialAdoptionHistoryAPI = {
    read,
    validate,
    states
  };
})();
