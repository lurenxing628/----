(function () {
  'use strict';
  const T = window.APSWorkbenchTransport, C = window.TrialContract, ROOT = '/api/workbench/v1', BASE = ROOT + '/trial';
  const PENDING_KEY = 'aps_workbench_trial_pending_v1';
  const validKey = v => typeof v === 'string' && /^trial-[a-f0-9]{48}$/.test(v);
  function pending() {
    let value; try { value = localStorage.getItem(PENDING_KEY); }
    catch (_) { throw new Error('读不到上次操作记录，暂时不能提交。请重新打开页面。'); }
    C.check(value === null || validKey(value), '上次操作记录已损坏，没有删除也没有覆盖。请重新打开页面。'); return value;
  }
  function reserve() {
    C.check(pending() === null, window.WorkbenchTerms.outcomes.pending('试调提交'));
    const key = T.requestKey('trial');
    try { localStorage.setItem(PENDING_KEY, key); } catch (_) { throw new Error('存不下上次操作记录，这次没有提交。请重新打开页面。'); }
    return key;
  }
  function clear(key) {
    C.check(pending() === key, '上次操作记录已变化，没有清除其他操作记录。');
    try { localStorage.removeItem(PENDING_KEY); } catch (_) { throw new Error('上次提交的结果已确认，但上次操作记录没清掉。请点「刷新」后重新查询。'); }
  }
  async function read(path, q, signal, validate) {
    const value = await T.read(ROOT + path, q, { signal, timeout: 60000 });
    if (validate) return validate(value);
    C.envelope(value, q); return value;
  }
  async function preview(input, signal) {
    C.base(input.base); C.scope(input.scope || {});
    const v = await T.preview(BASE + '/drafts/preview', input, { signal, timeout: 60000 }), d = C.envelope(v);
    C.check(JSON.stringify(d.base) === JSON.stringify(input.base) && d.tasks_complete === true && C.count(d.task_count)
      && C.object(d.base_identity) && (input.base.candidate_ref ? d.base_identity.candidate_ref === input.base.candidate_ref : d.base_identity.plan_ref === input.base.plan_ref)
      && d.write_context && d.write_context.capabilities['trial.create'] === true && typeof d.write_context.write_token === 'string');
    C.validation(d.validation); return v;
  }
  async function command(intent, token, key) {
    C.check(validKey(key) && typeof token === 'string');
    const suffix = intent.action === 'create' ? '/drafts' : '/drafts/' + intent.draft_ref + '/' + intent.action;
    return C.receipt(await T.command(BASE + suffix, { request_key: key, write_token: token, input: intent.input },
      { timeout: 60000, expect: BASE + '/commands/' + key }), intent);
  }
  async function lookup(key) {
    C.check(validKey(key)); const v = await read('/trial/commands/' + key), d = v.data;
    C.check(['committed', 'not_observed'].includes(d.state) && d.can_retry_automatically === false);
    if (d.state === 'committed') C.receipt(d.receipt); else C.check(d.receipt === null);
    return d;
  }
  window.TrialAPI = { read, preview, command, lookup, pending, reserve, clear, PENDING_KEY };
})();
