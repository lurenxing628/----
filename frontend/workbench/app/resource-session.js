(function () {
  'use strict';
  const C = window.APSResourceContract;
  // Keep uncertain intent across workspace remounts using the same adapter identity.
  // Never persist write tokens or guesses about completion to browser storage.
  const sessions = new WeakMap();
  function session(adapter) {
    if (!sessions.has(adapter)) {
      let state = { phase: 'idle' };
      try {
        const intent = typeof adapter.readPending === 'function' && adapter.readPending();
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
    const identity = React.useMemo(() => ({}), dependencies.concat([revision, enabled]));
    React.useEffect(() => {
      let active = true; const controller = new AbortController();
      if (!enabled) { setState({ identity, loading: false, result: null, error: null }); return () => controller.abort(); }
      setState({ identity, loading: true, result: null, error: null });
      Promise.resolve().then(() => load(controller.signal)).then(result => {
        if (active) setState({ identity, loading: false, result, error: null });
      }, error => { if (active) setState({ identity, loading: false, result: null, error }); });
      return () => { active = false; controller.abort(); };
    }, [identity]);
    return { ...(state.identity === identity ? state : { loading: enabled, result: null, error: null }), reload: () => setRevision(value => value + 1) };
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
      if (typeof adapter.lookup !== 'function') {
        publish(store, { ...store.state, phase: 'pending', error: C.failure('结果待核实；回执查询尚未接入。请保留当前页面。') }); return;
      }
      store.running = true; publish(store, { ...store.state, phase: 'checking', error: null });
      try {
        const result = await adapter.lookup(intent.request_key, new AbortController().signal);
        const status = C.receipt(result);
        publish(store, { intent, result, phase: status === 'terminal' ? 'done' : 'pending',
          error: status === 'terminal' ? null : C.failure(result && result.message || '尚未查到完成回执，原请求仍可能执行中。请继续核实，不要重复保存。') });
      } catch (error) { publish(store, { intent, phase: 'pending', error }); }
      finally { store.running = false; }
    }
    async function submit(kind, action, ref, context, input, category) {
      if (store.running || ['sending', 'pending', 'checking', 'done'].includes(store.state.phase)) return;
      if (typeof adapter.command !== 'function') {
        publish(store, { phase: 'rejected', error: C.failure('保存接口尚未接入。') }); return;
      }
      let intent;
      try {
        intent = { kind, action, ref, request_key: C.requestKey(), input, category };
        if (typeof adapter.savePending === 'function') adapter.savePending(intent);
      }
      catch (error) { publish(store, { phase: 'rejected', error }); return; }
      store.running = true; publish(store, { phase: 'sending', intent, error: null });
      try {
        const result = await adapter.command(kind, action, ref, {
          request_key: intent.request_key, write_token: context.write_token, input
        }, new AbortController().signal);
        const status = C.receipt(result);
        publish(store, { intent, result, phase: status === 'terminal' ? 'done' : status === 'rejected' ? 'rejected' : 'pending',
          error: status === 'rejected' ? result : null });
      } catch (error) {
        publish(store, { intent, phase: error && error.committed === false ? 'rejected' : 'pending', error });
      } finally { store.running = false; }
      if (store.state.phase === 'rejected' && typeof adapter.clearPending === 'function') {
        try { adapter.clearPending(); }
        catch (error) { publish(store, { ...store.state, phase: 'pending', error }); }
      }
      if (store.state.phase === 'pending') await check();
    }
    function reset() {
      if (store.running || ['sending', 'pending', 'checking'].includes(store.state.phase)) return false;
      if (store.state.intent && typeof adapter.clearPending === 'function') {
        try { adapter.clearPending(); }
        catch (error) { publish(store, { ...store.state, error }); return false; }
      }
      publish(store, { phase: 'idle' });
      return true;
    }
    return { ...state, locked, submit, check, reset };
  }
  const nonnegative = value => Number.isFinite(value) && value >= 0;
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
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
  function useSummary(adapter, revision) {
    return useQuery(async signal => {
      if (typeof adapter.summary !== 'function') throw C.failure('资源汇总接口尚未接入。');
      const result = C.query(await adapter.summary(signal), 'summary'), data = { ...result.data };
      if (!calendarSummary(data.calendar)) { data.calendar = null; data.calendar_error = '日历汇总缺失或协议不完整，无法核实。'; }
      if (!readinessSummary(data.readiness)) { data.readiness = null; data.readiness_error = '就绪口径缺失或协议不完整，未知。'; }
      return { ...result, data };
    }, [adapter, revision]);
  }
  function useCounts(adapter, revision) {
    const read = useSummary(adapter, revision), data = read.result && read.result.data;
    const names = { process: 'part', op_int: 'internal_op_types', op_ext: 'external_op_types' };
    const error = read.error ? C.message(read.error) : null;
    const counts = Object.fromEntries(Object.keys(C.nodes).map(node => [node, { total: data ? data.counts[names[node] || node] : null, error }]));
    counts.summary = { data, loading: read.loading, error, reload: read.reload };
    return counts;
  }
  window.APSResourceSession = { useQuery, useCommand, useCounts, useSummary };
})();
