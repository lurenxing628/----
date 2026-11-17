import React from './shared/runtime/react.js';
import C from './TrialContract.js';
import TrialControls from './TrialControls.jsx';
import { object, ref48, failure } from './shared/contract/kit.js';

const PREFIX = 'aps_workbench_trial_view_v1:', EVENT = 'aps-workbench-trial-view-changed';
const fields = ['mode', 'baseline', 'only_changed', 'query', 'result_tab'];
const tabs = ['delivery', 'capacity', 'preparation', 'history', 'adoptions', 'issues', 'tasks', 'unplanned'];
const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
function identity(data) {
  C.check(object(data) && ref48(data.draft_ref), '试调查看偏好缺少原草稿编号。');
  const kind = data.scenario_ref === undefined ? 'draft' : 'scenario', ref = kind === 'draft' ? data.draft_ref : data.scenario_ref;
  C.check(ref48(ref), '试调查看偏好的试调方案编号无效。');
  return { kind, ref };
}
function key(target) {
  C.check(exact(target, ['kind', 'ref']) && ['draft', 'scenario'].includes(target.kind) && ref48(target.ref), '试调查看偏好的记录类型无效。');
  return PREFIX + target.kind + ':' + target.ref;
}
function preferences(value) {
  if (!exact(value, fields) || !['machine', 'operator', 'batch'].includes(value.mode)
      || typeof value.baseline !== 'boolean' || typeof value.only_changed !== 'boolean'
      || typeof value.query !== 'string' || value.query.length > 200 || !tabs.includes(value.result_tab)) {
    throw failure('试调查看偏好的项或格式无效，原记录没有被覆盖。', { code: 'invalid_preferences' });
  }
  return value;
}
function defaults(data) {
  const scope = data.scope;
  return { mode: scope.resource_type || 'machine', baseline: true, only_changed: false,
    query: scope.query === undefined ? '' : scope.query, result_tab: 'delivery' };
}
function storage(value) { return value === undefined ? window.localStorage : value; }
function read(target, store) {
  const name = key(target); let raw;
  try { raw = storage(store).getItem(name); }
  catch (_) { throw failure('本机试调查看偏好读取失败。', { code: 'read_unavailable' }); }
  if (raw === null) return null;
  const corrupt = () => failure('本机试调查看偏好损坏，原记录未覆盖。', { code: 'corrupt_preferences' });
  if (typeof raw !== 'string' || raw.length > 2048) throw corrupt();
  let value;
  try { value = JSON.parse(raw); } catch (_) { throw corrupt(); }
  if (!exact(value, ['schema_version', 'kind', 'ref', 'preferences']) || value.schema_version !== 1
      || value.kind !== target.kind || value.ref !== target.ref) {
    throw failure('本机试调查看偏好的版本或所属记录不一致，没有恢复其他记录。', { code: 'invalid_identity' });
  }
  return preferences(value.preferences);
}
function write(target, initial, patch, store) {
  const name = key(target);
  if (!object(patch) || !Object.keys(patch).every(field => fields.includes(field))) {
    throw failure('试调查看偏好含未知的项，没有保存业务内容。', { code: 'invalid_preferences' });
  }
  const value = preferences({ ...(read(target, store) || initial), ...patch });
  try { storage(store).setItem(name, JSON.stringify({ schema_version: 1, kind: target.kind, ref: target.ref, preferences: value })); }
  catch (_) { throw failure('本次查看偏好尚未保存，本页选择已保留。', { code: 'write_unavailable' }); }
  return value;
}
function clear(target, store) {
  const name = key(target);
  try {
    storage(store).removeItem(name);
  } catch (_) { throw failure('查看偏好清除失败，请重试。', { code: 'clear_unavailable' }); }
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
  const notify = value => window.dispatchEvent(new CustomEvent(EVENT, { detail: { key: name, value, source: pending } }));
  function change(patch) {
    if (active.current !== name || !current.value) return false;
    let merged, value;
    try {
      merged = { ...pending.current.patch, ...patch }; value = preferences({ ...current.value, ...merged });
    } catch (error) { setState({ ...current, error }); return false; }
    pending.current.patch = merged;
    try {
      const saved = write(target, initial, merged);
      pending.current.patch = {}; setState({ name, value: saved, error: null }); notify(saved); return true;
    } catch (error) { setState({ name, value, error }); return false; }
  }
  function reload() {
    if (active.current !== name) return;
    if (Object.keys(pending.current.patch).length) change({});
    else setState(loaded());
  }
  function reset() {
    if (active.current !== name) return;
    try { clear(target); pending.current.patch = {}; setState({ name, value: initial, error: null }); notify(initial); }
    catch (error) { setState(previous => ({ ...previous, error })); }
  }
  React.useEffect(() => {
    function refresh(value) {
      if (active.current !== name) return;
      const next = value === undefined ? loaded() : { name, value, error: null };
      setState(previous => Object.keys(pending.current.patch).length && previous.name === name
        ? { name, value: next.value ? { ...next.value, ...pending.current.patch } : previous.value, error: next.error || previous.error }
        : next);
    }
    const local = event => {
      const detail = event.detail;
      if (detail && detail.key === name && detail.source !== pending) refresh(detail.value);
    };
    const external = event => { if (event.key === name || event.key === null) refresh(); };
    refresh(); window.addEventListener(EVENT, local); window.addEventListener('storage', external);
    return () => { window.removeEventListener(EVENT, local); window.removeEventListener('storage', external); };
  }, [name, signature]);
  return { value: current.value, error: current.error, pending: Object.keys(pending.current.patch).length > 0, change, reload, reset };
}
function Notice({ state, label }) {
  if (!state.error) return null;
  const U = TrialControls;
  return React.createElement('div', { className: 'tt-notice', role: 'region', 'aria-label': label },
    React.createElement(U.ErrorBox, { error: state.error }),
    React.createElement('div', { className: 'tt-tools' },
      React.createElement(U.Button, { icon: 'refresh-cw', onClick: state.reload, 'aria-label': '刷新' + label }, state.pending ? '重试保存偏好' : '刷新偏好'),
      React.createElement(U.Button, { icon: 'rotate-ccw', onClick: state.reset, 'aria-label': '清除' + label }, '清除本机的这份偏好')));
}
const TrialViewState = { identity, key, defaults, read, write, clear, useView, Notice };
export { TrialViewState, identity, key, defaults, read, write, clear, useView, Notice };
export default TrialViewState;
