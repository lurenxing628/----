(function (root, factory) {
  const api = factory(root.APSTrialSample || (typeof require === 'function' ? require('./trial-sample-model.js') : null));
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.APSPlanWorkbench = api;
})(typeof window === 'object' ? window : globalThis, function (model) {
  'use strict';
  const key = 'aps_trial_sample_v1', clone = value => JSON.parse(JSON.stringify(value));
  const base = model.scenarios.find(s => s.id === 'base');
  const same = (a, b) => a.tasks.length === b.tasks.length && a.tasks.every(t => {
    const other = b.tasks.find(x => x.id === t.id);
    return other && ['start', 'end', 'resource', 'person'].every(k => t[k] === other[k]);
  });
  function initial() {
    return { schema: 1, selected: 'balanced', adopted: clone(base), version: 15, taskId: base.tasks[0].id,
      draft: null, history: [], view: 'resource', showBaseline: true, changedOnly: false, search: '', tab: 'impact', theme: 'light' };
  }
  function selected(state) {
    const scenario = state.selected === 'adopted' ? state.adopted : state.selected === 'draft' ? state.draft : model.scenarios.find(s => s.id === state.selected);
    if (!scenario) throw new Error('所选方案不存在。');
    return scenario;
  }
  function validate(state) {
    if (state.schema !== 1 || !Number.isInteger(state.version) || state.version < 15 || !state.adopted || !Array.isArray(state.history)
      || !['resource', 'batch'].includes(state.view) || !['light', 'dark'].includes(state.theme) || !['impact', 'history'].includes(state.tab)
      || typeof state.search !== 'string' || typeof state.showBaseline !== 'boolean' || typeof state.changedOnly !== 'boolean') throw new Error('保存的方案状态格式无效。');
    model.evaluate(state.adopted);
    if (state.draft) model.inspect(state.draft);
    model.inspect(selected(state));
    if (!selected(state).tasks.some(t => t.id === state.taskId)) throw new Error('选中工序不在当前方案中。');
    if (!state.history.every(r => Number.isInteger(r.version) && ['name', 'person', 'reason', 'at', 'previous'].every(k => typeof r[k] === 'string') && Number.isInteger(r.changed))) throw new Error('采用历史不完整。');
    return state;
  }
  function read(storage) {
    try { const raw = storage.getItem(key); return raw ? validate(JSON.parse(raw)) : initial(); }
    catch (error) { return Object.assign(initial(), { error: '本地方案未恢复：' + error.message + ' 原记录未覆盖，请在方案试调中检查或重置。' }); }
  }
  function save(storage, patch) {
    const current = read(storage);
    if (current.error) throw new Error(current.error);
    const next = validate(Object.assign(current, patch));
    storage.setItem(key, JSON.stringify(next));
    return next;
  }
  function adopt(storage, person, reason) {
    if (!person.trim() || !reason.trim()) throw new Error('请填写确认人和采用说明。');
    const state = read(storage);
    if (state.error) throw new Error(state.error);
    const scenario = selected(state), report = model.evaluate(scenario, state.adopted);
    if (same(scenario, state.adopted)) throw new Error('当前方案已经采用。');
    const version = state.version + 1;
    return save(storage, { adopted: clone(scenario), version, history: state.history.concat({ version, name: scenario.name,
      person: person.trim(), reason: reason.trim(), at: new Date().toLocaleString('zh-CN', { hour12: false }), previous: state.adopted.name, changed: report.changedOperations }) });
  }
  function viewModel(state) {
    const scenario = selected(state), inspection = model.inspect(scenario, base);
    return { scenario, report: inspection.report, issues: inspection.issues, task: scenario.tasks.find(t => t.id === state.taskId), samePlan: same, isAdopted: same(scenario, state.adopted) };
  }
  return { key, initial, read, save, adopt, selected, viewModel, same };
});
