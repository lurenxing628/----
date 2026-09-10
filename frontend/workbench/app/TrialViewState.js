(function () {
  'use strict';
  const C = window.TrialContract, PREFIX = 'aps_workbench_trial_view_v1:', EVENT = 'aps-workbench-trial-view-changed';
  const fields = ['mode', 'baseline', 'only_changed', 'query', 'result_tab'];
  const tabs = ['delivery', 'capacity', 'history', 'adoptions', 'issues', 'tasks', 'unplanned'];
  const exact = (value, keys) => C.object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
  function problem(code, message) { const error = new Error(message); error.code = code; return error; }
  function identity(data) {
    C.check(C.object(data) && C.ref(data.draft_ref), '试调查看偏好缺少原草稿身份。');
    const kind = data.scenario_ref === undefined ? 'draft' : 'scenario', ref = kind === 'draft' ? data.draft_ref : data.scenario_ref;
    C.check(C.ref(ref), '试调查看偏好的场景身份无效。');
    return { kind, ref };
  }
  function key(target) {
    C.check(exact(target, ['kind', 'ref']) && ['draft', 'scenario'].includes(target.kind) && C.ref(target.ref), '试调查看偏好的身份类型无效。');
    return PREFIX + target.kind + ':' + target.ref;
  }
  function preferences(value) {
    if (!exact(value, fields) || !['machine', 'operator', 'batch'].includes(value.mode)
        || typeof value.baseline !== 'boolean' || typeof value.only_changed !== 'boolean'
        || typeof value.query !== 'string' || value.query.length > 200 || !tabs.includes(value.result_tab)) {
      throw problem('invalid_preferences', '试调查看偏好的字段或格式无效，原记录未覆盖。');
    }
    return value;
  }
  function defaults(data) {
    const scope = C.scope(data.scope);
    return { mode: scope.resource_type || 'machine', baseline: true, only_changed: false,
      query: scope.query === undefined ? '' : scope.query, result_tab: 'delivery' };
  }
  function storage(value) { return value === undefined ? window.localStorage : value; }
  function read(target, store) {
    const name = key(target); let raw;
    try { raw = storage(store).getItem(name); }
    catch (_) { throw problem('read_unavailable', '本机试调查看偏好无法读取，原记录未替换。'); }
    if (raw === null) return null;
    let value;
    try {
      if (typeof raw !== 'string' || raw.length > 2048) throw new Error('invalid size');
      value = JSON.parse(raw);
    } catch (_) { throw problem('corrupt_preferences', '本机试调查看偏好损坏，原记录未覆盖。'); }
    if (!exact(value, ['schema_version', 'kind', 'ref', 'preferences']) || value.schema_version !== 1
        || value.kind !== target.kind || value.ref !== target.ref) {
      throw problem('invalid_identity', '本机试调查看偏好的版本或原对象身份不一致，未恢复其他对象。');
    }
    return preferences(value.preferences);
  }
  function write(target, initial, patch, store) {
    const name = key(target);
    if (!C.object(patch) || !Object.keys(patch).every(field => fields.includes(field))) {
      throw problem('invalid_preferences', '试调查看偏好含未知字段，未保存业务内容。');
    }
    preferences(initial); preferences({ ...initial, ...patch });
    const value = preferences({ ...(read(target, store) || initial), ...patch });
    try { storage(store).setItem(name, JSON.stringify({ schema_version: 1, kind: target.kind, ref: target.ref, preferences: value })); }
    catch (_) { throw problem('write_unavailable', '本次查看偏好尚未保存，本页选择已保留。'); }
    const saved = read(target, store);
    if (!saved || !fields.every(field => saved[field] === value[field])) {
      throw problem('write_unverified', '本次查看偏好未能核实保存，本页选择已保留。');
    }
    return value;
  }
  function clear(target, store) {
    const name = key(target);
    try {
      const targetStorage = storage(store);
      targetStorage.removeItem(name);
      if (targetStorage.getItem(name) !== null) throw new Error('not removed');
    } catch (_) { throw problem('clear_unavailable', '无法核实本对象查看偏好已清除，未清理其他对象。'); }
  }
  function useView(data) {
    const target = identity(data), name = key(target), initial = defaults(data), signature = JSON.stringify(initial);
    const pending = React.useRef({ name, patch: {} }), active = React.useRef(name); active.current = name;
    if (pending.current.name !== name) pending.current = { name, patch: {} };
    function loaded() {
      try { return { name, value: read(target) || initial, error: null }; }
      catch (error) { return { name, value: null, error }; }
    }
    const [state, setState] = React.useState(loaded), current = state.name === name ? state : loaded();
    const notify = () => window.dispatchEvent(new CustomEvent(EVENT, { detail: { key: name } }));
    function change(patch) {
      if (active.current !== name || !current.value) return false;
      let merged, value;
      try {
        if (!C.object(patch) || !Object.keys(patch).every(field => fields.includes(field))) throw problem('invalid_preferences', '查看偏好含未知字段，未保存。');
        merged = { ...pending.current.patch, ...patch }; value = preferences({ ...current.value, ...merged });
      } catch (error) { setState({ ...current, error }); return false; }
      pending.current.patch = merged;
      try {
        const saved = write(target, initial, merged);
        pending.current.patch = {}; setState({ name, value: saved, error: null }); notify(); return true;
      } catch (error) { setState({ name, value, error }); return false; }
    }
    function reload() {
      if (active.current !== name) return;
      if (Object.keys(pending.current.patch).length) change({});
      else setState(loaded());
    }
    function reset() {
      if (active.current !== name) return;
      try { clear(target); pending.current.patch = {}; setState(loaded()); notify(); }
      catch (error) { setState(previous => ({ ...previous, error })); }
    }
    React.useEffect(() => {
      function refresh() {
        if (active.current !== name) return;
        const next = loaded();
        setState(previous => Object.keys(pending.current.patch).length && previous.name === name
          ? { name, value: next.value ? { ...next.value, ...pending.current.patch } : previous.value, error: next.error || previous.error }
          : next);
      }
      const local = event => { if (event.detail && event.detail.key === name) refresh(); };
      const external = event => { if (event.key === name || event.key === null) refresh(); };
      refresh(); window.addEventListener(EVENT, local); window.addEventListener('storage', external);
      return () => { window.removeEventListener(EVENT, local); window.removeEventListener('storage', external); };
    }, [name, signature]);
    return { value: current.value, error: current.error, pending: Object.keys(pending.current.patch).length > 0, change, reload, reset };
  }
  function Notice({ state, label }) {
    if (!state.error) return null;
    const U = window.TrialControls;
    return React.createElement('div', { className: 'tt-notice', role: 'region', 'aria-label': label },
      React.createElement(U.ErrorBox, { error: state.error }),
      React.createElement('div', { className: 'tt-tools' },
        React.createElement(U.Button, { icon: 'refresh-cw', onClick: state.reload, 'aria-label': '重读' + label }, state.pending ? '重试保存偏好' : '重读偏好'),
        React.createElement(U.Button, { icon: 'rotate-ccw', onClick: state.reset, 'aria-label': '清除' + label }, '清除此对象本机偏好')));
  }
  window.TrialViewState = { identity, key, defaults, read, write, clear, useView, Notice };
})();
