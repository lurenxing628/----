(function () {
  'use strict';
  const C = window.APSResourceContract, T = window.APSWorkbenchTransport;
  // Keep uncertain intent across workspace remounts using the same adapter identity.
  // Never persist write tokens or guesses about completion to browser storage.
  const sessions = new WeakMap();
  function session(adapter) {
    if (!sessions.has(adapter)) {
      let state = { phase: 'idle' };
      try {
        const intent = adapter.readPending();
        if (intent) state = { phase: 'pending', intent, restored: true };
      } catch (error) { state = { phase: 'pending', error }; }
      sessions.set(adapter, { state, listeners: new Set(), running: false });
    }
    return sessions.get(adapter);
  }
  function publish(store, state) {
    store.state = state; store.listeners.forEach(fn => fn(state));
  }
  function useQuery(load, dependencies, enabled = true) {
    const [state, setState] = React.useState({ loading: enabled, result: null, error: null });
    const [revision, setRevision] = React.useState(0);
    const requested = React.useRef(null), completed = React.useRef(null);
    const identity = React.useMemo(() => ({}), dependencies.concat([revision]));
    React.useEffect(() => {
      let active = true; const controller = new AbortController(), next = requested.current;
      requested.current = null;
      const previous = completed.current && completed.current.identity === identity ? completed.current : null;
      if (!enabled) { setState({ identity, loading: false, result: previous ? previous.result : null, error: null }); if (next) next.reject(new DOMException('读取已取消', 'AbortError')); return () => controller.abort(); }
      if (previous) { setState({ identity, loading: false, result: previous.result, error: null }); return () => controller.abort(); }
      setState({ identity, loading: true, result: null, error: null });
      Promise.resolve().then(() => (next ? next.load : load)(controller.signal)).then(result => {
        if (active) { completed.current = { identity, result }; setState({ identity, loading: false, result, error: null }); if (next) next.resolve(result); }
      }, error => { if (active) { setState({ identity, loading: false, result: null, error }); if (next) next.reject(error); } });
      return () => { active = false; controller.abort(); if (next) next.reject(new DOMException('读取已取消', 'AbortError')); };
    }, [identity, enabled]);
    React.useEffect(() => () => {
      const next = requested.current; requested.current = null;
      if (next) next.reject(new DOMException('读取已取消', 'AbortError'));
    }, []);
    return { ...(state.identity === identity ? state : { loading: enabled, result: null, error: null }), reload: () => setRevision(value => value + 1),
      reloadAndWait: nextLoad => new Promise((resolve, reject) => {
        if (requested.current) requested.current.reject(new DOMException('读取已取消', 'AbortError'));
        requested.current = { load: nextLoad, resolve, reject }; setRevision(value => value + 1);
      }) };
  }
  function useCommand(adapter) {
    const store = session(adapter);
    const [state, setState] = React.useState(store.state);
    React.useEffect(() => {
      setState(store.state); store.listeners.add(setState);
      return () => store.listeners.delete(setState);
    }, [store]);
    React.useEffect(() => {
      if (store.state.restored && store.state.intent) { store.state.restored = false; check(); }
    }, [store]);
    const locked = ['sending', 'pending', 'checking'].includes(state.phase);
    React.useEffect(() => {
      if (!locked) return undefined;
      const warn = event => { event.preventDefault(); event.returnValue = ''; };
      window.addEventListener('beforeunload', warn);
      return () => window.removeEventListener('beforeunload', warn);
    }, [locked]);
    async function check() {
      if (store.running || !store.state.intent) return;
      const intent = store.state.intent;
      store.running = true; publish(store, { ...store.state, phase: 'checking', error: null });
      try {
        const result = await adapter.lookup(intent.request_key);
        const status = C.receipt(result);
        publish(store, { intent, result, phase: status === 'terminal' ? 'done' : 'pending',
          error: status === 'terminal' ? null : C.failure(result.message || window.WorkbenchTerms.outcomes.pending('操作')) });
      } catch (error) { publish(store, { intent, phase: 'pending', error }); }
      finally { store.running = false; }
    }
    async function submit(kind, action, ref, context, input, listCategory) {
      if (store.running || ['sending', 'pending', 'checking', 'done'].includes(store.state.phase)) return;
      let intent;
      try {
        // category keeps the source list; the entity's category belongs to input.fields.
        intent = { kind, action, ref, request_key: T.requestKey('resource'), input, category: listCategory };
        adapter.savePending(intent);
      }
      catch (error) { publish(store, { phase: 'rejected', error }); return; }
      store.running = true; publish(store, { phase: 'sending', intent, error: null });
      try {
        const result = await adapter.command(kind, action, ref, { request_key: intent.request_key, write_token: context.write_token, input });
        publish(store, { intent, result, phase: C.receipt(result) === 'terminal' ? 'done' : 'pending', error: null });
      } catch (error) {
        publish(store, { intent, phase: T.rejected(error) ? 'rejected' : 'pending', error });
      } finally { store.running = false; }
      if (store.state.phase === 'rejected') {
        // 服务端已明确拒绝，没有回执可查；记录清不掉时保留拒绝态和意图，由 reset() 再清。
        try { adapter.clearPending(); }
        catch (error) { publish(store, { ...store.state, error }); return; }
        publish(store, { ...store.state, intent: null });
      }
      if (store.state.phase === 'pending') await check();
    }
    function reset() {
      if (store.running || ['sending', 'pending', 'checking'].includes(store.state.phase)) return false;
      if (store.state.intent) {
        try { adapter.clearPending(); }
        catch (error) { publish(store, { ...store.state, error }); return false; }
      }
      publish(store, { phase: 'idle' });
      return true;
    }
    // 用户改了输入就清掉拒绝态。过期拒绝默认保留，等用户刷新资料；重新预检、换文件本身会产出新的写入依据，传 includeStale 一并清掉。
    function clearRejection({ includeStale = false } = {}) {
      if (store.state.phase !== 'rejected' || !includeStale && C.stale(store.state.error)) return false;
      return reset();
    }
    return { ...state, locked, stale: state.phase === 'rejected' && C.stale(state.error), submit, check, reset, clearRejection };
  }
  const nonnegative = value => Number.isFinite(value) && value >= 0;
  const object = C.object;
  const issues = value => Array.isArray(value) && value.every(item => object(item) && typeof item.message === 'string');
  function calendarSummary(value) {
    const nullable = value => value === null || nonnegative(value);
    const config = value => object(value) && ['known', 'not_configured', 'unavailable'].includes(value.status) &&
      (value.status === 'known' ? nonnegative(value.value) : value.value === null);
    return object(value) && value.time_basis === 'factory_local' && typeof value.factory_today === 'string' &&
      typeof value.basis === 'string' && typeof value.week_start === 'string' && typeof value.week_end === 'string' &&
      config(value.standard_hours) && config(value.holiday_default_efficiency) && issues(value.holiday_default_efficiency.issues) &&
      object(value.stats) && ['configured_days', 'default_days', 'unavailable_days'].every(key => nonnegative(value.stats[key])) &&
      ['work_days', 'rest_days', 'effective_hours', 'normal_effective_hours', 'urgent_effective_hours'].every(key => nullable(value.stats[key])) &&
      Array.isArray(value.stats.known_rest_dates) && Array.isArray(value.days) && value.days.length === 7 &&
      new Set(value.days.map(day => day && day.date)).size === 7 && value.days.every((day, index) => object(day) &&
        typeof day.date === 'string' && day.weekday === index && typeof day.explicit === 'boolean' && issues(day.issues) &&
        (day.status === 'unavailable' ? day.effective === null : day.status === 'known' && object(day.effective) &&
          ['hours', 'efficiency', 'effective_hours', 'normal_effective_hours', 'urgent_effective_hours'].every(key => nonnegative(day.effective[key])) &&
          ['is_working', 'is_rest', 'allow_normal', 'allow_urgent', 'crosses_midnight'].every(key => typeof day.effective[key] === 'boolean') &&
          typeof day.effective.window_start === 'string' && typeof day.effective.window_end === 'string'));
  }
  function readinessSummary(value) {
    return object(value) && value.status === 'unknown' && value.ratio === null &&
      value.basis === 'static_resource_facts_not_schedule_precheck' && typeof value.message === 'string' && object(value.items) &&
      Object.keys(C.nodes).every(key => object(value.items[key]) && object(value.items[key].counts) && issues(value.items[key].issues));
  }
  function useSummary(adapter, revision, enabled = true) {
    return useQuery(async signal => {
      const result = C.query(await adapter.summary(signal), 'summary'), data = { ...result.data };
      if (!calendarSummary(data.calendar)) { data.calendar = null; data.calendar_error = '读到的班表汇总不完整，请刷新后重试。'; }
      if (!readinessSummary(data.readiness)) { data.readiness = null; data.readiness_error = '读到的就绪度数据不完整，请刷新后重试。'; }
      return { ...result, data };
    }, [adapter, revision], enabled);
  }
  function useCounts(adapter, revision) {
    const read = useSummary(adapter, revision), data = read.result && read.result.data;
    const names = { process: 'part', op_int: 'internal_op_types', op_ext: 'external_op_types' };
    const error = read.error ? C.message(read.error) : null;
    const counts = Object.fromEntries(Object.keys(C.nodes).map(node => [node, { total: data ? data.counts[names[node] || node] : null, error }]));
    counts.summary = { ...read, data };
    return counts;
  }
  window.APSResourceSession = { useQuery, useCommand, useCounts, useSummary };
})();
